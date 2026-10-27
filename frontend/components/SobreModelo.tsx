"use client";

import type { Metricas } from "@/lib/tipos";

const NOMES: Record<string, string> = {
  taxa_historica: "Histórico de acidentes do trecho",
  taxa_historica_periodo: "Histórico do trecho no período",
  acid_ult_90d: "Acidentes nos últimos 90 dias",
  periodo_idx: "Período do dia",
  lon: "Longitude",
  lat: "Latitude",
  dia_semana: "Dia da semana",
  delegacia: "Delegacia da PRF",
  nebulosidade: "Nebulosidade",
  trecho_km: "Km da rodovia",
  br: "Rodovia (BR)",
  temperatura: "Temperatura",
  chuva_mm: "Chuva",
  feriado: "Feriado",
  vespera_ou_pos_feriado: "Véspera/pós-feriado",
  temporada_verao: "Verão",
  fim_de_semana: "Fim de semana",
  mes: "Mês",
};

export default function SobreModelo({ metricas }: { metricas: Metricas | null }) {
  if (!metricas) return null;
  const m = metricas.modelos;
  const importancia = Object.entries(metricas.importancia).filter(([, v]) => v > 0).slice(0, 8);
  const maxImp = importancia[0]?.[1] ?? 1;

  return (
    <details className="group border-b border-slate-100 px-5 py-4">
      <summary className="cursor-pointer list-none text-sm font-semibold text-slate-800">
        <span className="mr-1 inline-block transition group-open:rotate-90">▸</span> Sobre o modelo e os dados
      </summary>
      <div className="mt-3 space-y-3 text-xs leading-relaxed text-slate-600">
        <p>
          Treinado com {metricas.trechos} trechos de 10 km das BRs de SC, por dia e período, a partir dos acidentes
          da PRF ({metricas.periodo_dados[0]} a {metricas.periodo_dados[1]}) e do clima histórico do Open-Meteo.
          Avaliado prevendo o período após {metricas.corte_teste}, sem ver esses dados no treino.
        </p>
        <table className="w-full text-left tabular-nums">
          <thead className="text-slate-500">
            <tr><th className="font-medium">Modelo</th><th className="font-medium">ROC-AUC</th><th className="font-medium">PR-AUC</th></tr>
          </thead>
          <tbody className="text-slate-800">
            <tr><td>Com clima (em uso)</td><td>{m.com_clima.roc_auc}</td><td>{m.com_clima.pr_auc}</td></tr>
            <tr><td>Sem clima</td><td>{m.sem_clima.roc_auc}</td><td>{m.sem_clima.pr_auc}</td></tr>
            <tr><td>Só o histórico do trecho</td><td>{m.ingenuo_taxa_periodo.roc_auc}</td><td>{m.ingenuo_taxa_periodo.pr_auc}</td></tr>
            <tr className="text-slate-500"><td>Chute aleatório</td><td>0.5</td><td>{metricas.taxa_base_teste}</td></tr>
          </tbody>
        </table>
        <div>
          <div className="mb-1 font-medium text-slate-700">O que o modelo mais usa</div>
          {importancia.map(([nome, v]) => (
            <div key={nome} className="flex items-center gap-2">
              <span className="w-44 shrink-0">{NOMES[nome] ?? nome}</span>
              <span className="h-1.5 flex-1 rounded-full bg-slate-100">
                <span className="block h-full rounded-full bg-slate-500" style={{ width: `${(v / maxImp) * 100}%` }} />
              </span>
            </div>
          ))}
        </div>
        <p>
          <b>Limitações:</b> só um ano de dados; sem volume de tráfego (o modelo aprende sobretudo <i>onde</i> já
          aconteceu); só trechos que tiveram acidente em 2025; o clima pouco muda o resultado nesses dados.
        </p>
      </div>
    </details>
  );
}
