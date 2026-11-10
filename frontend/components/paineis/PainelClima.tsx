"use client";

import { CloudSun } from "lucide-react";

import { ESTILO, Passo, Segmentado } from "./base";
import { IconeClima } from "@/components/Icones";
import { useCenario, useDados } from "@/lib/contexto";
import { diasAte } from "@/lib/formato";
import { usePrevisaoTempo } from "@/lib/hooks";
import type { CategoriaClima } from "@/lib/tipos";

export default function PainelClima({ numero, trechoIds }: { numero: number; trechoIds: string[] }) {
  const { opcoes } = useDados();
  const { data, clima, setClima, climaPrevisto } = useCenario();
  const previsaoTempo = usePrevisaoTempo(trechoIds);
  const dias = diasAte(data);
  const previsaoDisponivel = dias >= 0 && dias <= 15;
  const podeUsar = trechoIds.length > 0;
  const resumo = climaPrevisto ? "Previsão do tempo" : opcoes?.clima.find((c) => c.id === clima)?.rotulo;

  return (
    <Passo numero={numero} titulo="Condições do tempo" resumo={resumo}>
      <Segmentado<CategoriaClima> rotulo="Clima" colunas={4} valor={clima} onMudar={setClima}
        opcoes={(opcoes?.clima ?? []).map((c) => ({
          id: c.id,
          dica: `${Math.round(c.frequencia * 100)}% dos períodos no histórico · ${c.chuva_mm} mm em 6 h`,
          conteudo: (
            <>
              <IconeClima clima={c.id} size={18} className="mx-auto" />
              <div className="mt-1">{c.rotulo}</div>
            </>
          ),
        }))} />

      {climaPrevisto ? (
        <div className={`mt-2 ${ESTILO.info}`}>
          <b>Usando a previsão do tempo:</b> {climaPrevisto.chuva_mm.toLocaleString("pt-BR")} mm de chuva,{" "}
          {Math.round(climaPrevisto.nebulosidade)}% de nuvens, {climaPrevisto.temperatura.toLocaleString("pt-BR")} °C.
          Escolha uma opção acima para voltar ao manual.
        </div>
      ) : previsaoDisponivel ? (
        <button type="button" onClick={previsaoTempo.usar} disabled={!podeUsar || previsaoTempo.carregando}
          className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-sm font-medium text-sky-800 transition hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-200 dark:hover:bg-sky-500/20">
          <CloudSun size={16} aria-hidden />
          {previsaoTempo.carregando ? "Buscando previsão…" : "Usar a previsão do tempo para esse dia"}
        </button>
      ) : (
        <p className="mt-2 text-xs text-texto-fraco">A previsão do tempo automática vale para os próximos 16 dias.</p>
      )}
      {!podeUsar && previsaoDisponivel && !climaPrevisto && (
        <p className="mt-1 text-xs text-texto-fraco">Escolha um trecho, rodovia ou rota para buscar a previsão.</p>
      )}
      {previsaoTempo.erro && <p className="mt-1 text-xs text-red-600 dark:text-red-400">{previsaoTempo.erro}</p>}
    </Passo>
  );
}
