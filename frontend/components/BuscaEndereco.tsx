"use client";

import { useEffect, useId, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { Lugar } from "@/lib/tipos";

interface Props {
  rotulo: string;
  corMarcador: string;
  valor: Lugar | null;
  onEscolher: (lugar: Lugar | null) => void;
  placeholder: string;
}

function nomeCurto(nome: string) {
  return nome.split(",").slice(0, 3).join(",");
}

export default function BuscaEndereco({ rotulo, corMarcador, valor, onEscolher, placeholder }: Props) {
  const [texto, setTexto] = useState(valor ? nomeCurto(valor.nome) : "");
  const [resultados, setResultados] = useState<Lugar[]>([]);
  const [aberto, setAberto] = useState(false);
  const [ativo, setAtivo] = useState(0);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const editando = useRef(false);
  const idLista = useId();

  // valor definido de fora (clique no mapa ou "inverter")
  useEffect(() => {
    if (!editando.current) setTexto(valor ? nomeCurto(valor.nome) : "");
  }, [valor]);

  useEffect(() => {
    const q = texto.trim();
    if (!editando.current || q.length < 3) {
      setResultados([]);
      return;
    }
    const controle = new AbortController();
    const timer = setTimeout(async () => {
      setCarregando(true);
      setErro(null);
      try {
        const lugares = await api.buscar(q, controle.signal);
        setResultados(lugares);
        setAtivo(0);
        setAberto(true);
      } catch (e) {
        if (!controle.signal.aborted) setErro((e as Error).message);
      } finally {
        if (!controle.signal.aborted) setCarregando(false);
      }
    }, 450);
    return () => {
      clearTimeout(timer);
      controle.abort();
    };
  }, [texto]);

  function escolher(lugar: Lugar) {
    editando.current = false;
    setTexto(nomeCurto(lugar.nome));
    setAberto(false);
    onEscolher(lugar);
  }

  function aoTeclar(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!aberto || resultados.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setAtivo((a) => (a + 1) % resultados.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setAtivo((a) => (a - 1 + resultados.length) % resultados.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      escolher(resultados[ativo]);
    } else if (e.key === "Escape") {
      setAberto(false);
    }
  }

  return (
    <div className="relative">
      <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100">
        <span className="h-3 w-3 shrink-0 rounded-full ring-2 ring-white" style={{ background: corMarcador }} />
        <span className="sr-only">{rotulo}</span>
        <input
          className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400"
          placeholder={placeholder}
          value={texto}
          role="combobox"
          aria-expanded={aberto}
          aria-controls={idLista}
          aria-autocomplete="list"
          onChange={(e) => {
            editando.current = true;
            setTexto(e.target.value);
          }}
          onFocus={() => resultados.length > 0 && setAberto(true)}
          onBlur={() => setTimeout(() => setAberto(false), 150)}
          onKeyDown={aoTeclar}
        />
        {carregando && <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-blue-600" />}
        {!carregando && texto && (
          <button
            type="button"
            aria-label={`Limpar ${rotulo.toLowerCase()}`}
            className="rounded-full px-1 text-slate-400 hover:text-slate-700"
            onClick={() => {
              editando.current = false;
              setTexto("");
              setResultados([]);
              onEscolher(null);
            }}
          >
            ✕
          </button>
        )}
      </label>
      {erro && <p className="mt-1 text-xs text-red-600">{erro}</p>}
      {aberto && (
        <ul id={idLista} role="listbox"
          className="absolute z-[1000] mt-1 max-h-64 w-full overflow-auto rounded-xl border border-slate-200 bg-white py-1 shadow-lg">
          {resultados.length === 0 && <li className="px-3 py-2 text-sm text-slate-500">Nada encontrado em SC</li>}
          {resultados.map((r, i) => (
            <li key={`${r.lat},${r.lon}`} role="option" aria-selected={i === ativo}
              className={`cursor-pointer px-3 py-2 text-sm ${i === ativo ? "bg-blue-50" : "hover:bg-slate-50"}`}
              onMouseDown={(e) => {
                e.preventDefault();
                escolher(r);
              }}
              onMouseEnter={() => setAtivo(i)}>
              <div className="font-medium text-slate-800">{r.nome.split(",")[0]}</div>
              <div className="truncate text-xs text-slate-500">{r.nome.split(",").slice(1, 4).join(",")}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
