"use client";

import BuscaEndereco from "./BuscaEndereco";
import {
  ICONE_CLIMA, ICONE_PERIODO, capitalizar, corHistorico, dataExtensa, diasAte, isoLocal, nomeTrecho, somarDias,
} from "@/lib/formato";
import type {
  CategoriaClima, ClimaPrevisto, Lugar, Modo, Opcoes, Periodo, PropsTrecho, Rota,
} from "@/lib/tipos";

export function Passo({ numero, titulo, children }: { numero: number; titulo: string; children: React.ReactNode }) {
  return (
    <section className="border-b border-slate-100 px-5 py-4">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-800">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-900 text-xs text-white">{numero}</span>
        {titulo}
      </h2>
      {children}
    </section>
  );
}

function Segmentado<T extends string>({ opcoes, valor, onMudar, rotulo, colunas }: {
  opcoes: { id: T; conteudo: React.ReactNode; dica?: string }[];
  valor: T;
  onMudar: (v: T) => void;
  rotulo: string;
  colunas: number;
}) {
  return (
    <div role="radiogroup" aria-label={rotulo} className="grid gap-1.5"
      style={{ gridTemplateColumns: `repeat(${colunas}, minmax(0, 1fr))` }}>
      {opcoes.map((o) => (
        <button key={o.id} type="button" role="radio" aria-checked={valor === o.id} title={o.dica}
          onClick={() => onMudar(o.id)}
          className={`rounded-xl border px-2 py-2 text-center text-xs transition ${
            valor === o.id
              ? "border-blue-600 bg-blue-50 font-semibold text-blue-800 ring-1 ring-blue-600"
              : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50"
          }`}>
          {o.conteudo}
        </button>
      ))}
    </div>
  );
}

// ---- 1. Onde -----------------------------------------------------------------------------------
interface PropsOnde {
  modo: Modo;
  onModo: (m: Modo) => void;
  trecho: PropsTrecho | null;
  maisPerigosos: PropsTrecho[];
  onSelecionarTrecho: (id: string) => void;
  origem: Lugar | null;
  destino: Lugar | null;
  onOrigem: (l: Lugar | null) => void;
  onDestino: (l: Lugar | null) => void;
  onInverter: () => void;
  rota: Rota | null;
  carregandoRota: boolean;
  erroRota: string | null;
}

