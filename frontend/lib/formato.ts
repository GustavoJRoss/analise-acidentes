import type { Periodo } from "./tipos";

export const ICONE_PERIODO: Record<Periodo, string> = {
  madrugada: "🌙",
  manha: "🌅",
  tarde: "☀️",
  noite: "🌆",
};

export const ICONE_CLIMA: Record<string, string> = {
  ceu_claro: "☀️",
  nublado: "☁️",
  chuva: "🌧️",
  chuva_forte: "⛈️",
};

export function nomeTrecho(br: number, km: number) {
  return `BR-${br} · km ${km}–${km + 10}`;
}

export function porcentagem(p: number, casas?: number) {
  const valor = p * 100;
  const digitos = casas ?? (valor < 1 ? 2 : valor < 10 ? 1 : 0);
  return `${valor.toLocaleString("pt-BR", { minimumFractionDigits: digitos, maximumFractionDigits: digitos })}%`;
}

export function capitalizar(texto: string) {
  return texto.toLowerCase().replace(/(^|\s)\S/g, (l) => l.toUpperCase());
}

// Faixas de risco para a probabilidade em um período de 6 h
export const FAIXAS = [
  { ate: 0.02, rotulo: "Baixo", cor: "#16a34a", fundo: "bg-green-50", texto: "text-green-700" },
  { ate: 0.05, rotulo: "Moderado", cor: "#ca8a04", fundo: "bg-yellow-50", texto: "text-yellow-700" },
  { ate: 0.12, rotulo: "Alto", cor: "#ea580c", fundo: "bg-orange-50", texto: "text-orange-700" },
  { ate: Infinity, rotulo: "Muito alto", cor: "#dc2626", fundo: "bg-red-50", texto: "text-red-700" },
];

export function faixaRisco(p: number) {
  return FAIXAS.find((f) => p < f.ate)!;
}

// Cor do mapa base: acidentes registrados no trecho em 2025
export const FAIXAS_HISTORICO = [
  { ate: 10, cor: "#86efac", rotulo: "até 10" },
  { ate: 30, cor: "#fde047", rotulo: "10–30" },
  { ate: 70, cor: "#fb923c", rotulo: "30–70" },
  { ate: Infinity, cor: "#ef4444", rotulo: "70+" },
];

export function corHistorico(acidentes: number) {
  return FAIXAS_HISTORICO.find((f) => acidentes < f.ate)!.cor;
}

// ---- datas (sempre em horário local, formato AAAA-MM-DD) ------------------------------------
export function isoLocal(d: Date) {
  const mes = String(d.getMonth() + 1).padStart(2, "0");
  const dia = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mes}-${dia}`;
}

export function deIso(iso: string) {
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(a, m - 1, d);
}

export function somarDias(iso: string, dias: number) {
  const d = deIso(iso);
  d.setDate(d.getDate() + dias);
  return isoLocal(d);
}

export function diasAte(iso: string) {
  const hoje = deIso(isoLocal(new Date()));
  return Math.round((deIso(iso).getTime() - hoje.getTime()) / 86_400_000);
}

export function dataExtensa(iso: string) {
  const texto = deIso(iso).toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

export function periodoAtual(): Periodo {
  const h = new Date().getHours();
  return h < 6 ? "madrugada" : h < 12 ? "manha" : h < 18 ? "tarde" : "noite";
}
