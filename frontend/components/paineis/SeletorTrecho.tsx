"use client";

import { useId, useMemo, useState } from "react";

import { ESTILO } from "./base";
import { type FiltroDeRede, passaNoFiltro } from "./FiltroRede";
import { propsDe, useDados } from "@/lib/contexto";
import { capitalizar, corHistorico, decimal } from "@/lib/formato";
import { useNavegacaoLista } from "@/lib/hooks";
import { semAcentos } from "@/lib/texto";
import type { PropsTrecho } from "@/lib/tipos";

export function rotuloCompleto(t: PropsTrecho) {
  return t.rede === "br" ? `${t.rotulo} · ${capitalizar(t.municipio)}` : t.rotulo;
}

export function CartaoTrecho({ trecho }: { trecho: PropsTrecho }) {
  return (
    <div className={ESTILO.caixa}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-semibold text-texto">{trecho.rotulo}</div>
          <div className="text-sm text-texto-suave">
            {trecho.rede === "br"
              ? `${capitalizar(trecho.municipio)} · rodovia federal`
              : `Rodovia estadual · ${decimal(trecho.comprimento_km)} km dentro do município`}
          </div>
        </div>
        <span className="mt-1 h-3 w-3 shrink-0 rounded-full" style={{ background: corHistorico(trecho.densidade) }} />
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-texto-suave">
        <span><b className="text-texto">{decimal(trecho.acidentes_ano)}</b> acidentes por ano</span>
        <span><b className="text-texto">{trecho.mortos}</b> mortes no período</span>
        <span className="text-texto-fraco">{trecho.periodo_dados}</span>
      </div>
    </div>
  );
}

export default function SeletorTrecho({ filtro, selecionado, onSelecionar }: {
  filtro: FiltroDeRede;
  selecionado: string | null;
  onSelecionar: (id: string) => void;
}) {
  const dados = useDados();
  const [busca, setBusca] = useState("");
  const trecho = propsDe(dados, selecionado);

  const daRede = useMemo(
    () => (dados.trechos?.features ?? []).map((f) => f.properties).filter((t) => passaNoFiltro(t.rede, filtro)),
    [dados.trechos, filtro],
  );
  const maisPerigosos = useMemo(() => [...daRede].sort((a, b) => b.densidade - a.densidade).slice(0, 6), [daRede]);
  const resultados = useMemo(() => {
    const q = semAcentos(busca.trim().toLowerCase());
    if (q.length < 2) return [];
    return daRede.filter((t) => semAcentos(`${t.rotulo} ${t.municipio}`.toLowerCase()).includes(q)).slice(0, 8);
  }, [busca, daRede]);
  const idLista = useId();
  const escolher = (t: PropsTrecho) => {
    onSelecionar(t.trecho_id);
    setBusca("");
    nav.setAberto(false);
  };
  const nav = useNavegacaoLista(resultados, escolher);
  const mostrarLista = nav.aberto && busca.trim().length >= 2;

  return (
    <div className="space-y-3">
      {trecho ? <CartaoTrecho trecho={trecho} /> : (
        <p className="rounded-xl border border-dashed border-borda-forte p-3 text-sm text-texto-suave">
          Clique numa rodovia no mapa, busque pelo nome ou município, ou escolha um dos trechos abaixo.
        </p>
      )}

      <div className="relative">
        <input type="search" value={busca} aria-label="Buscar trecho"
          role="combobox" aria-expanded={mostrarLista} aria-controls={idLista} aria-autocomplete="list"
          aria-activedescendant={mostrarLista && resultados[nav.ativo] ? `${idLista}-${nav.ativo}` : undefined}
          onChange={(e) => { setBusca(e.target.value); nav.setAberto(true); }}
          onFocus={() => nav.setAberto(true)}
          onBlur={() => setTimeout(() => nav.setAberto(false), 150)}
          onKeyDown={nav.aoTeclar}
          placeholder="Buscar: BR-101, SC-401, Joinville…" className={`w-full ${ESTILO.campo}`} />
        {mostrarLista && (
          <ul id={idLista} role="listbox"
            className="absolute inset-x-0 top-full z-20 mt-1 max-h-64 overflow-auto rounded-xl border border-borda bg-superficie p-1 shadow-lg">
            {resultados.length === 0 && <li className="px-2 py-2 text-sm text-texto-fraco">Nenhum trecho encontrado.</li>}
            {resultados.map((t, i) => (
              <li key={t.trecho_id} id={`${idLista}-${i}`} role="option" aria-selected={i === nav.ativo}
                onMouseDown={(e) => { e.preventDefault(); escolher(t); }}
                onMouseEnter={() => nav.setAtivo(i)}
                className={`flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-texto ${
                  i === nav.ativo ? "bg-primaria-suave" : "hover:bg-superficie-2"
                }`}>
                <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: corHistorico(t.densidade) }} />
                <span className="min-w-0 flex-1 truncate">{rotuloCompleto(t)}</span>
                <span className="shrink-0 text-xs text-texto-fraco">{decimal(t.acidentes_ano)}/ano</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <div className={`mb-1.5 ${ESTILO.rotuloSecao}`}>Mais acidentes por km</div>
        <div className="flex flex-wrap gap-1.5">
          {maisPerigosos.map((t) => (
            <button key={t.trecho_id} type="button" onClick={() => onSelecionar(t.trecho_id)}
              className={ESTILO.chip(selecionado === t.trecho_id)}>
              {rotuloCompleto(t)}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
