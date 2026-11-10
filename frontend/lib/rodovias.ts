import { capitalizar } from "./formato";
import type { PropsTrecho, Rede } from "./tipos";

// Uma rodovia inteira ("extensão") = todos os trechos dela que o modelo cobre
export interface Rodovia {
  rodovia: string;           // "BR-101", "SC-401"
  rede: Rede;
  trecho_ids: string[];
  extensao_km: number;
  acidentes_ano: number;
  densidade: number;         // acidentes por 10 km por ano
  mortos: number;
  municipios: string[];
}

function numeroDaRodovia(r: string) {
  return Number(r.replace(/\D/g, "")) || 0;
}

export function agruparPorRodovia(trechos: PropsTrecho[]): Rodovia[] {
  const grupos = new Map<string, PropsTrecho[]>();
  for (const t of trechos) grupos.set(t.rodovia, [...(grupos.get(t.rodovia) ?? []), t]);

  return [...grupos.entries()]
    .map(([rodovia, ts]) => {
      const extensao = ts.reduce((s, t) => s + t.comprimento_km, 0);
      const acidentesAno = ts.reduce((s, t) => s + t.acidentes_ano, 0);
      // BR: ordem do km (está no id "101-200"); SC: ordem alfabética do município
      const ordenados = [...ts].sort((a, b) => a.rede === "br"
        ? Number(a.trecho_id.split("-")[1]) - Number(b.trecho_id.split("-")[1])
        : a.municipio.localeCompare(b.municipio));
      return {
        rodovia,
        rede: ts[0].rede,
        trecho_ids: ordenados.map((t) => t.trecho_id),
        extensao_km: Math.round(extensao),
        acidentes_ano: Math.round(acidentesAno * 10) / 10,
        densidade: Math.round((acidentesAno / Math.max(extensao, 1)) * 100) / 10,
        mortos: ts.reduce((s, t) => s + t.mortos, 0),
        municipios: [...new Set(ordenados.map((t) => capitalizar(t.municipio)))],
      };
    })
    .sort((a, b) => a.rede.localeCompare(b.rede) || numeroDaRodovia(a.rodovia) - numeroDaRodovia(b.rodovia));
}

export function limitesDe(coords: number[][]): [[number, number], [number, number]] {
  const lats = coords.map((c) => c[1]);
  const lons = coords.map((c) => c[0]);
  return [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]];
}
