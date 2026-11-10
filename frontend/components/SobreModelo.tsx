"use client";

import type { MetricasRede, Rede } from "@/lib/tipos";

const NOMES: Record<string, string> = {
  taxa_historica: "Histórico de acidentes do trecho",
  taxa_historica_periodo: "Histórico do trecho no período",
  acid_ult_365d: "Acidentes nos últimos 12 meses",
  periodo_idx: "Período do dia",
  lon: "Longitude",
  lat: "Latitude",
  dia_semana: "Dia da semana",
  delegacia: "Delegacia da PRF",
  nebulosidade: "Nebulosidade",
  trecho_km: "Km da rodovia",
  comprimento_km: "Extensão no município",
  br: "Rodovia (BR)",
  rodovia: "Rodovia (SC)",
  temperatura: "Temperatura",
  chuva_mm: "Chuva",
  feriado: "Feriado",
  vespera_ou_pos_feriado: "Véspera/pós-feriado",
  temporada_verao: "Verão",
  fim_de_semana: "Fim de semana",
  mes: "Mês",
  nivel_notificacao: "Nível de notificação do RENAEST",
  pandemia: "Pandemia (2020–2021)",
  vmd: "Volume de tráfego (VMD)",
};

const REDES: Record<Rede, { titulo: string; descricao: (m: MetricasRede) => string; limitacoes: React.ReactNode }> = {
  br: {
    titulo: "Rodovias federais (BRs)",
    descricao: (m) =>
      `${m.trechos} trechos de 10 km das BRs de SC, por dia e período, com os acidentes da PRF ` +
      `(${m.periodo_dados[0]} a ${m.periodo_dados[1]}) e o clima histórico do Open-Meteo. ` +
      `Avaliado prevendo o período após ${m.corte_teste}, sem ver esses dados no treino.`,
    limitacoes: <>o volume de tráfego (VMD do DNIT) é de uma única data e não varia com o dia; o km dos trechos sem acidente é interpolado na geometria do OpenStreetMap.</>,
  },
  sc: {
    titulo: "Rodovias estaduais (SC-xxx)",
    descricao: (m) =>
      `${m.trechos} trechos (cada rodovia dentro de cada município), com os acidentes do RENAEST ` +
      `(${m.periodo_dados[0]} a ${m.periodo_dados[1]}) e o clima histórico do Open-Meteo. ` +
      `Avaliado prevendo os 12 meses a partir de ${m.corte_teste}, treinando só com o período anterior.`,
    limitacoes: (
      <>
        em SC o RENAEST não traz coordenadas nem km: o local vem do endereço digitado pelo Detran, limpo e casado
        com as vias do OpenStreetMap, por isso o trecho é a rodovia inteira dentro do município; o volume de
        registros varia entre os anos (queda em 2024), o que reflete a notificação, não só os acidentes — o modelo
        recebe esse nível de notificação como variável; um trecho sem acidente pode ser só um endereço que não
        foi casado.
      </>
    ),
  },
};

export function SecaoRede({ rede, metricas }: { rede: Rede; metricas: MetricasRede }) {
  const m = metricas.modelos;
  const importancia = Object.entries(metricas.importancia).filter(([, v]) => v > 0).slice(0, 6);
  const maxImp = importancia[0]?.[1] ?? 1;
  const info = REDES[rede];

  return (
    <div className="space-y-3 text-sm leading-relaxed text-texto-suave">
      <h3 className="text-base font-semibold text-texto">{info.titulo}</h3>
      <p>{info.descricao(metricas)}</p>
      <table className="w-full max-w-md text-left tabular-nums">
        <thead className="text-xs text-texto-fraco">
          <tr><th className="font-medium">Modelo</th><th className="font-medium">ROC-AUC</th><th className="font-medium">PR-AUC</th></tr>
        </thead>
        <tbody className="text-texto">
          <tr><td>Com clima (em uso)</td><td>{m.com_clima.roc_auc}</td><td>{m.com_clima.pr_auc}</td></tr>
          <tr><td>Sem clima</td><td>{m.sem_clima.roc_auc}</td><td>{m.sem_clima.pr_auc}</td></tr>
          <tr><td>Só o histórico do trecho</td><td>{m.ingenuo_taxa_periodo.roc_auc}</td><td>{m.ingenuo_taxa_periodo.pr_auc}</td></tr>
          <tr className="text-texto-fraco"><td>Chute aleatório</td><td>0.5</td><td>{metricas.taxa_base_teste}</td></tr>
        </tbody>
      </table>
      <div>
        <div className="mb-1.5 font-medium text-texto">O que o modelo mais usa</div>
        {importancia.map(([nome, v]) => (
          <div key={nome} className="flex items-center gap-2">
            <span className="w-48 shrink-0 text-xs">{NOMES[nome] ?? nome}</span>
            <span className="h-1.5 flex-1 rounded-full bg-superficie-2">
              <span className="block h-full rounded-full bg-texto-fraco" style={{ width: `${(v / maxImp) * 100}%` }} />
            </span>
          </div>
        ))}
      </div>
      <p><b className="text-texto">Limitações:</b> {info.limitacoes}</p>
    </div>
  );
}
