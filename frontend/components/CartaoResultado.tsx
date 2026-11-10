"use client";

import { ArrowDown, ArrowUp, Check, ChevronRight, CloudSun, Link2 } from "lucide-react";
import { useEffect, useState } from "react";

import { IconeClima, IconePeriodo } from "./Icones";
import { useCenario, useDados } from "@/lib/contexto";
import { capitalizar, dataExtensa, faixaRisco, porcentagem, umEmN } from "@/lib/formato";
import { useComparacaoPeriodos } from "@/lib/hooks";
import type { Periodo, Previsao, TrechoPrevisto } from "@/lib/tipos";

export type TipoSelecao = "trecho" | "rodovia" | "rota";

interface Props {
  tipo: TipoSelecao;
  previsao: Previsao | null;
  carregando: boolean;
  erro: string | null;
  trechoIds: string[];
  onFocarTrecho: (id: string) => void;
}

const VAZIO: Record<TipoSelecao, string> = {
  trecho: "Clique num trecho de rodovia no mapa (BRs em linha contínua, estaduais tracejadas) para ver a probabilidade de acidente nas condições que você escolher.",
  rodovia: "Escolha uma rodovia na barra lateral para ver a chance de acidente em toda a extensão dela.",
  rota: "Informe origem e destino para ver o risco ao longo da sua viagem pelas rodovias federais e estaduais de SC.",
};

const PERIODOS: Periodo[] = ["madrugada", "manha", "tarde", "noite"];

function SeloRede({ rede }: { rede: TrechoPrevisto["rede"] }) {
  return (
    <span className={`shrink-0 rounded px-1 text-[10px] font-semibold ${
      rede === "br" ? "bg-superficie-3 text-texto-suave" : "bg-violet-100 text-violet-800 dark:bg-violet-500/15 dark:text-violet-300"
    }`}>
      {rede === "br" ? "BR" : "SC"}
    </span>
  );
}

function CopiarLink() {
  const [copiado, setCopiado] = useState(false);
  useEffect(() => {
    if (!copiado) return;
    const t = setTimeout(() => setCopiado(false), 2000);
    return () => clearTimeout(t);
  }, [copiado]);

  async function copiar() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopiado(true);
    } catch {
      // sem permissão de área de transferência: abre o diálogo nativo de compartilhar, se houver
      navigator.share?.({ url: window.location.href }).catch(() => {});
    }
  }

  return (
    <button type="button" onClick={copiar} title="Copiar link com este cenário"
      className="flex items-center gap-1 rounded-full bg-superficie/70 px-2 py-1 text-[11px] font-medium text-texto-suave transition hover:bg-superficie hover:text-texto">
      {copiado ? <Check size={12} aria-hidden /> : <Link2 size={12} aria-hidden />}
      <span aria-live="polite">{copiado ? "Copiado" : "Copiar link"}</span>
    </button>
  );
}

