"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import CartaoResultado from "@/components/CartaoResultado";
import { PainelClima, PainelOnde, PainelQuando } from "@/components/Paineis";
import SobreModelo from "@/components/SobreModelo";
import { api } from "@/lib/api";
import { FAIXAS, FAIXAS_HISTORICO, isoLocal, periodoAtual } from "@/lib/formato";
import type {
  CategoriaClima, ClimaPrevisto, Lugar, Metricas, Modo, Opcoes, Periodo, Previsao, Rota, TrechosGeoJSON,
} from "@/lib/tipos";

// Leaflet usa `window`: o mapa só é carregado no navegador
const Mapa = dynamic(() => import("@/components/Mapa"), {
  ssr: false,
  loading: () => <div className="flex h-full items-center justify-center bg-slate-100 text-sm text-slate-500">Carregando mapa…</div>,
});

type Limites = [[number, number], [number, number]];

function limitesDe(coords: number[][]): Limites {
  const lats = coords.map((c) => c[1]);
  const lons = coords.map((c) => c[0]);
  return [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]];
}

export default function Pagina() {
  const [trechos, setTrechos] = useState<TrechosGeoJSON | null>(null);
  const [opcoes, setOpcoes] = useState<Opcoes | null>(null);
  const [metricas, setMetricas] = useState<Metricas | null>(null);
  const [erroInicial, setErroInicial] = useState<string | null>(null);

  const [modo, setModo] = useState<Modo>("trecho");
  const [trechoId, setTrechoId] = useState<string | null>(null);
  const [origem, setOrigem] = useState<Lugar | null>(null);
  const [destino, setDestino] = useState<Lugar | null>(null);
  const [rota, setRota] = useState<Rota | null>(null);
  const [carregandoRota, setCarregandoRota] = useState(false);
  const [erroRota, setErroRota] = useState<string | null>(null);

  const [data, setData] = useState(() => isoLocal(new Date()));
  const [periodo, setPeriodo] = useState<Periodo>(() => periodoAtual());
  const [clima, setClima] = useState<CategoriaClima>("ceu_claro");
  const [climaPrevisto, setClimaPrevisto] = useState<ClimaPrevisto | null>(null);
  const [carregandoPrevisaoTempo, setCarregandoPrevisaoTempo] = useState(false);
  const [erroPrevisaoTempo, setErroPrevisaoTempo] = useState<string | null>(null);

  const [previsao, setPrevisao] = useState<Previsao | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [enquadrar, setEnquadrar] = useState<{ chave: number; limites: Limites } | null>(null);
  const painel = useRef<HTMLElement>(null);

  useEffect(() => {
    Promise.all([api.trechos(), api.opcoes(), api.modelo()])
      .then(([t, o, m]) => {
        setTrechos(t);
        setOpcoes(o);
        setMetricas(m);
      })
      .catch(() => setErroInicial("Não consegui carregar os dados. Confira se o backend está rodando em localhost:8000."));
  }, []);

  const porId = useMemo(
    () => Object.fromEntries((trechos?.features ?? []).map((f) => [f.properties.trecho_id, f])),
    [trechos],
  );
  const maisPerigosos = useMemo(
    () => [...(trechos?.features ?? [])].sort((a, b) => b.properties.acidentes - a.properties.acidentes).slice(0, 6).map((f) => f.properties),
    [trechos],
  );

  const trechoIds = useMemo(
    () => (modo === "trecho" ? (trechoId ? [trechoId] : []) : (rota?.trechos.map((t) => t.trecho_id) ?? [])),
    [modo, trechoId, rota],
  );

  const focarTrecho = useCallback((id: string) => {
    const f = porId[id];
    if (f) setEnquadrar({ chave: Date.now(), limites: limitesDe(f.geometry.coordinates.flat()) });
  }, [porId]);

  // ---- rota: recalcula quando origem e destino estão definidos ---------------------------------
  useEffect(() => {
    setRota(null);
    setErroRota(null);
    if (!origem || !destino) return;
    const controle = new AbortController();
    setCarregandoRota(true);
    api.rota(origem, destino, controle.signal)
      .then((r) => {
        setRota(r);
        setEnquadrar({ chave: Date.now(), limites: limitesDe(r.geometria.coordinates) });
      })
      .catch((e) => !controle.signal.aborted && setErroRota((e as Error).message))
      .finally(() => !controle.signal.aborted && setCarregandoRota(false));
    return () => controle.abort();
  }, [origem, destino]);

  // ---- previsão: recalcula sozinha quando qualquer entrada muda --------------------------------
  useEffect(() => {
    if (trechoIds.length === 0) {
      setPrevisao(null);
      setErro(null);
      return;
    }
    const controle = new AbortController();
    const timer = setTimeout(() => {
      setCarregando(true);
      setErro(null);
      api.prever({
        trecho_ids: trechoIds, data, periodo, clima,
        clima_personalizado: climaPrevisto
          ? { chuva_mm: climaPrevisto.chuva_mm, nebulosidade: climaPrevisto.nebulosidade, temperatura: climaPrevisto.temperatura }
          : null,
      }, controle.signal)
        .then(setPrevisao)
        .catch((e) => !controle.signal.aborted && setErro((e as Error).message))
        .finally(() => !controle.signal.aborted && setCarregando(false));
    }, 300);
    return () => {
      clearTimeout(timer);
      controle.abort();
    };
  }, [trechoIds, data, periodo, clima, climaPrevisto]);

  // no celular o resultado fica no topo do painel: ao escolher um lugar, rola até ele
  useEffect(() => {
    if (trechoIds.length > 0 && !window.matchMedia("(min-width: 768px)").matches) {
      painel.current?.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, [trechoIds]);

  // a previsão do tempo vale para um dia/período/lugar: qualquer mudança volta ao clima manual
  useEffect(() => {
    setClimaPrevisto(null);
    setErroPrevisaoTempo(null);
  }, [data, periodo, trechoIds]);

  async function usarPrevisaoTempo() {
    if (trechoIds.length === 0) return;
    setCarregandoPrevisaoTempo(true);
    setErroPrevisaoTempo(null);
    try {
      // para uma rota, usa o trecho do meio como referência do tempo
      const prev = await api.climaPrevisto(trechoIds[Math.floor(trechoIds.length / 2)], data, periodo);
      setClima(prev.categoria);
      setClimaPrevisto(prev);
    } catch (e) {
      setErroPrevisaoTempo((e as Error).message);
    } finally {
      setCarregandoPrevisaoTempo(false);
    }
  }

  function cliqueNoMapa(lat: number, lon: number) {
    const lugar = { nome: `Ponto no mapa (${lat.toFixed(4)}, ${lon.toFixed(4)})`, lat, lon };
    if (!origem) setOrigem(lugar);
    else setDestino(lugar);
  }

  const probPorTrecho = useMemo(
    () => Object.fromEntries((previsao?.trechos ?? []).filter((t) => trechoIds.includes(t.trecho_id)).map((t) => [t.trecho_id, t.probabilidade])),
    [previsao, trechoIds],
  );

  const resultado = (
    <CartaoResultado modo={modo} previsao={previsao} carregando={carregando} erro={erro}
      temSelecao={trechoIds.length > 0} opcoes={opcoes} usandoPrevisaoTempo={climaPrevisto !== null}
      onFocarTrecho={focarTrecho} />
  );

  return (
    <main className="flex h-dvh flex-col overflow-hidden md:flex-row">
      <aside ref={painel} className="order-2 flex min-h-0 flex-1 flex-col overflow-y-auto border-slate-200 bg-white md:order-1 md:w-[420px] md:flex-none md:border-r">
        <header className="border-b border-slate-100 px-5 py-4">
          <h1 className="text-lg font-bold tracking-tight text-slate-900">🚦 Risco nas BRs de Santa Catarina</h1>
          <p className="text-sm text-slate-600">
            Escolha onde, quando e com que tempo — o modelo estima a chance de acidente com base nos registros da PRF.
          </p>
        </header>

        {erroInicial && <p className="m-5 rounded-xl bg-red-50 p-3 text-sm text-red-700">{erroInicial}</p>}

        <div className="px-5 pt-4 md:hidden">{resultado}</div>

        <PainelOnde modo={modo} onModo={(m) => { setModo(m); setPrevisao(null); }}
          trecho={trechoId ? porId[trechoId]?.properties ?? null : null} maisPerigosos={maisPerigosos}
          onSelecionarTrecho={(id) => { setTrechoId(id); focarTrecho(id); }}
          origem={origem} destino={destino} onOrigem={setOrigem} onDestino={setDestino}
          onInverter={() => { setOrigem(destino); setDestino(origem); }}
          rota={rota} carregandoRota={carregandoRota} erroRota={erroRota} />
        <PainelQuando data={data} onData={setData} periodo={periodo} onPeriodo={setPeriodo} opcoes={opcoes} />
        <PainelClima clima={clima} onClima={(c) => { setClima(c); setClimaPrevisto(null); }} opcoes={opcoes} data={data}
          podeUsarPrevisao={trechoIds.length > 0} climaPrevisto={climaPrevisto}
          carregandoPrevisao={carregandoPrevisaoTempo} erroPrevisao={erroPrevisaoTempo} onUsarPrevisao={usarPrevisaoTempo} />
        <SobreModelo metricas={metricas} />
        <footer className="px-5 py-4 text-[11px] text-slate-400">
          Dados: PRF (acidentes 2025), © OpenStreetMap (mapa, rotas, busca), Open-Meteo (clima). Projeto de estudo.
        </footer>
      </aside>

      <section className="relative order-1 h-[42dvh] shrink-0 md:order-2 md:h-full md:flex-1">
        <Mapa trechos={trechos} modo={modo} trechoSelecionado={trechoId} probPorTrecho={probPorTrecho}
          rota={modo === "rota" ? rota : null} origem={modo === "rota" ? origem : null} destino={modo === "rota" ? destino : null}
          enquadrar={enquadrar} onClicarTrecho={(id) => setTrechoId(id)} onClicarMapa={cliqueNoMapa} />

        <div className="pointer-events-none absolute inset-x-0 top-0 z-[500] hidden p-4 md:flex md:justify-end">
          <div className="pointer-events-auto max-h-[calc(100dvh-2rem)] w-[380px] overflow-y-auto">{resultado}</div>
        </div>

        <div className="absolute bottom-2 left-2 z-[500] rounded-lg border border-slate-200 bg-white/95 px-2 py-1 text-[10px] text-slate-600 shadow-sm md:bottom-3 md:left-3 md:rounded-xl md:px-3 md:py-2 md:text-[11px]">
          {Object.keys(probPorTrecho).length > 0 ? (
            <>
              <div className="mb-1 hidden font-medium text-slate-700 md:block">Chance no cenário</div>
              <div className="flex gap-2">
                {FAIXAS.map((f) => (
                  <span key={f.rotulo} className="flex items-center gap-1">
                    <span className="h-1.5 w-4 rounded-full" style={{ background: f.cor }} />{f.rotulo}
                  </span>
                ))}
              </div>
            </>
          ) : (
            <>
              <div className="mb-1 font-medium text-slate-700">Acidentes em 2025<span className="hidden md:inline"> por trecho</span></div>
              <div className="flex gap-2">
                {FAIXAS_HISTORICO.map((f) => (
                  <span key={f.rotulo} className="flex items-center gap-1">
                    <span className="h-1.5 w-4 rounded-full" style={{ background: f.cor }} />{f.rotulo}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>
        {modo === "rota" && !destino && (
          <div className="absolute left-1/2 top-3 z-[500] -translate-x-1/2 rounded-full bg-slate-900/85 px-3 py-1.5 text-xs text-white shadow md:top-auto md:bottom-16">
            Clique no mapa para marcar {origem ? "o destino" : "a origem"}
          </div>
        )}
      </section>
    </main>
  );
}
