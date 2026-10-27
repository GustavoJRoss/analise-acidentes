"use client";

import "leaflet/dist/leaflet.css";

import type { Feature, GeoJsonObject } from "geojson";
import L from "leaflet";
import { useEffect, useMemo } from "react";
import { CircleMarker, GeoJSON, MapContainer, Polyline, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";

import { capitalizar, corHistorico, faixaRisco, nomeTrecho } from "@/lib/formato";
import type { Lugar, Modo, PropsTrecho, Rota, TrechosGeoJSON } from "@/lib/tipos";

const CENTRO_SC: [number, number] = [-27.25, -50.3];
const LIMITES_SC = L.latLngBounds([-29.6, -54.0], [-25.8, -48.2]);

interface Props {
  trechos: TrechosGeoJSON | null;
  modo: Modo;
  trechoSelecionado: string | null;
  probPorTrecho: Record<string, number>;
  rota: Rota | null;
  origem: Lugar | null;
  destino: Lugar | null;
  enquadrar: { chave: number; limites: [[number, number], [number, number]] } | null;
  onClicarTrecho: (id: string) => void;
  onClicarMapa: (lat: number, lon: number) => void;
}

function CliquesNoMapa({ ativo, onClicar }: { ativo: boolean; onClicar: (lat: number, lon: number) => void }) {
  useMapEvents({
    click(e) {
      if (ativo) onClicar(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function Enquadrar({ enquadrar }: { enquadrar: Props["enquadrar"] }) {
  const map = useMap();
  useEffect(() => {
    if (!enquadrar) return;
    // no desktop o cartão de resultado cobre a direita do mapa
    const desktop = window.matchMedia("(min-width: 768px)").matches;
    map.flyToBounds(enquadrar.limites, {
      paddingTopLeft: [40, 40],
      paddingBottomRight: [desktop ? 420 : 40, 40],
      maxZoom: 12,
      duration: 0.8,
    });
  }, [enquadrar, map]);
  return null;
}

function textoTooltip(p: PropsTrecho, prob?: number) {
  const linhaProb =
    prob !== undefined
      ? `<div style="margin-top:4px"><b style="color:${faixaRisco(prob).cor}">${(prob * 100).toFixed(1)}%</b> no cenário escolhido</div>`
      : "";
  return `<div style="font-size:12px;line-height:1.35">
    <div style="font-weight:600">${nomeTrecho(p.br, p.trecho_km)}</div>
    <div style="color:#475569">${capitalizar(p.municipio)}</div>
    <div style="color:#475569">${p.acidentes} acidentes em 2025 · ${p.mortos} mortes</div>
    ${linhaProb}
  </div>`;
}

export default function Mapa(props: Props) {
  const { trechos, modo, trechoSelecionado, probPorTrecho, rota, origem, destino, enquadrar } = props;
  const destacados = useMemo(() => new Set(Object.keys(probPorTrecho)), [probPorTrecho]);
  // GeoJSON do react-leaflet não reage a mudanças de estilo: a chave força o redesenho
  const chaveCamadas = `${modo}|${trechoSelecionado}|${Object.entries(probPorTrecho).join(",")}`;

  const estiloVisivel = (f?: Feature) => {
    const p = f!.properties as PropsTrecho;
    const prob = probPorTrecho[p.trecho_id];
    if (prob !== undefined) {
      return { color: faixaRisco(prob).cor, weight: p.trecho_id === trechoSelecionado ? 9 : 7, opacity: 1 };
    }
    const apagado = destacados.size > 0;
    return { color: corHistorico(p.acidentes), weight: 4, opacity: apagado ? 0.35 : 0.9 };
  };

  return (
    <MapContainer
      center={CENTRO_SC}
      zoom={7}
      minZoom={6}
      maxBounds={LIMITES_SC.pad(0.5)}
      className="h-full w-full"
      zoomControl={false}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <CliquesNoMapa ativo={modo === "rota"} onClicar={props.onClicarMapa} />
      <Enquadrar enquadrar={enquadrar} />

      {rota && (
        <Polyline
          positions={rota.geometria.coordinates.map(([lon, lat]) => [lat, lon] as [number, number])}
          pathOptions={{ color: "#1e40af", weight: 12, opacity: 0.25 }}
          interactive={false}
        />
      )}

      {trechos && (
        <>
          <GeoJSON
            key={`v-${chaveCamadas}`}
            data={trechos as unknown as GeoJsonObject}
            style={estiloVisivel}
            interactive={false}
          />
          {/* camada invisível e larga: facilita clicar na rodovia (principalmente no celular) */}
          <GeoJSON
            key={`h-${chaveCamadas}`}
            data={trechos as unknown as GeoJsonObject}
            style={{ color: "#000", weight: 18, opacity: 0 }}
            interactive={modo === "trecho"}
            onEachFeature={(f, camada) => {
              const p = f.properties as PropsTrecho;
              camada.bindTooltip(textoTooltip(p, probPorTrecho[p.trecho_id]), {
                sticky: true,
                className: "tooltip-trecho",
              });
              camada.on("click", () => props.onClicarTrecho(p.trecho_id));
            }}
          />
        </>
      )}

      {origem && (
        <CircleMarker center={[origem.lat, origem.lon]} radius={9}
          pathOptions={{ color: "#fff", weight: 3, fillColor: "#16a34a", fillOpacity: 1 }}>
          <Tooltip direction="top" offset={[0, -8]}>Origem</Tooltip>
        </CircleMarker>
      )}
      {destino && (
        <CircleMarker center={[destino.lat, destino.lon]} radius={9}
          pathOptions={{ color: "#fff", weight: 3, fillColor: "#dc2626", fillOpacity: 1 }}>
          <Tooltip direction="top" offset={[0, -8]}>Destino</Tooltip>
        </CircleMarker>
      )}
    </MapContainer>
  );
}
