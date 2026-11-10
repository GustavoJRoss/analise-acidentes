"use client";

import { useEffect, useId, useRef, useState } from "react";

import { X } from "lucide-react";

import { api } from "@/lib/api";
import { useNavegacaoLista } from "@/lib/hooks";
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
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const editando = useRef(false);
  const idLista = useId();
  const { ativo, setAtivo, aberto, setAberto, aoTeclar } = useNavegacaoLista(resultados, escolher);

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
  }, [texto, setAberto]);

  function escolher(lugar: Lugar) {
    editando.current = false;
    setTexto(nomeCurto(lugar.nome));
    setAberto(false);
    onEscolher(lugar);
  }

  return (
    <div className="relative">
      <label className="flex items-center gap-2 rounded-xl border border-borda bg-superficie px-3 py-2 focus-within:border-primaria focus-within:ring-2 focus-within:ring-primaria/20">
        <span className="h-3 w-3 shrink-0 rounded-full ring-2 ring-superficie" style={{ background: corMarcador }} />
        <span className="sr-only">{rotulo}</span>
        <input
          className="min-w-0 flex-1 bg-transparent text-sm text-texto outline-none placeholder:text-texto-fraco"
          placeholder={placeholder}
          value={texto}
          role="combobox"
          aria-expanded={aberto}
          aria-controls={idLista}
          aria-autocomplete="list"
          aria-activedescendant={aberto && resultados[ativo] ? `${idLista}-${ativo}` : undefined}
          onChange={(e) => {
            editando.current = true;
            setTexto(e.target.value);
          }}
          onFocus={() => resultados.length > 0 && setAberto(true)}
          onBlur={() => setTimeout(() => setAberto(false), 150)}
          onKeyDown={aoTeclar}
        />
        {carregando && <span className="h-4 w-4 animate-spin rounded-full border-2 border-borda-forte border-t-primaria" />}
        {!carregando && texto && (
          <button
            type="button"
            aria-label={`Limpar ${rotulo.toLowerCase()}`}
            className="rounded-full p-0.5 text-texto-fraco hover:bg-superficie-2 hover:text-texto"
            onClick={() => {
              editando.current = false;
              setTexto("");
              setResultados([]);
              onEscolher(null);
            }}
          >
            <X size={14} aria-hidden />
          </button>
        )}
      </label>
      {erro && <p className="mt-1 text-xs text-red-600 dark:text-red-400">{erro}</p>}
      {aberto && (
        <ul id={idLista} role="listbox"
          className="absolute z-[1000] mt-1 max-h-64 w-full overflow-auto rounded-xl border border-borda bg-superficie py-1 shadow-lg">
          {resultados.length === 0 && <li className="px-3 py-2 text-sm text-texto-fraco">Nada encontrado em SC</li>}
          {resultados.map((r, i) => (
            <li key={`${r.lat},${r.lon}`} id={`${idLista}-${i}`} role="option" aria-selected={i === ativo}
              className={`cursor-pointer px-3 py-2 text-sm ${i === ativo ? "bg-primaria-suave" : "hover:bg-superficie-2"}`}
              onMouseDown={(e) => {
                e.preventDefault();
                escolher(r);
              }}
              onMouseEnter={() => setAtivo(i)}>
              <div className="font-medium text-texto">{r.nome.split(",")[0]}</div>
              <div className="truncate text-xs text-texto-fraco">{r.nome.split(",").slice(1, 4).join(",")}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
