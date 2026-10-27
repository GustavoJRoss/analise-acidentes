"use client";

import { ICONE_CLIMA, ICONE_PERIODO, capitalizar, dataExtensa, faixaRisco, porcentagem } from "@/lib/formato";
import type { Modo, Opcoes, Previsao } from "@/lib/tipos";

interface Props {
  modo: Modo;
  previsao: Previsao | null;
  carregando: boolean;
  erro: string | null;
  temSelecao: boolean;
  opcoes: Opcoes | null;
  usandoPrevisaoTempo: boolean;
  onFocarTrecho: (id: string) => void;
}

export default function CartaoResultado(p: Props) {
  if (!p.temSelecao) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm">
        <div className="mb-1 text-base font-semibold text-slate-900">Qual a chance de acidente?</div>
        {p.modo === "trecho"
          ? "Clique num trecho de rodovia federal no mapa para ver a probabilidade de acidente nas condições que você escolher."
          : "Informe origem e destino para ver o risco ao longo da sua viagem pelas BRs de SC."}
      </div>
    );
  }
  if (p.erro) {
    return <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 shadow-sm">{p.erro}</div>;
  }
  if (!p.previsao) {
    return <div className="h-40 animate-pulse rounded-2xl border border-slate-200 bg-white shadow-sm" />;
  }

  const { previsao } = p;
  const faixa = faixaRisco(previsao.probabilidade);
  const periodo = p.opcoes?.periodos.find((x) => x.id === previsao.cenario.periodo);
  const clima = p.opcoes?.clima.find((x) => x.id === previsao.cenario.clima);
  const ehRota = p.modo === "rota";
  const piorTrecho = [...previsao.trechos].sort((a, b) => b.probabilidade - a.probabilidade)[0];
  const maxProb = piorTrecho?.probabilidade ?? 1;
  const chuvaReduz = previsao.cenario.chuva_mm >= 1 && previsao.fatores.some(
    (f) => (f.fator.startsWith("Chuva") || f.fator.startsWith("Clima previsto")) && f.efeito < 0,
  );

  return (
    <div className={`rounded-2xl border border-slate-200 bg-white shadow-sm transition-opacity ${p.carregando ? "opacity-60" : ""}`}
      aria-live="polite" aria-busy={p.carregando}>
      <div className={`rounded-t-2xl p-4 ${faixa.fundo}`}>
        <div className="text-xs font-medium text-slate-600">
          {ehRota
            ? `Chance de ocorrer ao menos 1 acidente em algum dos ${previsao.trechos.length} trechos da rota`
            : "Chance de ocorrer ao menos 1 acidente neste trecho"}
        </div>
        <div className="mt-1 flex items-end gap-3">
          <div className={`text-5xl font-bold tabular-nums tracking-tight ${faixa.texto}`}>{porcentagem(previsao.probabilidade)}</div>
          <div className={`mb-1.5 rounded-full bg-white/70 px-2 py-0.5 text-xs font-semibold ${faixa.texto}`}>{faixa.rotulo}</div>
        </div>
        <div className="mt-1 text-xs text-slate-600">
          <span>{dataExtensa(previsao.cenario.data)}</span> · {ICONE_PERIODO[previsao.cenario.periodo]}{" "}
          {periodo?.rotulo} ({periodo?.faixa}) ·{" "}
          {p.usandoPrevisaoTempo ? "🌦️ previsão do tempo" : `${ICONE_CLIMA[previsao.cenario.clima]} ${clima?.rotulo}`}
        </div>
        {previsao.razao_media !== null && (
          <div className="mt-2 text-sm text-slate-700">
            {previsao.razao_media >= 1.05
              ? <>⬆️ <b>{previsao.razao_media.toLocaleString("pt-BR")}×</b> a frequência de 2025 {ehRota ? "nesses trechos" : "neste trecho"} nesse período</>
              : previsao.razao_media <= 0.95
                ? <>⬇️ <b>{previsao.razao_media.toLocaleString("pt-BR")}×</b> a frequência de 2025 {ehRota ? "nesses trechos" : "neste trecho"} nesse período</>
                : <>Parecido com a frequência de 2025 {ehRota ? "nesses trechos" : "neste trecho"} nesse período ({porcentagem(previsao.media_referencia)})</>}
          </div>
        )}
      </div>

      <div className="space-y-4 p-4">
        <div>
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">O que mais pesa nesse cenário</div>
          <ul className="space-y-1.5">
            {previsao.fatores.slice(0, 4).map((f) => {
              const pct = Math.round(f.efeito_relativo * 100);
              const sobe = pct > 0;
              return (
                <li key={f.fator} className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-slate-700">{f.fator}</span>
                  <span className={`shrink-0 rounded-md px-1.5 py-0.5 text-xs font-semibold tabular-nums ${
                    pct === 0 ? "bg-slate-100 text-slate-600" : sobe ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"
                  }`}>
                    {pct === 0 ? "≈ 0%" : `${sobe ? "+" : ""}${pct}%`}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>

        {chuvaReduz && (
          <p className="rounded-xl bg-sky-50 p-2.5 text-xs leading-relaxed text-sky-900">
            <b>Por que a chuva reduz?</b> Em 2025, períodos de chuva tiveram <i>menos</i> acidentes nos trechos —
            provavelmente porque menos gente pega a estrada. O modelo mede a chance de acontecer algum acidente no
            trecho, não o risco de quem está dirigindo: na chuva, o risco por veículo tende a ser maior.
          </p>
        )}

        {ehRota && previsao.trechos.length > 0 && (
          <div>
            <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Trechos da viagem, na ordem</div>
            <ul className="max-h-64 space-y-1 overflow-auto pr-1">
              {previsao.trechos.map((t) => {
                const f = faixaRisco(t.probabilidade);
                return (
                  <li key={t.trecho_id}>
                    <button type="button" onClick={() => p.onFocarTrecho(t.trecho_id)}
                      className="flex w-full items-center gap-2 rounded-lg px-1.5 py-1 text-left text-xs hover:bg-slate-50">
                      <span className="w-28 shrink-0 font-medium text-slate-700">BR-{t.br} km {t.trecho_km}</span>
                      <span className="relative h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                        <span className="absolute inset-y-0 left-0 rounded-full"
                          style={{ width: `${(t.probabilidade / maxProb) * 100}%`, background: f.cor }} />
                      </span>
                      <span className="w-12 shrink-0 text-right tabular-nums text-slate-700">{porcentagem(t.probabilidade)}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
            {piorTrecho && (
              <p className="mt-2 text-xs text-slate-600">
                Mais crítico: <b>BR-{piorTrecho.br} km {piorTrecho.trecho_km}</b> ({capitalizar(piorTrecho.municipio)}).
              </p>
            )}
          </div>
        )}

        <p className="text-[11px] leading-relaxed text-slate-500">
          Probabilidade de ocorrer ao menos um acidente registrado pela PRF {ehRota ? "em algum desses trechos" : "nesse trecho de 10 km"},
          durante o período de 6 h escolhido, envolvendo qualquer veículo. Não é o risco individual de quem viaja.
        </p>
      </div>
    </div>
  );
}
