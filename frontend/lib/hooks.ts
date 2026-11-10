"use client";

import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { api } from "./api";
import { useCenario } from "./contexto";
import type { Periodo, Previsao } from "./tipos";

/** Recalcula a previsão sozinha (debounce de 300 ms) quando os trechos ou o cenário mudam. */
export function usePrevisao(trechoIds: string[]) {
  const { data, periodo, clima, climaPrevisto } = useCenario();
  const [previsao, setPrevisao] = useState<Previsao | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  // a lista muda de identidade a cada render: compara pelo conteúdo
  const chave = trechoIds.join(",");

  useEffect(() => {
    const ids = chave ? chave.split(",") : [];
    if (ids.length === 0) {
      setPrevisao(null);
      setErro(null);
      return;
    }
    const controle = new AbortController();
    const timer = setTimeout(() => {
      setCarregando(true);
      setErro(null);
      api.prever({
        trecho_ids: ids, data, periodo, clima,
        clima_personalizado: climaPrevisto
          ? { chuva_mm: climaPrevisto.chuva_mm, nebulosidade: climaPrevisto.nebulosidade, temperatura: climaPrevisto.temperatura }
          : null,
      }, controle.signal)
        .then(setPrevisao)
        .catch((e) => !controle.signal.aborted && setErro((e as Error).message))
        .finally(() => !controle.signal.aborted && setCarregando(false));
    }, 300);
    return () => {
      clearTimeout(timer);
      controle.abort();
    };
  }, [chave, data, periodo, clima, climaPrevisto]);

  // probabilidade de cada trecho no cenário, para colorir o mapa (só os que ainda estão selecionados)
  const probPorTrecho = useMemo(() => {
    const ids = new Set(chave ? chave.split(",") : []);
    return Object.fromEntries((previsao?.trechos ?? []).filter((t) => ids.has(t.trecho_id)).map((t) => [t.trecho_id, t.probabilidade]));
  }, [previsao, chave]);

  return { previsao, carregando, erro, probPorTrecho };
}

/** "Usar a previsão do tempo": busca o clima previsto no trecho de referência e o aplica ao cenário. */
export function usePrevisaoTempo(trechoIds: string[]) {
  const { data, periodo, setClima, setClimaPrevisto } = useCenario();
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const chave = trechoIds.join(",");

  useEffect(() => {
    setClimaPrevisto(null);
    setErro(null);
  }, [chave, setClimaPrevisto]);

  async function usar() {
    if (trechoIds.length === 0) return;
    setCarregando(true);
    setErro(null);
    try {
      // para uma rota ou rodovia inteira, usa o trecho do meio como referência do tempo
      const prev = await api.climaPrevisto(trechoIds[Math.floor(trechoIds.length / 2)], data, periodo);
      setClima(prev.categoria);
      setClimaPrevisto(prev);
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setCarregando(false);
    }
  }

  return { usar, carregando, erro };
}

const PERIODOS: Periodo[] = ["madrugada", "manha", "tarde", "noite"];

/**
 * Probabilidade nos 4 períodos do dia escolhido, para responder "qual o melhor horário?".
 * O período atual reaproveita a previsão principal (que pode usar a previsão do tempo); os outros usam a categoria de clima.
 */
export function useComparacaoPeriodos(trechoIds: string[], previsaoAtual: Previsao | null) {
  const { data, periodo, clima } = useCenario();
  const [outros, setOutros] = useState<Partial<Record<Periodo, number>>>({});
  const [carregando, setCarregando] = useState(false);
  const chave = trechoIds.join(",");

  useEffect(() => {
    setOutros({});
    const ids = chave ? chave.split(",") : [];
    if (ids.length === 0) return;
    const controle = new AbortController();
    const timer = setTimeout(() => {
      setCarregando(true);
      Promise.all(PERIODOS.filter((p) => p !== periodo).map((p) =>
        api.prever({ trecho_ids: ids, data, periodo: p, clima }, controle.signal).then((r) => [p, r.probabilidade] as const)))
        .then((pares) => setOutros(Object.fromEntries(pares)))
        .catch(() => {})
        .finally(() => !controle.signal.aborted && setCarregando(false));
    }, 500);
    return () => {
      clearTimeout(timer);
      controle.abort();
    };
  }, [chave, data, periodo, clima]);

  const valores: Partial<Record<Periodo, number>> = previsaoAtual ? { ...outros, [periodo]: previsaoAtual.probabilidade } : outros;
  const completo = PERIODOS.every((p) => valores[p] !== undefined);
  return { valores, completo, carregando };
}

/** Lista curta guardada no navegador (recentes). Sem armazenamento disponível, fica só na memória. */
export function useRecentes<T>(chave: string, igual: (a: T, b: T) => boolean, maximo = 5) {
  const [itens, setItens] = useState<T[]>([]);

  useEffect(() => {
    try {
      const salvo = localStorage.getItem(chave);
      if (salvo) setItens(JSON.parse(salvo));
    } catch {
      // sem localStorage (aba privada) ou JSON inválido: começa vazio
    }
  }, [chave]);

  const adicionar = useCallback((item: T) => {
    setItens((atual) => {
      const novo = [item, ...atual.filter((x) => !igual(x, item))].slice(0, maximo);
      try {
        localStorage.setItem(chave, JSON.stringify(novo));
      } catch {
        // ignora: os recentes valem só nesta visita
      }
      return novo;
    });
  }, [chave, igual, maximo]);

  const limpar = useCallback(() => {
    setItens([]);
    try {
      localStorage.removeItem(chave);
    } catch {
      // nada a fazer
    }
  }, [chave]);

  return { itens, adicionar, limpar };
}

/** true quando a media query casa; no servidor (e na primeira pintura) assume false. */
export function useMediaQuery(consulta: string) {
  return useSyncExternalStore(
    (avisar) => {
      const mql = window.matchMedia(consulta);
      mql.addEventListener("change", avisar);
      return () => mql.removeEventListener("change", avisar);
    },
    () => window.matchMedia(consulta).matches,
    () => false,
  );
}

/** Setas, Enter e Esc numa lista de sugestões (combobox). */
export function useNavegacaoLista<T>(itens: T[], onEscolher: (item: T) => void) {
  const [ativo, setAtivo] = useState(0);
  const [aberto, setAberto] = useState(false);

  useEffect(() => setAtivo(0), [itens]);

  function aoTeclar(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      setAberto(false);
      return;
    }
    if (!aberto || itens.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setAtivo((a) => (a + 1) % itens.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setAtivo((a) => (a - 1 + itens.length) % itens.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      onEscolher(itens[Math.min(ativo, itens.length - 1)]);
    }
  }

  return { ativo, setAtivo, aberto, setAberto, aoTeclar };
}
