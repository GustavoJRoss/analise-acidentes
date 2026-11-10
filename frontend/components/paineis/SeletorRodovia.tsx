"use client";

import { useMemo, useState } from "react";

import { ESTILO } from "./base";
import { type FiltroDeRede, passaNoFiltro } from "./FiltroRede";
import { useDados } from "@/lib/contexto";
import { corHistorico, decimal } from "@/lib/formato";
import type { Rodovia } from "@/lib/rodovias";
import { semAcentos } from "@/lib/texto";

export function CartaoRodovia({ rodovia }: { rodovia: Rodovia }) {
  const cidades = rodovia.municipios;
  return (
    <div className={ESTILO.caixa}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-semibold text-texto">{rodovia.rodovia} inteira</div>
          <div className="text-sm text-texto-suave">
            {rodovia.rede === "br" ? "Rodovia federal" : "Rodovia estadual"} · {rodovia.trecho_ids.length} trechos ·{" "}
            {decimal(rodovia.extensao_km)} km com dados
          </div>
        </div>
        <span className="mt-1 h-3 w-3 shrink-0 rounded-full" style={{ background: corHistorico(rodovia.densidade) }} />
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-texto-suave">
        <span><b className="text-texto">{decimal(rodovia.acidentes_ano)}</b> acidentes por ano</span>
        <span><b className="text-texto">{decimal(rodovia.densidade)}</b> por 10 km/ano</span>
        <span><b className="text-texto">{rodovia.mortos}</b> mortes no período</span>
      </div>
      <p className="mt-1.5 text-xs text-texto-fraco">
        Passa por {cidades.slice(0, 4).join(", ")}{cidades.length > 4 ? ` e mais ${cidades.length - 4}` : ""}.
      </p>
    </div>
  );
}

export default function SeletorRodovia({ filtro, selecionada, onSelecionar }: {
  filtro: FiltroDeRede;
  selecionada: string | null;
  onSelecionar: (rodovia: string) => void;
}) {
  const { rodovias } = useDados();
  const [busca, setBusca] = useState("");
  const atual = rodovias.find((r) => r.rodovia === selecionada) ?? null;

  const lista = useMemo(() => {
    const q = semAcentos(busca.trim().toLowerCase());
    return rodovias.filter((r) => passaNoFiltro(r.rede, filtro)
      && (!q || semAcentos(`${r.rodovia} ${r.municipios.join(" ")}`.toLowerCase()).includes(q)));
  }, [rodovias, filtro, busca]);

  return (
    <div className="space-y-3">
      {atual ? <CartaoRodovia rodovia={atual} /> : (
        <p className="rounded-xl border border-dashed border-borda-forte p-3 text-sm text-texto-suave">
          Escolha uma rodovia para ver a chance de acidente em toda a extensão dela dentro de SC.
        </p>
      )}
      <input type="search" value={busca} onChange={(e) => setBusca(e.target.value)} aria-label="Buscar rodovia"
        placeholder="Buscar rodovia ou município…" className={`w-full ${ESTILO.campo}`} />
      <ul className="max-h-72 space-y-0.5 overflow-auto rounded-xl border border-borda p-1">
        {lista.map((r) => (
          <li key={r.rodovia}>
            <button type="button" onClick={() => onSelecionar(r.rodovia)} aria-pressed={r.rodovia === selecionada}
              className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm transition ${
                r.rodovia === selecionada ? "bg-primaria-suave text-primaria-texto" : "text-texto hover:bg-superficie-2"
              }`}>
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: corHistorico(r.densidade) }} />
              <span className="w-16 shrink-0 font-medium">{r.rodovia}</span>
              <span className="min-w-0 flex-1 truncate text-xs text-texto-fraco">
                {decimal(r.extensao_km)} km · {r.trecho_ids.length} trechos
              </span>
              <span className="shrink-0 text-xs tabular-nums text-texto-suave">{decimal(r.acidentes_ano)}/ano</span>
            </button>
          </li>
        ))}
        {lista.length === 0 && <li className="px-2 py-3 text-center text-xs text-texto-fraco">Nenhuma rodovia encontrada.</li>}
      </ul>
    </div>
  );
}
