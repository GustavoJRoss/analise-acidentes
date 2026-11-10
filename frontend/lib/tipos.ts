export type Periodo = "madrugada" | "manha" | "tarde" | "noite";
export type CategoriaClima = "ceu_claro" | "nublado" | "chuva" | "chuva_forte";
export type Modo = "trecho" | "rota";
// "br": BRs (PRF, trechos de 10 km) · "sc": rodovias estaduais (RENAEST, rodovia × município)
export type Rede = "br" | "sc";

interface DescricaoTrecho {
  trecho_id: string;
  rede: Rede;
  rodovia: string;           // "BR-101", "SC-401"
  rotulo: string;            // "BR-101 · km 200–210", "SC-401 · Florianópolis"
  municipio: string;
  comprimento_km: number;
  acidentes_ano: number;
  densidade: number;         // acidentes por 10 km por ano
}

export interface PropsTrecho extends DescricaoTrecho {
  acidentes: number;
  mortos: number;
  periodo_dados: string;
  centro: [number, number];
}

export interface TrechoPrevisto extends DescricaoTrecho {
  probabilidade: number;
  media_periodo: number;
}

export interface TrechosGeoJSON {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    properties: PropsTrecho;
    geometry: { type: "MultiLineString"; coordinates: number[][][] };
  }[];
}

export interface Opcoes {
  clima: { id: CategoriaClima; rotulo: string; chuva_mm: number; frequencia: number }[];
  periodos: { id: Periodo; rotulo: string; faixa: string }[];
  feriados: string[];
}

export interface Lugar {
  nome: string;
  lat: number;
  lon: number;
}

export interface Rota {
  geometria: { type: "LineString"; coordinates: [number, number][] };
  distancia_km: number;
  duracao_min: number;
  trechos: { trecho_id: string; km_na_rota: number }[];
}

export interface ClimaPrevisto {
  chuva_mm: number;
  nebulosidade: number;
  temperatura: number;
  categoria: CategoriaClima;
}

export interface Fator {
  fator: string;
  efeito: number;
  efeito_relativo: number;
}

export interface Previsao {
  probabilidade: number;
  media_referencia: number;
  razao_media: number | null;
  trechos: TrechoPrevisto[];
  fatores: Fator[];
  cenario: {
    data: string;
    periodo: Periodo;
    clima: CategoriaClima;
    feriado: boolean;
    vespera_ou_pos_feriado: boolean;
    fim_de_semana: boolean;
    temporada_verao: boolean;
    chuva_mm: number;
    temperatura: number;
  };
}

export interface MetricasRede {
  taxa_base_teste: number;
  modelos: Record<string, { roc_auc: number; pr_auc: number; brier: number }>;
  importancia: Record<string, number>;
  efeito_clima_prob_media: Record<CategoriaClima, number>;
  periodo_dados: [string, string];
  corte_teste: string;
  trechos: number;
}

export type Metricas = Partial<Record<Rede, MetricasRede>>;