/** Os 4 períodos do dia lado a lado: responde "qual o melhor horário?" e troca o período com um clique. */
function MelhorHorario({ tipo, trechoIds, previsao }: { tipo: TipoSelecao; trechoIds: string[]; previsao: Previsao }) {
  const { opcoes } = useDados();
  const { periodo, setPeriodo } = useCenario();
  const { valores, completo } = useComparacaoPeriodos(trechoIds, previsao);
  const max = Math.max(...PERIODOS.map((p) => valores[p] ?? 0), 1e-6);
  const melhor = completo ? PERIODOS.reduce((m, p) => (valores[p]! < valores[m]! ? p : m), PERIODOS[0]) : null;

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-texto-fraco">
          {tipo === "rota" ? "Quando sair?" : "Melhor horário nesse dia"}
        </span>
        {melhor && melhor !== periodo && (
          <button type="button" onClick={() => setPeriodo(melhor)} className="text-xs font-medium text-primaria hover:underline">
            Ver {opcoes?.periodos.find((p) => p.id === melhor)?.rotulo.toLowerCase()} →
          </button>
        )}
      </div>
      <div role="radiogroup" aria-label="Comparar períodos do dia" className="grid grid-cols-4 gap-1.5">
        {PERIODOS.map((p) => {
          const v = valores[p];
          const info = opcoes?.periodos.find((x) => x.id === p);
          const atual = p === periodo;
          return (
            <button key={p} type="button" role="radio" aria-checked={atual} onClick={() => setPeriodo(p)}
              title={`${info?.rotulo} (${info?.faixa})${v !== undefined ? `: ${porcentagem(v)}` : ""}`}
              className={`flex flex-col items-center gap-1 rounded-xl border px-1 pb-1.5 pt-2 text-[11px] transition ${
                atual ? "border-primaria bg-primaria-suave text-primaria-texto" : "border-borda text-texto-suave hover:bg-superficie-2"
              }`}>
              <span className="flex h-10 w-full items-end justify-center">
                {v === undefined
                  ? <span className="h-3 w-5 animate-pulse rounded-sm bg-superficie-3" />
                  : <span className="w-5 rounded-sm transition-all" style={{ height: `${Math.max(8, (v / max) * 100)}%`, background: faixaRisco(v).cor }} />}
              </span>
              <span className="font-semibold tabular-nums">{v === undefined ? "…" : porcentagem(v)}</span>
              <span className="flex items-center gap-0.5"><IconePeriodo periodo={p} size={12} />{info?.rotulo}</span>
              {melhor === p && <span className="rounded-full bg-green-100 px-1.5 text-[9px] font-semibold text-green-800 dark:bg-green-500/15 dark:text-green-300">menor</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ListaTrechos({ trechos, titulo, onFocar }: { trechos: TrechoPrevisto[]; titulo: string; onFocar: (id: string) => void }) {
  const maxProb = Math.max(...trechos.map((t) => t.probabilidade), 1e-6);
  return (
    <div>
      <div className="mb-2 text-xs font-medium uppercase tracking-wide text-texto-fraco">{titulo}</div>
      <ul className="max-h-64 space-y-1 overflow-auto pr-1">
        {trechos.map((t) => (
          <li key={t.trecho_id}>
            <button type="button" onClick={() => onFocar(t.trecho_id)} title="Ver no mapa"
              className="flex w-full items-center gap-2 rounded-lg px-1.5 py-1 text-left text-xs hover:bg-superficie-2">
              <SeloRede rede={t.rede} />
              <span className="w-32 shrink-0 truncate font-medium text-texto-suave" title={t.rotulo}>
                {t.rede === "br" ? t.rotulo : t.rotulo.replace(" · ", " ")}
              </span>
              <span className="relative h-2 flex-1 overflow-hidden rounded-full bg-superficie-2">
                <span className="absolute inset-y-0 left-0 rounded-full"
                  style={{ width: `${(t.probabilidade / maxProb) * 100}%`, background: faixaRisco(t.probabilidade).cor }} />
              </span>
              <span className="w-12 shrink-0 text-right tabular-nums text-texto-suave">{porcentagem(t.probabilidade)}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function CartaoResultado(p: Props) {
  const { opcoes } = useDados();
  const { climaPrevisto } = useCenario();
  const caixa = "rounded-2xl border border-borda bg-superficie shadow-sm";

  if (p.trechoIds.length === 0) {
    return (
      <div className={`${caixa} p-4 text-sm text-texto-suave`}>
        <div className="mb-1 text-base font-semibold text-texto">Qual a chance de acidente?</div>
        {VAZIO[p.tipo]}
      </div>
    );
  }
  if (p.erro) {
    return <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 shadow-sm dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">{p.erro}</div>;
  }
  if (!p.previsao) {
    return (
      <div className={`${caixa} space-y-3 p-4`} aria-busy>
        <div className="h-3 w-3/4 animate-pulse rounded bg-superficie-3" />
        <div className="h-12 w-32 animate-pulse rounded-lg bg-superficie-3" />
        <div className="h-3 w-1/2 animate-pulse rounded bg-superficie-3" />
      </div>
    );
  }

  const { previsao } = p;
  const faixa = faixaRisco(previsao.probabilidade);
  const periodo = opcoes?.periodos.find((x) => x.id === previsao.cenario.periodo);
  const clima = opcoes?.clima.find((x) => x.id === previsao.cenario.clima);
  const n = previsao.trechos.length;
  const temEstadual = previsao.trechos.some((t) => t.rede === "sc");
  const soEstadual = previsao.trechos.every((t) => t.rede === "sc");
  const frequencia = temEstadual ? "a frequência histórica" : "a frequência de 2025";
  const onde = p.tipo === "trecho" ? "neste trecho" : "nesses trechos";
  const piorTrecho = [...previsao.trechos].sort((a, b) => b.probabilidade - a.probabilidade)[0];
  const chuvaReduz = previsao.cenario.chuva_mm >= 1 && previsao.fatores.some(
    (f) => (f.fator.startsWith("Chuva") || f.fator.startsWith("Clima previsto")) && f.efeito < 0,
  );
  const titulo = {
    trecho: "Chance de ao menos 1 acidente neste trecho",
    rodovia: `Chance de ao menos 1 acidente em algum dos ${n} trechos da ${previsao.trechos[0]?.rodovia}`,
    rota: `Chance de ao menos 1 acidente em algum dos ${n} trechos da rota`,
  }[p.tipo];
  const umEm = umEmN(previsao.probabilidade);

  return (
    <div className={`${caixa} transition-opacity ${p.carregando ? "opacity-60" : ""}`} aria-live="polite" aria-busy={p.carregando}>
      <div className={`rounded-t-2xl p-4 ${faixa.fundo}`}>
        <div className="flex items-start justify-between gap-2">
          <div className="text-xs font-medium text-texto-suave">{titulo}</div>
          <CopiarLink />
        </div>
        <div className="mt-1 flex flex-wrap items-end gap-x-3 gap-y-1">
          <div className={`text-5xl font-bold tabular-nums tracking-tight ${faixa.texto}`}>{porcentagem(previsao.probabilidade)}</div>
          <div className="mb-1.5 flex flex-col gap-0.5">
            <span className={`w-fit rounded-full bg-superficie/70 px-2 py-0.5 text-xs font-semibold ${faixa.texto}`}>Risco {faixa.rotulo.toLowerCase()}</span>
            {umEm && <span className="text-[11px] text-texto-suave">≈ {umEm} períodos como este</span>}
          </div>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-texto-suave">
          <span>{dataExtensa(previsao.cenario.data)}</span>·
          <span className="inline-flex items-center gap-1"><IconePeriodo periodo={previsao.cenario.periodo} size={12} />{periodo?.rotulo} ({periodo?.faixa})</span>·
          {climaPrevisto
            ? <span className="inline-flex items-center gap-1"><CloudSun size={12} aria-hidden />previsão do tempo</span>
            : <span className="inline-flex items-center gap-1"><IconeClima clima={previsao.cenario.clima} size={12} />{clima?.rotulo}</span>}
        </div>
        {previsao.razao_media !== null && (
          <div className="mt-2 flex items-center gap-1 text-sm text-texto">
            {previsao.razao_media >= 1.05
              ? <><ArrowUp size={14} className="text-red-600 dark:text-red-400" aria-hidden /><b>{previsao.razao_media.toLocaleString("pt-BR")}×</b> {frequencia} {onde} nesse período</>
              : previsao.razao_media <= 0.95
                ? <><ArrowDown size={14} className="text-green-600 dark:text-green-400" aria-hidden /><b>{previsao.razao_media.toLocaleString("pt-BR")}×</b> {frequencia} {onde} nesse período</>
                : <>Parecido com {frequencia} {onde} nesse período ({porcentagem(previsao.media_referencia)})</>}
          </div>
        )}
      </div>

      <div className="space-y-4 p-4">
        <MelhorHorario tipo={p.tipo} trechoIds={p.trechoIds} previsao={previsao} />

        {p.tipo !== "trecho" && n > 0 && (
          <div className="space-y-2">
            <ListaTrechos onFocar={p.onFocarTrecho}
              titulo={p.tipo === "rota" ? "Trechos da viagem, na ordem" : "Trechos da rodovia, do mais crítico"}
              trechos={p.tipo === "rota" ? previsao.trechos : [...previsao.trechos].sort((a, b) => b.probabilidade - a.probabilidade)} />
            {piorTrecho && (
              <button type="button" onClick={() => p.onFocarTrecho(piorTrecho.trecho_id)}
                className="text-left text-xs text-texto-suave hover:text-texto">
                Mais crítico: <b className="text-texto">{piorTrecho.rotulo}</b>
                {piorTrecho.rede === "br" && <> ({capitalizar(piorTrecho.municipio)})</>} · <span className="text-primaria">ver no mapa</span>
              </button>
            )}
          </div>
        )}

        <details className="group rounded-xl border border-borda">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 text-sm font-medium text-texto">
            <ChevronRight size={14} aria-hidden className="text-texto-fraco transition-transform group-open:rotate-90" />
            Por que esse valor?
          </summary>
          <div className="space-y-2 px-3 pb-3">
            <p className="text-[11px] text-texto-fraco">
              Quanto cada fator aumenta (+) ou diminui (−) a chance em relação ao que seria esperado sem ele.
            </p>
            <ul className="space-y-1.5">
              {previsao.fatores.slice(0, 5).map((f) => {
                const pct = Math.round(f.efeito_relativo * 100);
                const sobe = pct > 0;
                return (
                  <li key={f.fator} className="flex items-center justify-between gap-3 text-sm">
                    <span className="text-texto-suave">{f.fator}</span>
                    <span className={`shrink-0 rounded-md px-1.5 py-0.5 text-xs font-semibold tabular-nums ${
                      pct === 0 ? "bg-superficie-2 text-texto-suave"
                        : sobe ? "bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-300"
                          : "bg-green-50 text-green-700 dark:bg-green-500/10 dark:text-green-300"
                    }`}>
                      {pct === 0 ? "≈ 0%" : `${sobe ? "+" : ""}${pct}%`}
                    </span>
                  </li>
                );
              })}
            </ul>
            {chuvaReduz && (
              <p className="rounded-xl bg-sky-50 p-2.5 text-xs leading-relaxed text-sky-900 dark:bg-sky-500/10 dark:text-sky-200">
                <b>Por que a chuva reduz?</b> Nos dados, períodos de chuva tiveram <i>menos</i> acidentes nesses trechos —
                provavelmente porque menos gente pega a estrada. O modelo mede a chance de acontecer algum acidente no
                trecho, não o risco de quem está dirigindo: na chuva, o risco por veículo tende a ser maior.
              </p>
            )}
          </div>
        </details>

        <p className="text-[11px] leading-relaxed text-texto-fraco">
          Probabilidade de ocorrer ao menos um acidente {p.tipo !== "trecho" ? "em algum desses trechos" : soEstadual
            ? "nesse trecho da rodovia estadual (toda a extensão dentro do município)" : "nesse trecho de 10 km"},
          durante o período de 6 h escolhido, envolvendo qualquer veículo. Não é o risco individual de quem viaja.
          {" "}Fontes: {temEstadual && !soEstadual ? "PRF (BRs) e RENAEST (estaduais)"
            : soEstadual ? "RENAEST/Senatran, acidentes informados pelo Detran-SC" : "PRF"}.
        </p>
      </div>
    </div>
  );
}