export function PainelOnde(p: PropsOnde) {
  return (
    <Passo numero={1} titulo="Onde">
      <Segmentado<Modo> rotulo="Tipo de seleção" colunas={2} valor={p.modo} onMudar={p.onModo}
        opcoes={[
          { id: "trecho", conteudo: "📍 Um trecho de BR" },
          { id: "rota", conteudo: "🧭 Uma viagem (rota)" },
        ]} />

      {p.modo === "trecho" ? (
        <div className="mt-3">
          {p.trecho ? (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-semibold text-slate-900">{nomeTrecho(p.trecho.br, p.trecho.trecho_km)}</div>
                  <div className="text-sm text-slate-600">{capitalizar(p.trecho.municipio)}</div>
                </div>
                <span className="mt-1 h-3 w-3 shrink-0 rounded-full" style={{ background: corHistorico(p.trecho.acidentes) }} />
              </div>
              <div className="mt-2 flex gap-4 text-xs text-slate-600">
                <span><b className="text-slate-900">{p.trecho.acidentes}</b> acidentes em 2025</span>
                <span><b className="text-slate-900">{p.trecho.mortos}</b> mortes</span>
                <span><b className="text-slate-900">{p.trecho.feridos_graves}</b> feridos graves</span>
              </div>
            </div>
          ) : (
            <p className="rounded-xl border border-dashed border-slate-300 p-3 text-sm text-slate-600">
              Clique numa rodovia no mapa ou escolha um dos trechos com mais acidentes:
            </p>
          )}
          <div className="mt-3">
            <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">Mais acidentes em 2025</div>
            <div className="flex flex-wrap gap-1.5">
              {p.maisPerigosos.map((t) => (
                <button key={t.trecho_id} type="button" onClick={() => p.onSelecionarTrecho(t.trecho_id)}
                  className={`rounded-full border px-2.5 py-1 text-xs transition ${
                    p.trecho?.trecho_id === t.trecho_id
                      ? "border-blue-600 bg-blue-50 text-blue-800"
                      : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                  }`}>
                  BR-{t.br} km {t.trecho_km} · {capitalizar(t.municipio)}
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-3 space-y-2">
          <div className="flex items-center gap-2">
            <div className="min-w-0 flex-1 space-y-2">
              <BuscaEndereco rotulo="Origem" corMarcador="#16a34a" valor={p.origem} onEscolher={p.onOrigem}
                placeholder="De onde? (cidade ou endereço)" />
              <BuscaEndereco rotulo="Destino" corMarcador="#dc2626" valor={p.destino} onEscolher={p.onDestino}
                placeholder="Para onde?" />
            </div>
            <button type="button" onClick={p.onInverter} aria-label="Inverter origem e destino" title="Inverter"
              className="shrink-0 rounded-full border border-slate-200 bg-white px-2 py-1 text-sm text-slate-600 shadow-sm hover:bg-slate-50">
              ⇅
            </button>
          </div>
          <p className="text-xs text-slate-500">
            Dica: você também pode clicar no mapa — o 1º clique marca a origem, o 2º o destino.
          </p>
          {p.carregandoRota && <p className="text-sm text-slate-600">Traçando rota…</p>}
          {p.erroRota && <p className="rounded-lg bg-red-50 p-2 text-sm text-red-700">{p.erroRota}</p>}
          {p.rota && !p.carregandoRota && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
              <b>{p.rota.distancia_km.toLocaleString("pt-BR")} km</b> · cerca de {Math.floor(p.rota.duracao_min / 60)}h
              {String(p.rota.duracao_min % 60).padStart(2, "0")} ·{" "}
              {p.rota.trechos.length > 0
                ? `passa por ${p.rota.trechos.length} trechos de BR federal`
                : "não passa por BR federal coberta pelo modelo"}
            </div>
          )}
        </div>
      )}
    </Passo>
  );
}

// ---- 2. Quando ---------------------------------------------------------------------------------
function proximoDiaSemana(desdeIso: string, diaSemana: number) {
  let d = desdeIso;
  for (let i = 0; i < 7; i++) {
    if (new Date(`${d}T12:00`).getDay() === diaSemana && i > 0) return d;
    d = somarDias(d, 1);
  }
  return d;
}

function sabadoDeVerao(hoje: string) {
  const ano = Number(hoje.slice(0, 4));
  const mes = Number(hoje.slice(5, 7));
  const inicio = mes <= 1 ? hoje : `${ano + 1}-01-01`;
  return proximoDiaSemana(somarDias(inicio, -1), 6);
}

interface PropsQuando {
  data: string;
  onData: (d: string) => void;
  periodo: Periodo;
  onPeriodo: (p: Periodo) => void;
  opcoes: Opcoes | null;
}

export function PainelQuando({ data, onData, periodo, onPeriodo, opcoes }: PropsQuando) {
  const hoje = isoLocal(new Date());
  const feriados = new Set(opcoes?.feriados ?? []);
  const proximoFeriado = opcoes?.feriados.find((f) => f >= hoje);
  const atalhos = [
    { rotulo: "Hoje", data: hoje },
    { rotulo: "Amanhã", data: somarDias(hoje, 1) },
    { rotulo: "Próximo sábado", data: proximoDiaSemana(hoje, 6) },
    ...(proximoFeriado ? [{ rotulo: "Próximo feriado", data: proximoFeriado }] : []),
    { rotulo: "Sábado de verão", data: sabadoDeVerao(hoje) },
  ];
  const dia = new Date(`${data}T12:00`);
  const selos = [
    feriados.has(data) && "🎉 Feriado",
    (feriados.has(somarDias(data, 1)) || feriados.has(somarDias(data, -1))) && !feriados.has(data) && "Véspera/pós-feriado",
    [0, 6].includes(dia.getDay()) && "Fim de semana",
    [11, 0, 1].includes(dia.getMonth()) && "🏖️ Temporada de verão",
  ].filter(Boolean) as string[];

  return (
    <Passo numero={2} titulo="Quando">
      <div className="flex flex-wrap gap-1.5">
        {atalhos.map((a) => (
          <button key={a.rotulo} type="button" onClick={() => onData(a.data)}
            className={`rounded-full border px-2.5 py-1 text-xs transition ${
              data === a.data ? "border-blue-600 bg-blue-50 text-blue-800" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
            }`}>
            {a.rotulo}
          </button>
        ))}
      </div>
      <label className="relative mt-2 flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm focus-within:border-blue-500">
        <span className="text-slate-500">📅</span>
        <span className="sr-only">Data</span>
        <input type="date" value={data} min="2025-01-01" max="2027-12-31"
          onChange={(e) => e.target.value && onData(e.target.value)}
          className="flex-1 bg-transparent outline-none" />
      </label>
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs">
        <span className="text-slate-600">{dataExtensa(data)}</span>
        {selos.map((s) => (
          <span key={s} className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800">{s}</span>
        ))}
      </div>

      <div className="mt-3">
        <Segmentado<Periodo> rotulo="Período do dia" colunas={4} valor={periodo} onMudar={onPeriodo}
          opcoes={(opcoes?.periodos ?? []).map((p) => ({
            id: p.id,
            conteudo: (
              <>
                <div className="text-base leading-none">{ICONE_PERIODO[p.id]}</div>
                <div className="mt-1">{p.rotulo}</div>
                <div className="text-[10px] font-normal text-slate-500">{p.faixa}</div>
              </>
            ),
          }))} />
      </div>
    </Passo>
  );
}

// ---- 3. Clima ----------------------------------------------------------------------------------
interface PropsClima {
  clima: CategoriaClima;
  onClima: (c: CategoriaClima) => void;
  opcoes: Opcoes | null;
  data: string;
  podeUsarPrevisao: boolean;
  climaPrevisto: ClimaPrevisto | null;
  carregandoPrevisao: boolean;
  erroPrevisao: string | null;
  onUsarPrevisao: () => void;
}

export function PainelClima(p: PropsClima) {
  const dias = diasAte(p.data);
  const previsaoDisponivel = dias >= 0 && dias <= 15;
  return (
    <Passo numero={3} titulo="Condições do tempo">
      <Segmentado<CategoriaClima> rotulo="Clima" colunas={4} valor={p.clima}
        onMudar={p.onClima}
        opcoes={(p.opcoes?.clima ?? []).map((c) => ({
          id: c.id,
          dica: `${Math.round(c.frequencia * 100)}% dos períodos de 2025 · ${c.chuva_mm} mm em 6 h`,
          conteudo: (
            <>
              <div className="text-base leading-none">{ICONE_CLIMA[c.id]}</div>
              <div className="mt-1">{c.rotulo}</div>
            </>
          ),
        }))} />

      {p.climaPrevisto ? (
        <div className="mt-2 rounded-xl bg-sky-50 p-2.5 text-xs text-sky-900">
          <b>Usando a previsão do tempo:</b> {p.climaPrevisto.chuva_mm.toLocaleString("pt-BR")} mm de chuva,{" "}
          {Math.round(p.climaPrevisto.nebulosidade)}% de nuvens, {p.climaPrevisto.temperatura.toLocaleString("pt-BR")} °C.
          Escolha uma opção acima para voltar ao manual.
        </div>
      ) : previsaoDisponivel ? (
        <button type="button" onClick={p.onUsarPrevisao} disabled={!p.podeUsarPrevisao || p.carregandoPrevisao}
          className="mt-2 w-full rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-sm font-medium text-sky-800 transition hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-50">
          {p.carregandoPrevisao ? "Buscando previsão…" : "🌦️ Usar a previsão do tempo para esse dia"}
        </button>
      ) : (
        <p className="mt-2 text-xs text-slate-500">A previsão do tempo automática vale para os próximos 16 dias.</p>
      )}
      {!p.podeUsarPrevisao && previsaoDisponivel && !p.climaPrevisto && (
        <p className="mt-1 text-xs text-slate-500">Escolha um trecho ou rota para buscar a previsão.</p>
      )}
      {p.erroPrevisao && <p className="mt-1 text-xs text-red-600">{p.erroPrevisao}</p>}
    </Passo>
  );
}
