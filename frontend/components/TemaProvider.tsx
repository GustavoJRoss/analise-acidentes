"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

export type PreferenciaTema = "claro" | "escuro" | "sistema";
type TemaEfetivo = "claro" | "escuro";

const CHAVE = "tema";

// Roda no <head> antes da primeira pintura: aplica a classe .dark sem a página piscar no tema errado
export const SCRIPT_TEMA = `(() => {
  try {
    const p = localStorage.getItem("${CHAVE}") || "sistema";
    const escuro = p === "escuro" || (p === "sistema" && matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", escuro);
  } catch (e) {}
})();`;

function lerPreferencia(): PreferenciaTema {
  try {
    const p = localStorage.getItem(CHAVE);
    return p === "claro" || p === "escuro" ? p : "sistema";
  } catch {
    return "sistema";
  }
}

const ContextoTema = createContext<{
  preferencia: PreferenciaTema;
  tema: TemaEfetivo;
  setPreferencia: (p: PreferenciaTema) => void;
}>({ preferencia: "sistema", tema: "claro", setPreferencia: () => {} });

export function TemaProvider({ children }: { children: React.ReactNode }) {
  const [preferencia, setPref] = useState<PreferenciaTema>("sistema");
  const [sistemaEscuro, setSistemaEscuro] = useState(false);
  // até ler a preferência salva, quem manda é o SCRIPT_TEMA (senão o primeiro efeito desfaria o tema escuro)
  const [pronto, setPronto] = useState(false);

  useEffect(() => {
    setPref(lerPreferencia());
    setPronto(true);
    const consulta = matchMedia("(prefers-color-scheme: dark)");
    setSistemaEscuro(consulta.matches);
    const mudar = (e: MediaQueryListEvent) => setSistemaEscuro(e.matches);
    consulta.addEventListener("change", mudar);
    return () => consulta.removeEventListener("change", mudar);
  }, []);

  const tema: TemaEfetivo = preferencia === "sistema" ? (sistemaEscuro ? "escuro" : "claro") : preferencia;

  useEffect(() => {
    if (pronto) document.documentElement.classList.toggle("dark", tema === "escuro");
  }, [tema, pronto]);

  const setPreferencia = useCallback((p: PreferenciaTema) => {
    setPref(p);
    try {
      localStorage.setItem(CHAVE, p);
    } catch {
      // sem armazenamento (aba privada): o tema vale só nesta visita
    }
  }, []);

  return <ContextoTema.Provider value={{ preferencia, tema, setPreferencia }}>{children}</ContextoTema.Provider>;
}

export function useTema() {
  return useContext(ContextoTema);
}
