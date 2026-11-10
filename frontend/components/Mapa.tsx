"use client";

import "leaflet/dist/leaflet.css";

import type { Feature, GeoJsonObject, MultiPolygon, Polygon, Position } from "geojson";
import L from "leaflet";
import { LocateFixed, Maximize, Minus, Plus } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  CircleMarker, GeoJSON, MapContainer, Marker, Pane, Polyline, TileLayer, Tooltip, useMap, useMapEvents,
} from "react-leaflet";

import { useFaixasOcultas } from "./Legenda";
import { type FiltroDeRede, passaNoFiltro } from "./paineis/FiltroRede";
import { useTema } from "./TemaProvider";
import { capitalizar, corHistorico, decimal, faixaHistorico, faixaRisco } from "@/lib/formato";
import type { Lugar, PropsTrecho, Rota, TrechosGeoJSON } from "@/lib/tipos";

const CENTRO_SC: [number, number] = [-27.25, -50.3];
const LIMITES_SC = L.latLngBounds([-29.6, -54.0], [-25.8, -48.2]);

// Mapa base da CARTO: tem versão clara e escura de verdade (antes o OSM era invertido por CSS)
const TILES = {
  claro: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
  escuro: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
};
const ATRIBUICAO = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>';

export type Enquadramento = { chave: number; limites: [[number, number], [number, number]] } | null;

interface Props {
  trechos: TrechosGeoJSON | null;
  filtroRede: FiltroDeRede;
  trechoSelecionado?: string | null;
  probPorTrecho: Record<string, number>;
  rota?: Rota | null;
  origem?: Lugar | null;
  destino?: Lugar | null;
  enquadrar: Enquadramento;
  /** com este callback os trechos ficam clicáveis (mapa de risco) */
  onClicarTrecho?: (id: string) => void;
  /** com este callback cliques no mapa marcam pontos (viagem); os trechos então só mostram o tooltip */
  onClicarMapa?: (lat: number, lon: number) => void;
  /** com estes callbacks os marcadores de origem/destino podem ser arrastados */
  onMoverOrigem?: (lat: number, lon: number) => void;
  onMoverDestino?: (lat: number, lon: number) => void;
}

