import type { Periodo } from "./tipos";

export function porcentagem(p: number, casas?: number) {
  const valor = p * 100;
  const digitos = casas ?? (valor < 1 ? 2 : valor < 10 ? 1 : 0);
  return `${valor.toLocaleString("pt-BR", { minimumFractionDigits: digitos, maximumFractionDigits: digitos })}%`;
}

/** "SAO JOSE" (PRF) → "Sao Jose". Nomes já escritos certo (IBGE: "Braço do Norte") ficam como estão. */
export function capitalizar(texto: string) {
  if (texto !== texto.toUpperCase()) return texto;
  return texto.toLowerCase().replace(/(^|\s)\S/g, (l) => l.toUpperCase());
}

// Faixas de risco para a probabilidade em um período de 6 h
export const FAIXAS = [
  { ate: 0.02, rotulo: "Baixo", cor: "#16a34a", fundo: "bg-green-50 dark:bg-green-500/10", texto: "text-green-700 dark:text-green-400" },
  { ate: 0.05, rotulo: "Moderado", cor: "#ca8a04", fundo: "bg-yellow-50 dark:bg-yellow-500/10", texto: "text-yellow-700 dark:text-yellow-400" },
  { ate: 0.12, rotulo: "Alto", cor: "#ea580c", fundo: "bg-orange-50 dark:bg-orange-500/10", texto: "text-orange-700 dark:text-orange-400" },
  { ate: Infinity, rotulo: "Muito alto", cor: "#dc2626", fundo: "bg-red-50 dark:bg-red-500/10", texto: "text-red-700 dark:text-red-400" },
];

export function faixaRisco(p: number) {
  return FAIXAS.find((f) => p < f.ate)!;
}

// Cor do mapa base: acidentes por 10 km por ano (mesma escala para BRs e rodovias estaduais)
export const FAIXAS_HISTORICO = [
  { ate: 10, cor: "#86efac", rotulo: "até 10" },
  { ate: 30, cor: "#fde047", rotulo: "10–30" },
  { ate: 70, cor: "#fb923c", rotulo: "30–70" },
  { ate: Infinity, cor: "#ef4444", rotulo: "70+" },
];

export function corHistorico(densidade: number) {
  return FAIXAS_HISTORICO.find((f) => densidade < f.ate)!.cor;
}

export function decimal(n: number) {
  return n.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
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

/** 45 → "45 min", 125 → "2 h 05" */
export function formatarDuracao(minutos: number) {
  const m = Math.round(minutos);
  if (m < 60) return `${m} min`;
  return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}`;
}

/** Leitura intuitiva de uma probabilidade pequena: 0,008 → "1 em 125" */
export function umEmN(p: number) {
  if (p <= 0) return null;
  if (p >= 0.5) return null;
  const n = Math.round(1 / p);
  return `1 em ${n.toLocaleString("pt-BR")}`;
}

export function faixaHistorico(densidade: number) {
  return FAIXAS_HISTORICO.find((f) => densidade < f.ate)!;
}
