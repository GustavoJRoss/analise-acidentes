"use client";

import { BarChart3, Info, Map as IconeMapa, Monitor, Moon, Navigation, Sun, TrafficCone } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { type PreferenciaTema, useTema } from "./TemaProvider";

const PAGINAS = [
  { href: "/", rotulo: "Mapa de risco", curto: "Mapa", Icone: IconeMapa },
  { href: "/viagem", rotulo: "Planejar viagem", curto: "Viagem", Icone: Navigation },
  { href: "/rankings", rotulo: "Rankings", curto: "Rankings", Icone: BarChart3 },
  { href: "/sobre", rotulo: "Sobre os dados", curto: "Sobre", Icone: Info },
];

const TEMAS: { id: PreferenciaTema; Icone: typeof Sun; rotulo: string }[] = [
  { id: "claro", Icone: Sun, rotulo: "Tema claro" },
  { id: "escuro", Icone: Moon, rotulo: "Tema escuro" },
  { id: "sistema", Icone: Monitor, rotulo: "Seguir o sistema" },
];

function paginaAtiva(caminho: string, href: string) {
  return href === "/" ? caminho === "/" : caminho.startsWith(href);
}

function SeletorTema() {
  const { preferencia, setPreferencia } = useTema();
  return (
    <div className="flex shrink-0 rounded-full border border-borda bg-superficie-2 p-0.5" role="radiogroup" aria-label="Tema">
      {TEMAS.map(({ id, Icone, rotulo }) => (
        <button key={id} type="button" role="radio" aria-checked={preferencia === id} title={rotulo}
          aria-label={rotulo} onClick={() => setPreferencia(id)}
          className={`flex h-7 w-7 items-center justify-center rounded-full transition ${
            preferencia === id ? "bg-superficie text-texto shadow-sm" : "text-texto-fraco hover:text-texto"
          }`}>
          <Icone size={14} aria-hidden />
        </button>
      ))}
    </div>
  );
}

export default function Header() {
  const caminho = usePathname();
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-borda bg-superficie px-3 md:gap-6 md:px-5">
      <Link href="/" className="flex shrink-0 items-center gap-2 font-bold tracking-tight text-texto">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primaria text-superficie">
          <TrafficCone size={18} aria-hidden />
        </span>
        <span className="leading-tight">
          Risco nas rodovias<span className="block text-[11px] font-medium text-texto-fraco">Santa Catarina</span>
        </span>
      </Link>
      <nav aria-label="Páginas" className="hidden min-w-0 flex-1 gap-1 md:flex">
        {PAGINAS.map(({ href, rotulo, Icone }) => {
          const ativa = paginaAtiva(caminho, href);
          return (
            <Link key={href} href={href} aria-current={ativa ? "page" : undefined}
              className={`flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium transition ${
                ativa ? "bg-primaria-suave text-primaria-texto" : "text-texto-suave hover:bg-superficie-2 hover:text-texto"
              }`}>
              <Icone size={16} aria-hidden />
              {rotulo}
            </Link>
          );
        })}
      </nav>
      <span className="flex-1 md:hidden" />
      <SeletorTema />
    </header>
  );
}

/** Navegação principal no celular: barra fixa embaixo, ao alcance do polegar. */
export function BarraAbas() {
  const caminho = usePathname();
  return (
    <nav aria-label="Páginas" className="grid shrink-0 grid-cols-4 border-t border-borda bg-superficie pb-[env(safe-area-inset-bottom)] md:hidden">
      {PAGINAS.map(({ href, curto, Icone }) => {
        const ativa = paginaAtiva(caminho, href);
        return (
          <Link key={href} href={href} aria-current={ativa ? "page" : undefined}
            className={`flex flex-col items-center gap-0.5 py-2 text-[11px] font-medium transition ${
              ativa ? "text-primaria" : "text-texto-fraco"
            }`}>
            <Icone size={20} aria-hidden strokeWidth={ativa ? 2.4 : 2} />
            {curto}
          </Link>
        );
      })}
    </nav>
  );
}
