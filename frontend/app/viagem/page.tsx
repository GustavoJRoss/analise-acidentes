"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import CartaoResultado from "@/components/CartaoResultado";
import LayoutMapa, { Mapa } from "@/components/LayoutMapa";
import type { Enquadramento } from "@/components/Mapa";
import { Passo } from "@/components/paineis/base";
import PainelClima from "@/components/paineis/PainelClima";
import PainelQuando from "@/components/paineis/PainelQuando";
import PainelRota, { type RotaRecente } from "@/components/paineis/PainelRota";
import { api } from "@/lib/api";
import { useDados } from "@/lib/contexto";
import { usePrevisao, useRecentes } from "@/lib/hooks";
import { limitesDe } from "@/lib/rodovias";
import type { Lugar, Rota } from "@/lib/tipos";
import { atualizarUrl, lugarDaUrl, lugarParaUrl } from "@/lib/url";

const pontoNoMapa = (lat: number, lon: number): Lugar => ({ nome: `Ponto no mapa (${lat.toFixed(4)}, ${lon.toFixed(4)})`, lat, lon });
const mesmaRota = (a: RotaRecente, b: RotaRecente) => a.origem.nome === b.origem.nome && a.destino.nome === b.destino.nome;

export default function PlanejarViagem() {
  const { trechos, porId } = useDados();
  const [origem, setOrigem] = useState<Lugar | null>(null);
  const [destino, setDestino] = useState<Lugar | null>(null);
  const [rota, setRota] = useState<Rota | null>(null);
  const [carregandoRota, setCarregandoRota] = useState(false);
  const [erroRota, setErroRota] = useState<string | null>(null);
  const [enquadrar, setEnquadrar] = useState<Enquadramento>(null);
  const [lidoDaUrl, setLidoDaUrl] = useState(false);
  const recentes = useRecentes<RotaRecente>("recentes-viagem", mesmaRota);

  // origem e destino vão para a URL (?de=lat,lon,nome&para=…): o link abre a mesma viagem
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    setOrigem(lugarDaUrl(p.get("de")));
    setDestino(lugarDaUrl(p.get("para")));
    setLidoDaUrl(true);
  }, []);

  useEffect(() => {
    if (lidoDaUrl) atualizarUrl({ de: lugarParaUrl(origem), para: lugarParaUrl(destino) });
  }, [lidoDaUrl, origem, destino]);

  // recalcula a rota quando origem e destino estão definidos
  const { adicionar } = recentes;
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
        adicionar({ origem, destino });
      })
      .catch((e) => !controle.signal.aborted && setErroRota((e as Error).message))
      .finally(() => !controle.signal.aborted && setCarregandoRota(false));
    return () => controle.abort();
  }, [origem, destino, adicionar]);

  const trechoIds = useMemo(() => rota?.trechos.map((t) => t.trecho_id) ?? [], [rota]);
  const { previsao, carregando, erro, probPorTrecho } = usePrevisao(trechoIds);

  const focarTrecho = useCallback((id: string) => {
    const coords = porId[id]?.geometry.coordinates.flat();
    if (coords?.length) setEnquadrar({ chave: Date.now(), limites: limitesDe(coords) });
  }, [porId]);

  function cliqueNoMapa(lat: number, lon: number) {
    if (!origem) setOrigem(pontoNoMapa(lat, lon));
    else setDestino(pontoNoMapa(lat, lon));
  }

  const barra = (
    <>
      <Passo numero={1} titulo="Sua viagem" abertoNoCelular
        resumo={origem && destino ? `${origem.nome.split(",")[0]} → ${destino.nome.split(",")[0]}` : undefined}>
        <PainelRota origem={origem} destino={destino} onOrigem={setOrigem} onDestino={setDestino}
          onInverter={() => { setOrigem(destino); setDestino(origem); }}
          onLimpar={() => { setOrigem(null); setDestino(null); }}
          recentes={recentes.itens} onLimparRecentes={recentes.limpar}
          onEscolherRecente={(r) => { setOrigem(r.origem); setDestino(r.destino); }}
          rota={rota} carregando={carregandoRota} erro={erroRota} />
      </Passo>
      <PainelQuando numero={2} />
      <PainelClima numero={3} trechoIds={trechoIds} />
    </>
  );

  return (
    <LayoutMapa barra={barra} emCenario={Object.keys(probPorTrecho).length > 0} selecionou={trechoIds.join(",")}
      cartao={<CartaoResultado tipo="rota" previsao={previsao} carregando={carregando} erro={erro}
        trechoIds={trechoIds} onFocarTrecho={focarTrecho} />}
      mapa={<Mapa trechos={trechos} filtroRede="todas" probPorTrecho={probPorTrecho} rota={rota}
        origem={origem} destino={destino} enquadrar={enquadrar} onClicarMapa={cliqueNoMapa}
        onMoverOrigem={(lat, lon) => setOrigem(pontoNoMapa(lat, lon))}
        onMoverDestino={(lat, lon) => setDestino(pontoNoMapa(lat, lon))} />}
      dica={!destino && (
        <div className="pointer-events-none absolute left-1/2 top-16 z-[500] -translate-x-1/2 whitespace-nowrap rounded-full bg-texto/85 px-3 py-1.5 text-xs text-superficie shadow md:bottom-16 md:top-auto">
          Clique no mapa para marcar {origem ? "o destino" : "a origem"}
        </div>
      )} />
  );
}
