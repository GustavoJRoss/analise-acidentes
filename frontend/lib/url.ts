"use client";

import { useSearchParams } from "next/navigation";
import { useCallback } from "react";

/**
 * Atualiza a query string sem navegar (o Next 15 sincroniza replaceState com useSearchParams).
 * `null`/"" remove o parâmetro. As chaves que não foram passadas ficam como estão.
 */
export function atualizarUrl(mudancas: Record<string, string | null | undefined>) {
  const params = new URLSearchParams(window.location.search);
  for (const [k, v] of Object.entries(mudancas)) {
    if (v) params.set(k, v);
    else params.delete(k);
  }
  const busca = params.toString();
  if (busca === window.location.search.replace(/^\?/, "")) return;
  // estado null de propósito: o Next 15 só sincroniza o useSearchParams quando o state NÃO tem a marca interna
  // dele (__NA); repassar window.history.state fazia a URL mudar sem a tela reagir até dar refresh
  window.history.replaceState(null, "", busca ? `?${busca}` : window.location.pathname);
}

/** Estado guardado num parâmetro da URL (precisa de um <Suspense> acima, por causa do useSearchParams). */
export function useParametro<T extends string>(chave: string, padrao: T, validos?: readonly T[]) {
  const params = useSearchParams();
  const bruto = params.get(chave);
  const valor = (bruto !== null && (!validos || validos.includes(bruto as T)) ? bruto : padrao) as T;
  const setValor = useCallback(
    (v: T) => atualizarUrl({ [chave]: v === padrao ? null : v }),
    [chave, padrao],
  );
  return [valor, setValor] as const;
}

/** Lugar ↔ texto da URL: "-27.59,-48.55,Florianópolis" */
export function lugarParaUrl(l: { lat: number; lon: number; nome: string } | null) {
  return l ? `${l.lat.toFixed(5)},${l.lon.toFixed(5)},${l.nome}` : null;
}

export function lugarDaUrl(texto: string | null) {
  if (!texto) return null;
  const [lat, lon, ...nome] = texto.split(",");
  const la = Number(lat);
  const lo = Number(lon);
  if (!Number.isFinite(la) || !Number.isFinite(lo)) return null;
  return { lat: la, lon: lo, nome: nome.join(",") || `Ponto no mapa (${la.toFixed(4)}, ${lo.toFixed(4)})` };
}
