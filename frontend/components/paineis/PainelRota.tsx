"use client";

import { ArrowUpDown, History, X } from "lucide-react";

import { ESTILO } from "./base";
import BuscaEndereco from "@/components/BuscaEndereco";
import { useDados } from "@/lib/contexto";
import { formatarDuracao } from "@/lib/formato";
import type { Lugar, Rota } from "@/lib/tipos";

export type RotaRecente = { origem: Lugar; destino: Lugar };

const nomeCurto = (l: Lugar) => l.nome.split(",")[0];

export default function PainelRota({
  origem, destino, onOrigem, onDestino, onInverter, onLimpar, recentes, onEscolherRecente, onLimparRecentes, rota, carregando, erro,
}: {
  origem: Lugar | null;
  destino: Lugar | null;
  onOrigem: (l: Lugar | null) => void;
  onDestino: (l: Lugar | null) => void;
  onInverter: () => void;
  onLimpar: () => void;
  recentes: RotaRecente[];
  onEscolherRecente: (r: RotaRecente) => void;
  onLimparRecentes: () => void;
  rota: Rota | null;
  carregando: boolean;
  erro: string | null;
}) {
  const { porId } = useDados();
  const redes = (rota?.trechos ?? []).map((t) => porId[t.trecho_id]?.properties.rede);
  const nBr = redes.filter((r) => r === "br").length;
  const nSc = redes.filter((r) => r === "sc").length;
  const partes = [nBr > 0 && `${nBr} ${nBr === 1 ? "trecho" : "trechos"} de BR`, nSc > 0 && `${nSc} de rodovias estaduais`].filter(Boolean);
  const outrasRecentes = recentes.filter((r) => !(origem && destino && r.origem.nome === origem.nome && r.destino.nome === destino.nome));

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1 space-y-2">
          <BuscaEndereco rotulo="Origem" corMarcador="#16a34a" valor={origem} onEscolher={onOrigem}
            placeholder="De onde? (cidade ou endereço)" />
          <BuscaEndereco rotulo="Destino" corMarcador="#dc2626" valor={destino} onEscolher={onDestino}
            placeholder="Para onde?" />
        </div>
        <button type="button" onClick={onInverter} aria-label="Inverter origem e destino" title="Inverter"
          disabled={!origem && !destino}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-borda bg-superficie text-texto-suave shadow-sm transition hover:bg-superficie-2 hover:text-texto disabled:opacity-40">
          <ArrowUpDown size={16} aria-hidden />
        </button>
      </div>

      <div className="flex items-start justify-between gap-2">
        <p className="text-xs text-texto-fraco">
          Também dá para clicar no mapa (1º clique: origem, 2º: destino) e arrastar os marcadores para ajustar.
        </p>
        {(origem || destino) && (
          <button type="button" onClick={onLimpar} className={`shrink-0 ${ESTILO.botaoSecundario}`}>
            <X size={12} aria-hidden /> Limpar
          </button>
        )}
      </div>

      {outrasRecentes.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <History size={13} aria-label="Viagens recentes" className="text-texto-fraco" />
          {outrasRecentes.map((r) => (
            <button key={`${r.origem.nome}|${r.destino.nome}`} type="button" onClick={() => onEscolherRecente(r)}
              className={`max-w-full truncate ${ESTILO.chip(false)}`}>
              {nomeCurto(r.origem)} → {nomeCurto(r.destino)}
            </button>
          ))}
          <button type="button" onClick={onLimparRecentes} className="text-[11px] text-texto-fraco hover:text-texto">limpar</button>
        </div>
      )}

      {carregando && (
        <p className="flex items-center gap-2 text-sm text-texto-suave">
          <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-borda-forte border-t-primaria" />
          Traçando rota…
        </p>
      )}
      {erro && <p className={ESTILO.erro}>{erro}</p>}
      {rota && !carregando && (
        <div className={`${ESTILO.caixa} text-sm text-texto-suave`}>
          <b className="text-texto">{rota.distancia_km.toLocaleString("pt-BR")} km</b> · cerca de{" "}
          <b className="text-texto">{formatarDuracao(rota.duracao_min)}</b> ·{" "}
          {partes.length > 0
            ? `passa por ${partes.join(" e ")}`
            : "não passa por rodovias cobertas pelos modelos"}
        </div>
      )}
    </div>
  );
}