function CliquesNoMapa({ onClicar }: { onClicar?: (lat: number, lon: number) => void }) {
  useMapEvents({
    click(e) {
      onClicar?.(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function Enquadrar({ enquadrar }: { enquadrar: Props["enquadrar"] }) {
  const map = useMap();
  useEffect(() => {
    if (!enquadrar) return;
    // no desktop o cartão de resultado cobre a direita do mapa; no celular, o painel cobre a parte de baixo
    const desktop = window.matchMedia("(min-width: 768px)").matches;
    const alturaMapa = map.getContainer().clientHeight;
    map.flyToBounds(enquadrar.limites, {
      paddingTopLeft: [desktop ? 60 : 50, desktop ? 40 : 60],
      paddingBottomRight: [desktop ? 420 : 30, desktop ? 40 : Math.round(alturaMapa * 0.32) + 20],
      maxZoom: 12,
      duration: 0.8,
    });
  }, [enquadrar, map]);
  return null;
}

/** Zoom, "ver SC inteira" e "minha localização". Fica dentro do mapa, então o clique não pode vazar para ele. */
function ControlesMapa() {
  const map = useMap();
  const caixa = useRef<HTMLDivElement>(null);
  const [posicao, setPosicao] = useState<[number, number] | null>(null);
  const [localizando, setLocalizando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  useEffect(() => {
    if (!caixa.current) return;
    L.DomEvent.disableClickPropagation(caixa.current);
    L.DomEvent.disableScrollPropagation(caixa.current);
  }, []);

  useEffect(() => {
    if (!aviso) return;
    const t = setTimeout(() => setAviso(null), 4000);
    return () => clearTimeout(t);
  }, [aviso]);

  function localizar() {
    if (!("geolocation" in navigator)) {
      setAviso("Seu navegador não informa a localização.");
      return;
    }
    setLocalizando(true);
    navigator.geolocation.getCurrentPosition(
      (p) => {
        const ponto: [number, number] = [p.coords.latitude, p.coords.longitude];
        setPosicao(ponto);
        setLocalizando(false);
        if (!LIMITES_SC.pad(0.2).contains(ponto)) setAviso("Você está fora de Santa Catarina.");
        map.flyTo(ponto, Math.max(map.getZoom(), 11), { duration: 0.8 });
      },
      () => {
        setLocalizando(false);
        setAviso("Não foi possível obter sua localização.");
      },
      { enableHighAccuracy: false, timeout: 10_000 },
    );
  }

  const botao = "flex h-9 w-9 items-center justify-center text-texto-suave transition hover:bg-superficie-2 hover:text-texto disabled:opacity-50";

  return (
    <>
      <div ref={caixa} className="absolute left-2 top-2 z-[500] flex flex-col items-start gap-2 md:left-3 md:top-3">
        <div className="flex flex-col divide-y divide-borda overflow-hidden rounded-xl border border-borda bg-superficie/95 shadow-sm backdrop-blur">
          <button type="button" className={botao} onClick={() => map.zoomIn()} aria-label="Aproximar" title="Aproximar">
            <Plus size={16} aria-hidden />
          </button>
          <button type="button" className={botao} onClick={() => map.zoomOut()} aria-label="Afastar" title="Afastar">
            <Minus size={16} aria-hidden />
          </button>
        </div>
        <div className="flex flex-col divide-y divide-borda overflow-hidden rounded-xl border border-borda bg-superficie/95 shadow-sm backdrop-blur">
          <button type="button" className={botao} onClick={() => map.flyToBounds(LIMITES_SC, { duration: 0.8 })}
            aria-label="Ver Santa Catarina inteira" title="Ver SC inteira">
            <Maximize size={15} aria-hidden />
          </button>
          <button type="button" className={botao} onClick={localizar} disabled={localizando}
            aria-label="Ir para minha localização" title="Minha localização">
            <LocateFixed size={15} aria-hidden className={localizando ? "animate-pulse" : ""} />
          </button>
        </div>
        {aviso && (
          <div role="status" className="max-w-48 rounded-lg bg-texto/85 px-2 py-1 text-xs text-superficie shadow">{aviso}</div>
        )}
      </div>
      {posicao && (
        <CircleMarker center={posicao} radius={7} interactive={false}
          pathOptions={{ color: "#fff", weight: 2, fillColor: "#2563eb", fillOpacity: 1 }} />
      )}
    </>
  );
}

// Retângulo bem maior que a área navegável, com SC recortada como buraco: o que fica fora do estado é esmaecido
const ANEL_EXTERNO: Position[] = [[-80, -60], [-20, -60], [-20, 10], [-80, 10], [-80, -60]];

function MascaraForaDeSC({ escuro }: { escuro: boolean }) {
  const [contorno, setContorno] = useState<Polygon | MultiPolygon | null>(null);

  useEffect(() => {
    // contorno oficial do IBGE (API de malhas, qualidade máxima), salvo em public/sc.geojson
    fetch("/sc.geojson")
      .then((r) => r.json())
      .then((fc) => setContorno(fc.features[0].geometry))
      .catch(() => setContorno(null));
  }, []);

  const mascara = useMemo<Feature<Polygon> | null>(() => {
    if (!contorno) return null;
    const poligonos = contorno.type === "Polygon" ? [contorno.coordinates] : contorno.coordinates;
    return {
      type: "Feature",
      properties: {},
      geometry: { type: "Polygon", coordinates: [ANEL_EXTERNO, ...poligonos.map((p) => p[0])] },
    };
  }, [contorno]);

  if (!contorno || !mascara) return null;
  return (
    <Pane name="mascara" style={{ zIndex: 350 }}>
      <GeoJSON key={`m-${escuro}`} data={mascara} interactive={false}
        style={{ stroke: false, fillColor: escuro ? "#020617" : "#f1f5f9", fillOpacity: escuro ? 0.55 : 0.65 }} />
      <GeoJSON key={`c-${escuro}`} data={contorno} interactive={false}
        style={{ color: escuro ? "#94a3b8" : "#475569", weight: 1.5, opacity: 0.8, fill: false }} />
    </Pane>
  );
}

function escapar(texto: string) {
  return texto.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

function textoTooltip(p: PropsTrecho, prob: number | undefined, clicavel: boolean) {
  const linhaProb =
    prob !== undefined
      ? `<div style="margin-top:4px"><b style="color:${faixaRisco(prob).cor}">${(prob * 100).toFixed(1)}%</b> no cenário escolhido</div>`
      : "";
  const local = p.rede === "br" ? capitalizar(p.municipio) : `Rodovia estadual · ${decimal(p.comprimento_km)} km no município`;
  const acao = clicavel && prob === undefined ? `<div style="margin-top:4px;color:var(--primaria)">Clique para ver o risco</div>` : "";
  return `<div style="font-size:12px;line-height:1.35">
    <div style="font-weight:600">${escapar(p.rotulo)}</div>
    <div style="color:var(--texto-suave)">${escapar(local)}</div>
    <div style="color:var(--texto-suave)">${decimal(p.acidentes_ano)} acidentes/ano · ${p.mortos} mortes</div>
    <div style="color:var(--texto-fraco)">${escapar(p.periodo_dados)}</div>
    ${linhaProb}${acao}
  </div>`;
}

const iconePonto = (cor: string) => L.divIcon({
  className: "",
  html: `<div class="marcador-ponto" style="background:${cor};width:20px;height:20px"></div>`,
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});
const ICONE_ORIGEM = iconePonto("#16a34a");
const ICONE_DESTINO = iconePonto("#dc2626");

type CamadaTrecho = L.Path & { feature: Feature; getTooltip(): L.Tooltip | undefined };

export default function Mapa(props: Props) {
  const { trechos, filtroRede, trechoSelecionado = null, probPorTrecho, rota, origem, destino, enquadrar } = props;
  const escuro = useTema().tema === "escuro";
  const { ocultas } = useFaixasOcultas();
  const clicavel = Boolean(props.onClicarTrecho);
  const destacados = useMemo(() => new Set(Object.keys(probPorTrecho)), [probPorTrecho]);
  const camadaVisivel = useRef<L.GeoJSON>(null);
  const camadaClique = useRef<L.GeoJSON>(null);
  // o clique é ligado uma vez por camada: lê sempre o callback mais recente
  const onClicarTrecho = useRef(props.onClicarTrecho);
  useEffect(() => {
    onClicarTrecho.current = props.onClicarTrecho;
  });

  // o filtro de rede e a legenda escondem o resto, mas nunca o que está em uso (selecionado, na rodovia ou na rota)
  const { visiveis, chaveCamadas } = useMemo(() => {
    if (!trechos) return { visiveis: null, chaveCamadas: "" };
    const extras: string[] = [];
    const features = trechos.features.filter((f) => {
      const p = f.properties;
      const passa = passaNoFiltro(p.rede, filtroRede) && !ocultas.has(faixaHistorico(p.densidade).rotulo);
      const emUso = destacados.has(p.trecho_id) || p.trecho_id === trechoSelecionado;
      if (!passa && emUso) extras.push(p.trecho_id);
      return passa || emUso;
    });
    // só o conjunto de features força o redesenho; cores e tooltips são atualizados no lugar (efeito abaixo)
    return {
      visiveis: { ...trechos, features },
      chaveCamadas: `${clicavel}|${filtroRede}|${[...ocultas].join()}|${extras.join()}`,
    };
  }, [trechos, filtroRede, ocultas, destacados, trechoSelecionado, clicavel]);

  const estiloVisivel = (f?: Feature): L.PathOptions => {
    const p = f!.properties as PropsTrecho;
    const prob = probPorTrecho[p.trecho_id];
    // rodovias estaduais tracejadas, para diferenciar das BRs
    const traco = p.rede === "sc" ? { dashArray: "7 5", lineCap: "butt" as const } : { dashArray: undefined, lineCap: "round" as const };
    if (prob !== undefined) {
      return { color: faixaRisco(prob).cor, weight: p.trecho_id === trechoSelecionado ? 9 : 7, opacity: 1, ...traco };
    }
    const apagado = destacados.size > 0;
    return { color: corHistorico(p.densidade), weight: p.rede === "sc" ? 3.5 : 4, opacity: apagado ? 0.35 : 0.9, ...traco };
  };

  // cenário mudou: recolore e atualiza os tooltips sem desmontar as camadas (antes o mapa "piscava")
  useEffect(() => {
    camadaVisivel.current?.setStyle(estiloVisivel as L.StyleFunction);
    camadaClique.current?.eachLayer((l) => {
      const camada = l as CamadaTrecho;
      const p = camada.feature.properties as PropsTrecho;
      camada.getTooltip()?.setContent(textoTooltip(p, probPorTrecho[p.trecho_id], clicavel));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [probPorTrecho, trechoSelecionado, destacados, chaveCamadas]);

  const selecionadoFeature = trechoSelecionado ? trechos?.features.find((f) => f.properties.trecho_id === trechoSelecionado) : null;

  return (
    <div className="relative h-full w-full">
      <MapContainer
        center={CENTRO_SC}
        zoom={7}
        minZoom={6}
        maxBounds={LIMITES_SC.pad(0.5)}
        className="h-full w-full"
        zoomControl={false}
      >
        <TileLayer key={escuro ? "escuro" : "claro"} url={escuro ? TILES.escuro : TILES.claro} attribution={ATRIBUICAO}
          subdomains="abcd" maxZoom={19} />
        <MascaraForaDeSC escuro={escuro} />
        <CliquesNoMapa onClicar={props.onClicarMapa} />
        <Enquadrar enquadrar={enquadrar} />
        <ControlesMapa />

        {/* rota e halo da seleção ficam embaixo dos trechos */}
        <Pane name="destaques" style={{ zIndex: 390 }}>
          {rota && (
            <Polyline
              positions={rota.geometria.coordinates.map(([lon, lat]) => [lat, lon] as [number, number])}
              pathOptions={{ color: escuro ? "#60a5fa" : "#1e40af", weight: 12, opacity: escuro ? 0.35 : 0.25 }}
              interactive={false}
            />
          )}
          {selecionadoFeature && (
            <GeoJSON key={`s-${trechoSelecionado}-${escuro}`} data={selecionadoFeature as unknown as GeoJsonObject}
              interactive={false}
              style={{ color: escuro ? "#e2e8f0" : "#0f172a", weight: 16, opacity: 0.9, lineCap: "round", className: "trecho-pulso" }} />
          )}
        </Pane>

        {visiveis && (
          <>
            <GeoJSON
              ref={camadaVisivel}
              key={`v-${chaveCamadas}`}
              data={visiveis as unknown as GeoJsonObject}
              style={estiloVisivel}
              interactive={false}
            />
            {/* camada invisível e larga: facilita clicar na rodovia (principalmente no celular) */}
            <GeoJSON
              ref={camadaClique}
              key={`h-${chaveCamadas}`}
              data={visiveis as unknown as GeoJsonObject}
              style={{ color: "#000", weight: 18, opacity: 0 }}
              interactive
              onEachFeature={(f, camada) => {
                const p = f.properties as PropsTrecho;
                camada.bindTooltip(textoTooltip(p, probPorTrecho[p.trecho_id], clicavel), {
                  sticky: true,
                  className: "tooltip-trecho",
                });
                if (clicavel) camada.on("click", () => onClicarTrecho.current?.(p.trecho_id));
              }}
            />
          </>
        )}

        {origem && (
          <Marker position={[origem.lat, origem.lon]} icon={ICONE_ORIGEM} draggable={Boolean(props.onMoverOrigem)}
            eventHandlers={{ dragend: (e) => { const ll = (e.target as L.Marker).getLatLng(); props.onMoverOrigem?.(ll.lat, ll.lng); } }}>
            <Tooltip direction="top" offset={[0, -10]}>Origem{props.onMoverOrigem ? " · arraste para ajustar" : ""}</Tooltip>
          </Marker>
        )}
        {destino && (
          <Marker position={[destino.lat, destino.lon]} icon={ICONE_DESTINO} draggable={Boolean(props.onMoverDestino)}
            eventHandlers={{ dragend: (e) => { const ll = (e.target as L.Marker).getLatLng(); props.onMoverDestino?.(ll.lat, ll.lng); } }}>
            <Tooltip direction="top" offset={[0, -10]}>Destino{props.onMoverDestino ? " · arraste para ajustar" : ""}</Tooltip>
          </Marker>
        )}
      </MapContainer>

      {!trechos && (
        <div className="pointer-events-none absolute inset-0 z-[600] flex items-center justify-center">
          <div className="flex items-center gap-2 rounded-full border border-borda bg-superficie/95 px-3 py-1.5 text-xs text-texto-suave shadow">
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-borda-forte border-t-primaria" />
            Carregando rodovias…
          </div>
        </div>
      )}
    </div>
  );
}
