import { Cloud, CloudLightning, CloudRain, MoonStar, Sun, Sunrise, Sunset, type LucideProps } from "lucide-react";

import type { CategoriaClima, Periodo } from "@/lib/tipos";

// Ícones vetoriais (no lugar dos emojis, que mudam de aparência em cada sistema)
const PERIODO = { madrugada: MoonStar, manha: Sunrise, tarde: Sun, noite: Sunset } satisfies Record<Periodo, unknown>;
const CLIMA = { ceu_claro: Sun, nublado: Cloud, chuva: CloudRain, chuva_forte: CloudLightning } satisfies Record<CategoriaClima, unknown>;

export function IconePeriodo({ periodo, ...props }: { periodo: Periodo } & LucideProps) {
  const Icone = PERIODO[periodo] ?? Sun;
  return <Icone size={16} aria-hidden {...props} />;
}

export function IconeClima({ clima, ...props }: { clima: string } & LucideProps) {
  const Icone = CLIMA[clima as CategoriaClima] ?? Cloud;
  return <Icone size={16} aria-hidden {...props} />;
}
