"use client";

import { CalendarDays } from "lucide-react";

import { ESTILO, Passo, Segmentado } from "./base";
import { IconePeriodo } from "@/components/Icones";
import { useCenario, useDados } from "@/lib/contexto";
import { dataExtensa, isoLocal, somarDias } from "@/lib/formato";
import type { Periodo } from "@/lib/tipos";

function proximoDiaSemana(desdeIso: string, diaSemana: number) {
  let d = desdeIso;
  for (let i = 0; i < 7; i++) {
    if (new Date(`${d}T12:00`).getDay() === diaSemana && i > 0) return d;
    d = somarDias(d, 1);
  }
  return d;
}

function deIsoCurta(iso: string, hoje: string) {
  if (iso === hoje) return "Hoje";
  if (iso === somarDias(hoje, 1)) return "Amanhã";
  const d = new Date(`${iso}T12:00`);
  return d.toLocaleDateString("pt-BR", { weekday: "short", day: "numeric", month: "short" }).replace(/\./g, "");
}

function sabadoDeVerao(hoje: string) {
  const ano = Number(hoje.slice(0, 4));
  const mes = Number(hoje.slice(5, 7));
  const inicio = mes <= 1 ? hoje : `${ano + 1}-01-01`;
  return proximoDiaSemana(somarDias(inicio, -1), 6);
}

export default function PainelQuando({ numero }: { numero: number }) {
  const { opcoes } = useDados();
  const { data, setData, periodo, setPeriodo } = useCenario();
  const hoje = isoLocal(new Date());
  const feriados = new Set(opcoes?.feriados ?? []);
  const proximoFeriado = opcoes?.feriados.find((f) => f >= hoje);
  const atalhos = [
    { rotulo: "Hoje", data: hoje },
    { rotulo: "Amanhã", data: somarDias(hoje, 1) },
    { rotulo: "Próximo sábado", data: proximoDiaSemana(hoje, 6) },
    ...(proximoFeriado ? [{ rotulo: "Próximo feriado", data: proximoFeriado }] : []),
    { rotulo: "Sábado de verão", data: sabadoDeVerao(hoje) },
  ];
  const dia = new Date(`${data}T12:00`);
  const selos = [
    feriados.has(data) && "Feriado",
    (feriados.has(somarDias(data, 1)) || feriados.has(somarDias(data, -1))) && !feriados.has(data) && "Véspera/pós-feriado",
    [0, 6].includes(dia.getDay()) && "Fim de semana",
    [11, 0, 1].includes(dia.getMonth()) && "Temporada de verão",
  ].filter(Boolean) as string[];
  const rotuloPeriodo = opcoes?.periodos.find((p) => p.id === periodo)?.rotulo;
  const resumo = `${deIsoCurta(data, hoje)}${rotuloPeriodo ? ` · ${rotuloPeriodo}` : ""}`;

  return (
    <Passo numero={numero} titulo="Quando" resumo={resumo}>
      <div className="flex flex-wrap gap-1.5">
        {atalhos.map((a) => (
          <button key={a.rotulo} type="button" onClick={() => setData(a.data)} className={ESTILO.chip(data === a.data)}>
            {a.rotulo}
          </button>
        ))}
      </div>
      <label className={`relative mt-2 flex items-center gap-2 ${ESTILO.campo}`}>
        <CalendarDays size={16} aria-hidden className="text-texto-fraco" />
        <span className="sr-only">Data</span>
        <input type="date" value={data} min="2025-01-01" max="2027-12-31"
          onChange={(e) => e.target.value && setData(e.target.value)}
          className="flex-1 bg-transparent outline-none" />
      </label>
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs">
        <span className="text-texto-suave">{dataExtensa(data)}</span>
        {selos.map((s) => <span key={s} className={ESTILO.selo}>{s}</span>)}
      </div>

      <div className="mt-3">
        <Segmentado<Periodo> rotulo="Período do dia" colunas={4} valor={periodo} onMudar={setPeriodo}
          opcoes={(opcoes?.periodos ?? []).map((p) => ({
            id: p.id,
            conteudo: (
              <>
                <IconePeriodo periodo={p.id} size={18} className="mx-auto" />
                <div className="mt-1">{p.rotulo}</div>
                <div className="text-[10px] font-normal text-texto-fraco">{p.faixa}</div>
              </>
            ),
          }))} />
      </div>
    </Passo>
  );
}
