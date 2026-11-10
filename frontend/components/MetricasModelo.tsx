"use client";

import { SecaoRede } from "@/components/SobreModelo";
import { useDados } from "@/lib/contexto";
import type { Rede } from "@/lib/tipos";

/** Métricas dos modelos (vêm da API): a única parte da página "Sobre" que roda no navegador. */
export default function MetricasModelo() {
  const { metricas, erro } = useDados();
  const redes = (["br", "sc"] as Rede[]).filter((r) => metricas?.[r]);

  if (erro) return <p className="text-sm text-texto-fraco">Métricas indisponíveis: não foi possível falar com o servidor.</p>;
  if (!metricas) return <div className="h-40 animate-pulse rounded-2xl border border-borda bg-superficie" />;
  return (
    <>
      {redes.map((r) => (
        <div key={r} className="rounded-2xl border border-borda bg-superficie p-5">
          <SecaoRede rede={r} metricas={metricas[r]!} />
        </div>
      ))}
    </>
  );
}
