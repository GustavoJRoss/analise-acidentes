"use client";

// Peças comuns da barra lateral. As cores vêm dos tokens de tema (globals.css), nunca de slate/white fixos.

import { ChevronDown } from "lucide-react";
import { useId, useRef, useState } from "react";

export const ESTILO = {
  chip: (ativo: boolean) => `rounded-full border px-2.5 py-1 text-xs transition ${
    ativo ? "border-primaria bg-primaria-suave text-primaria-texto" : "border-borda bg-superficie text-texto-suave hover:bg-superficie-2"
  }`,
  caixa: "rounded-xl border border-borda bg-superficie-2 p-3",
  campo: "rounded-xl border border-borda bg-superficie px-3 py-2 text-sm text-texto outline-none focus-within:border-primaria focus-within:ring-2 focus-within:ring-primaria/20 focus:border-primaria",
  aviso: "rounded-xl bg-amber-50 p-2.5 text-xs text-amber-900 dark:bg-amber-500/10 dark:text-amber-200",
  info: "rounded-xl bg-sky-50 p-2.5 text-xs text-sky-900 dark:bg-sky-500/10 dark:text-sky-200",
  erro: "rounded-xl bg-red-50 p-2.5 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300",
  selo: "rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  rotuloSecao: "text-xs font-medium uppercase tracking-wide text-texto-fraco",
  botaoSecundario: "inline-flex items-center justify-center gap-1.5 rounded-lg border border-borda bg-superficie px-2.5 py-1.5 text-xs font-medium text-texto-suave transition hover:bg-superficie-2 hover:text-texto disabled:cursor-not-allowed disabled:opacity-50",
};

/**
 * Seção numerada da barra lateral. Recolhível: quando fechada mostra o `resumo` (ex.: "Sábado · Noite").
 * No celular só fica aberta de início se `abertoNoCelular`; no desktop todas começam abertas.
 */
export function Passo({ numero, titulo, children, acao, resumo, abertoNoCelular = false }: {
  numero: number;
  titulo: string;
  children: React.ReactNode;
  acao?: React.ReactNode;
  resumo?: React.ReactNode;
  abertoNoCelular?: boolean;
}) {
  // null = estado inicial definido só por CSS (sem piscar na hidratação); depois do 1º clique vira booleano
  const [aberto, setAberto] = useState<boolean | null>(null);
  const idConteudo = useId();

  function alternar() {
    const atual = aberto ?? (abertoNoCelular || window.matchMedia("(min-width: 768px)").matches);
    setAberto(!atual);
  }

  const classeConteudo = aberto === null ? (abertoNoCelular ? "" : "hidden md:block") : aberto ? "" : "hidden";
  const classeResumo = aberto === null ? (abertoNoCelular ? "hidden" : "md:hidden") : aberto ? "hidden" : "";
  const classeSeta = aberto === null ? (abertoNoCelular ? "rotate-180" : "md:rotate-180") : aberto ? "rotate-180" : "";
  const expandido = aberto ?? abertoNoCelular;

  return (
    <section className="border-b border-borda px-5 py-3.5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-texto">
        <button type="button" onClick={alternar} aria-expanded={expandido} aria-controls={idConteudo}
          className="-mx-1 flex min-w-0 flex-1 items-center gap-2 rounded-lg px-1 py-0.5 text-left">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-texto text-xs text-superficie">{numero}</span>
          <span className="shrink-0">{titulo}</span>
          {resumo && (
            <span className={`min-w-0 flex-1 truncate text-xs font-normal text-texto-fraco ${classeResumo}`}>· {resumo}</span>
          )}
          <span className="flex-1" />
          <ChevronDown size={16} aria-hidden className={`shrink-0 text-texto-fraco transition-transform ${classeSeta}`} />
        </button>
        {acao}
      </h2>
      <div id={idConteudo} className={`mt-3 ${classeConteudo}`}>{children}</div>
    </section>
  );
}

export function Segmentado<T extends string>({ opcoes, valor, onMudar, rotulo, colunas }: {
  opcoes: { id: T; conteudo: React.ReactNode; dica?: string; desativado?: boolean }[];
  valor: T;
  onMudar: (v: T) => void;
  rotulo: string;
  colunas: number;
}) {
  const grupo = useRef<HTMLDivElement>(null);

  // radiogroup acessível: setas mudam a opção e levam o foco junto
  function aoTeclar(e: React.KeyboardEvent) {
    const passo = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!passo) return;
    e.preventDefault();
    const habilitadas = opcoes.filter((o) => !o.desativado);
    const i = habilitadas.findIndex((o) => o.id === valor);
    const proxima = habilitadas[(i + passo + habilitadas.length) % habilitadas.length];
    if (!proxima) return;
    onMudar(proxima.id);
    grupo.current?.querySelector<HTMLButtonElement>(`[data-id="${proxima.id}"]`)?.focus();
  }

  return (
    <div ref={grupo} role="radiogroup" aria-label={rotulo} className="grid gap-1.5" onKeyDown={aoTeclar}
      style={{ gridTemplateColumns: `repeat(${colunas}, minmax(0, 1fr))` }}>
      {opcoes.map((o, i) => (
        <button key={o.id} data-id={o.id} type="button" role="radio" aria-checked={valor === o.id} title={o.dica}
          tabIndex={valor === o.id || (i === 0 && !opcoes.some((x) => x.id === valor)) ? 0 : -1}
          disabled={o.desativado} onClick={() => onMudar(o.id)}
          className={`rounded-xl border px-2 py-2 text-center text-xs transition disabled:cursor-not-allowed disabled:opacity-40 ${
            valor === o.id
              ? "border-primaria bg-primaria-suave font-semibold text-primaria-texto ring-1 ring-primaria"
              : "border-borda bg-superficie text-texto-suave hover:border-borda-forte hover:bg-superficie-2"
          }`}>
          {o.conteudo}
        </button>
      ))}
    </div>
  );
}
