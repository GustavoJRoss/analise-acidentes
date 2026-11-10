"use client";

import { RotateCw } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

import Legenda, { FaixasProvider } from "@/components/Legenda";
import { ESTILO } from "@/components/paineis/base";
import { useDados } from "@/lib/contexto";
import { useMediaQuery } from "@/lib/hooks";

// Leaflet usa `window`: o mapa só é carregado no navegador
export const Mapa = dynamic(() => import("@/components/Mapa"), {
  ssr: false,
  loading: () => <div className="flex h-full items-center justify-center bg-superficie-2 text-sm text-texto-fraco">Carregando mapa…</div>,
});

// alturas do painel no celular (fração da área abaixo do header): resumo, meio, cheio
const NIVEIS = [0.3, 0.56, 0.92];

/** Painel que desliza de baixo no celular: toque na alça alterna a altura, arrastar ajusta. */
function usePainelDeslizante(area: React.RefObject<HTMLElement | null>) {
  const [nivel, setNivel] = useState(1);
  const [arrasto, setArrasto] = useState<number | null>(null);
  const inicio = useRef<{ y: number; fracao: number; moveu: boolean } | null>(null);

  const alca = {
    onPointerDown(e: React.PointerEvent) {
      inicio.current = { y: e.clientY, fracao: NIVEIS[nivel], moveu: false };
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    },
    onPointerMove(e: React.PointerEvent) {
      const ini = inicio.current;
      const altura = area.current?.clientHeight;
      if (!ini || !altura) return;
      const dy = e.clientY - ini.y;
      if (Math.abs(dy) > 6) ini.moveu = true;
      if (ini.moveu) setArrasto(Math.min(0.95, Math.max(0.15, ini.fracao - dy / altura)));
    },
    onPointerUp() {
      const ini = inicio.current;
      inicio.current = null;
      if (!ini) return;
      if (!ini.moveu) {
        setNivel((n) => (n + 1) % NIVEIS.length);
      } else if (arrasto !== null) {
        const maisPerto = NIVEIS.reduce((m, v, i) => (Math.abs(v - arrasto) < Math.abs(NIVEIS[m] - arrasto) ? i : m), 0);
        setNivel(maisPerto);
      }
      setArrasto(null);
    },
  };

  return { fracao: arrasto ?? NIVEIS[nivel], arrastando: arrasto !== null, nivel, setNivel, alca };
}

/** Casca das páginas com mapa: barra lateral à esquerda no desktop, painel deslizante no celular. */
export default function LayoutMapa({ barra, cartao, mapa, emCenario, dica, selecionou }: {
  barra: React.ReactNode;
  cartao: React.ReactNode;
  mapa: React.ReactNode;
  emCenario: boolean;
  dica?: React.ReactNode;
  /** muda quando o usuário escolhe algo: no celular, baixa o painel para mostrar mapa + resultado */
  selecionou: string;
}) {
  const { erro, recarregar } = useDados();
  const desktop = useMediaQuery("(min-width: 768px)");
  const area = useRef<HTMLElement>(null);
  const rolagem = useRef<HTMLDivElement>(null);
  const painel = usePainelDeslizante(area);
  const { setNivel } = painel;

  useEffect(() => {
    if (selecionou && !window.matchMedia("(min-width: 768px)").matches) {
      setNivel(0);
      rolagem.current?.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, [selecionou, setNivel]);

  return (
    <FaixasProvider>
      <main ref={area} className="relative h-full overflow-hidden md:flex md:flex-row">
        <section className="absolute inset-0 isolate md:relative md:inset-auto md:order-2 md:h-full md:flex-1">
          {mapa}
          {desktop && (
            <div className="pointer-events-none absolute inset-x-0 top-0 z-[500] flex justify-end p-4">
              <div className="pointer-events-auto max-h-[calc(100dvh-5.5rem)] w-[380px] overflow-y-auto rounded-2xl">{cartao}</div>
            </div>
          )}
          <Legenda emCenario={emCenario} />
          {dica}
        </section>

        <aside
          style={{ "--altura-painel": `${painel.fracao * 100}%` } as React.CSSProperties}
          className={`absolute inset-x-0 bottom-0 z-10 flex h-[var(--altura-painel)] flex-col rounded-t-2xl border-t border-borda bg-superficie shadow-[0_-8px_24px_rgb(var(--sombra)/0.18)] ${
            painel.arrastando ? "" : "transition-[height] duration-300 ease-out"
          } md:static md:z-auto md:order-1 md:h-full md:w-[400px] md:flex-none md:rounded-none md:border-r md:border-t-0 md:shadow-none md:transition-none`}>
          <button type="button" {...painel.alca}
            aria-label={painel.nivel === NIVEIS.length - 1 ? "Recolher painel" : "Expandir painel"}
            className="flex h-6 shrink-0 touch-none items-center justify-center md:hidden">
            <span className="h-1.5 w-10 rounded-full bg-borda-forte" />
          </button>
          <div ref={rolagem} className="flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain">
            {erro && (
              <div className={`m-5 mb-0 flex items-start gap-3 ${ESTILO.erro}`}>
                <span className="flex-1">{erro}</span>
                <button type="button" onClick={recarregar} className={ESTILO.botaoSecundario}>
                  <RotateCw size={12} aria-hidden /> Tentar de novo
                </button>
              </div>
            )}
            {!desktop && <div className="px-4 pb-1 pt-1">{cartao}</div>}
            {barra}
            <footer className="mt-auto px-5 py-4 text-[11px] text-texto-fraco">
              Dados: PRF, RENAEST/Senatran, © OpenStreetMap, IBGE e Open-Meteo. Projeto de estudo.
            </footer>
          </div>
        </aside>
      </main>
    </FaixasProvider>
  );
}
