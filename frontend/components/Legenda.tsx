"use client";

import { Eye, EyeOff } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useState } from "react";

import { useDados } from "@/lib/contexto";
import { FAIXAS, FAIXAS_HISTORICO } from "@/lib/formato";

// ---- faixas do histórico escondidas pelo usuário (clique na legenda) ----------------------------
const ContextoFaixas = createContext<{ ocultas: Set<string>; alternar: (rotulo: string) => void }>({
  ocultas: new Set(),
  alternar: () => {},
});

export function FaixasProvider({ children }: { children: React.ReactNode }) {
  const [ocultas, setOcultas] = useState<Set<string>>(new Set());
  const alternar = useCallback((rotulo: string) => {
    setOcultas((atual) => {
      const nova = new Set(atual);
      if (nova.has(rotulo)) nova.delete(rotulo);
      else nova.add(rotulo);
      // esconder tudo não faz sentido: o último clique volta a mostrar todas
      return nova.size === FAIXAS_HISTORICO.length ? new Set() : nova;
    });
  }, []);
  const valor = useMemo(() => ({ ocultas, alternar }), [ocultas, alternar]);
  return <ContextoFaixas.Provider value={valor}>{children}</ContextoFaixas.Provider>;
}

export function useFaixasOcultas() {
  return useContext(ContextoFaixas);
}

const DICA_RISCO: Record<string, string> = {
  Baixo: "menos de 2% de chance no período de 6 h",
  Moderado: "de 2% a 5% de chance no período de 6 h",
  Alto: "de 5% a 12% de chance no período de 6 h",
  "Muito alto": "12% ou mais de chance no período de 6 h",
};

export default function Legenda({ emCenario }: { emCenario: boolean }) {
  const { temEstaduais } = useDados();
  const { ocultas, alternar } = useFaixasOcultas();

  return (
    <div className="absolute right-2 top-2 z-[500] rounded-lg border border-borda bg-superficie/95 px-2 py-1 text-[10px] text-texto-suave shadow-sm backdrop-blur md:bottom-3 md:left-3 md:right-auto md:top-auto md:rounded-xl md:px-3 md:py-2 md:text-[11px]">
      <div className="mb-1 hidden font-medium text-texto md:block">
        {emCenario ? "Chance no cenário" : "Acidentes por 10 km/ano"}
        {!emCenario && <span className="ml-1 font-normal text-texto-fraco">· clique para filtrar</span>}
      </div>
      <div className="flex gap-1">
        {emCenario
          ? FAIXAS.map((f) => (
            <span key={f.rotulo} title={DICA_RISCO[f.rotulo]} className="flex items-center gap-1 px-1">
              <span className="h-1.5 w-4 rounded-full" style={{ background: f.cor }} />{f.rotulo}
            </span>
          ))
          : FAIXAS_HISTORICO.map((f) => {
            const oculta = ocultas.has(f.rotulo);
            return (
              <button key={f.rotulo} type="button" onClick={() => alternar(f.rotulo)} aria-pressed={!oculta}
                title={`${oculta ? "Mostrar" : "Esconder"} trechos com ${f.rotulo} acidentes por 10 km/ano`}
                className={`flex items-center gap-1 rounded px-1 py-0.5 transition hover:bg-superficie-2 ${oculta ? "opacity-40" : ""}`}>
                <span className="h-1.5 w-4 rounded-full" style={{ background: f.cor }} />
                {f.rotulo}
                {oculta ? <EyeOff size={10} aria-hidden /> : <Eye size={10} aria-hidden className="hidden md:block opacity-50" />}
              </button>
            );
          })}
      </div>
      {temEstaduais && (
        <div className="mt-1 flex gap-3 border-t border-borda px-1 pt-1">
          <span className="flex items-center gap-1"><span className="h-0.5 w-4 bg-texto-suave" />Federal (BR)</span>
          <span className="flex items-center gap-1"><span className="w-4 border-t-2 border-dashed border-texto-suave" />Estadual (SC)</span>
        </div>
      )}
    </div>
  );
}
