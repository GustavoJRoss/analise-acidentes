"use client";

import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api } from "./api";
import { isoLocal, periodoAtual } from "./formato";
import { atualizarUrl } from "./url";
import { agruparPorRodovia, type Rodovia } from "./rodovias";
import type { CategoriaClima, ClimaPrevisto, Metricas, Opcoes, Periodo, PropsTrecho, TrechosGeoJSON } from "./tipos";

// ---- dados do backend: carregados uma vez e compartilhados por todas as páginas -------------------
interface Dados {
  trechos: TrechosGeoJSON | null;
  opcoes: Opcoes | null;
  metricas: Metricas | null;
  erro: string | null;
  recarregar: () => void;
  porId: Record<string, TrechosGeoJSON["features"][number]>;
  rodovias: Rodovia[];
  temEstaduais: boolean;
}

const ContextoDados = createContext<Dados | null>(null);

export function DadosProvider({ children }: { children: React.ReactNode }) {
  const [trechos, setTrechos] = useState<TrechosGeoJSON | null>(null);
  const [opcoes, setOpcoes] = useState<Opcoes | null>(null);
  const [metricas, setMetricas] = useState<Metricas | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [tentativa, setTentativa] = useState(0);
  const recarregar = useCallback(() => setTentativa((t) => t + 1), []);

  useEffect(() => {
    setErro(null);
    Promise.all([api.trechos(), api.opcoes(), api.modelo()])
      .then(([t, o, m]) => {
        setTrechos(t);
        setOpcoes(o);
        setMetricas(m);
      })
      .catch(() => setErro("Não foi possível carregar os dados do servidor. Confira se o backend está rodando e tente de novo."));
  }, [tentativa]);

  const valor = useMemo<Dados>(() => {
    const features = trechos?.features ?? [];
    return {
      trechos, opcoes, metricas, erro, recarregar,
      porId: Object.fromEntries(features.map((f) => [f.properties.trecho_id, f])),
      rodovias: agruparPorRodovia(features.map((f) => f.properties)),
      temEstaduais: features.some((f) => f.properties.rede === "sc"),
    };
  }, [trechos, opcoes, metricas, erro, recarregar]);

  return <ContextoDados.Provider value={valor}>{children}</ContextoDados.Provider>;
}

export function useDados() {
  const dados = useContext(ContextoDados);
  if (!dados) throw new Error("useDados fora do DadosProvider");
  return dados;
}

export function propsDe(dados: Dados, id: string | null): PropsTrecho | null {
  return id ? dados.porId[id]?.properties ?? null : null;
}

// ---- cenário (quando e com que tempo): o mesmo no mapa de risco e na viagem ----------------------
interface Cenario {
  data: string;
  setData: (d: string) => void;
  periodo: Periodo;
  setPeriodo: (p: Periodo) => void;
  clima: CategoriaClima;
  setClima: (c: CategoriaClima) => void;
  climaPrevisto: ClimaPrevisto | null;
  setClimaPrevisto: (c: ClimaPrevisto | null) => void;
}

const ContextoCenario = createContext<Cenario | null>(null);

const PERIODOS: Periodo[] = ["madrugada", "manha", "tarde", "noite"];
const CLIMAS: CategoriaClima[] = ["ceu_claro", "nublado", "chuva", "chuva_forte"];
// só as páginas com mapa levam o cenário na URL (?data=…&periodo=…&clima=…)
const PAGINAS_COM_CENARIO = ["/", "/viagem"];

export function CenarioProvider({ children }: { children: React.ReactNode }) {
  const [data, setData] = useState(() => isoLocal(new Date()));
  const [periodo, setPeriodo] = useState<Periodo>(() => periodoAtual());
  const [clima, setClima] = useState<CategoriaClima>("ceu_claro");
  const [climaPrevisto, setClimaPrevisto] = useState<ClimaPrevisto | null>(null);
  const [lidoDaUrl, setLidoDaUrl] = useState(false);
  const caminho = usePathname();

  // um link compartilhado abre com o mesmo cenário de quem enviou
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const d = p.get("data");
    if (d && /^\d{4}-\d{2}-\d{2}$/.test(d)) setData(d);
    const per = p.get("periodo") as Periodo | null;
    if (per && PERIODOS.includes(per)) setPeriodo(per);
    const c = p.get("clima") as CategoriaClima | null;
    if (c && CLIMAS.includes(c)) setClima(c);
    setLidoDaUrl(true);
  }, []);

  useEffect(() => {
    if (lidoDaUrl && PAGINAS_COM_CENARIO.includes(caminho)) atualizarUrl({ data, periodo, clima });
  }, [lidoDaUrl, caminho, data, periodo, clima]);

  // a previsão do tempo vale para um dia e período: mudou, volta ao clima manual
  useEffect(() => setClimaPrevisto(null), [data, periodo]);

  const valor = useMemo(() => ({
    data, setData, periodo, setPeriodo, climaPrevisto, setClimaPrevisto,
    clima, setClima: (c: CategoriaClima) => {
      setClima(c);
      setClimaPrevisto(null);
    },
  }), [data, periodo, clima, climaPrevisto]);

  return <ContextoCenario.Provider value={valor}>{children}</ContextoCenario.Provider>;
}

export function useCenario() {
  const cenario = useContext(ContextoCenario);
  if (!cenario) throw new Error("useCenario fora do CenarioProvider");
  return cenario;
}
