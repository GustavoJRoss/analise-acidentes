"use client";

import { Route } from "lucide-react";

import { Segmentado } from "./base";
import { useDados } from "@/lib/contexto";
import type { Rede } from "@/lib/tipos";

export type FiltroDeRede = "todas" | Rede;

export function passaNoFiltro(rede: Rede, filtro: FiltroDeRede) {
  return filtro === "todas" || filtro === rede;
}

export default function FiltroRede({ valor, onMudar }: { valor: FiltroDeRede; onMudar: (f: FiltroDeRede) => void }) {
  const { temEstaduais } = useDados();
  return (
    <Segmentado<FiltroDeRede> rotulo="Rede de rodovias" colunas={3} valor={valor} onMudar={onMudar}
      opcoes={[
        { id: "todas", conteudo: <><Route size={14} aria-hidden className="mx-auto" /><div className="mt-1">Todas</div></> },
        { id: "br", conteudo: <><span className="mx-auto my-1.5 block h-0.5 w-6 rounded bg-current" /><div className="mt-1">Federais (BR)</div></> },
        {
          id: "sc", desativado: !temEstaduais,
          dica: temEstaduais ? undefined : "Rede estadual ainda não preparada no backend",
          conteudo: <><span className="mx-auto my-1.5 block w-6 border-t-2 border-dashed border-current" /><div className="mt-1">Estaduais (SC)</div></>,
        },
      ]} />
  );
}
