"use client";

import { History, MapPin, Route, X } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

import CartaoResultado from "@/components/CartaoResultado";
import LayoutMapa, { Mapa } from "@/components/LayoutMapa";
import type { Enquadramento } from "@/components/Mapa";
import { ESTILO, Passo, Segmentado } from "@/components/paineis/base";
import FiltroRede, { type FiltroDeRede } from "@/components/paineis/FiltroRede";
import PainelClima from "@/components/paineis/PainelClima";
import PainelQuando from "@/components/paineis/PainelQuando";
import SeletorRodovia from "@/components/paineis/SeletorRodovia";
import SeletorTrecho from "@/components/paineis/SeletorTrecho";
import { useDados } from "@/lib/contexto";
import { usePrevisao, useRecentes } from "@/lib/hooks";
import { limitesDe } from "@/lib/rodovias";
import { atualizarUrl, useParametro } from "@/lib/url";

type Nivel = "trecho" | "rodovia";
type Recente = { tipo: Nivel; id: string; rotulo: string };

const ROTULO_REDE: Record<FiltroDeRede, string> = { todas: "Todas", br: "Federais", sc: "Estaduais" };
const mesmoRecente = (a: Recente, b: Recente) => a.tipo === b.tipo && a.id === b.id;

function MapaDeRisco() {
  const { porId, rodovias, trechos } = useDados();
  // a seleção e o filtro moram na URL (?trecho=101-200, ?rodovia=SC-401, ?rede=sc): o link pode ser compartilhado
  const params = useSearchParams();
  const trechoId = params.get("trecho");
  const rodoviaSel = params.get("rodovia");
  const nivel: Nivel = params.get("nivel") === "rodovia" || rodoviaSel ? "rodovia" : "trecho";
  const [filtro, setFiltro] = useParametro<FiltroDeRede>("rede", "todas", ["todas", "br", "sc"]);

  const [enquadrar, setEnquadrar] = useState<Enquadramento>(null);
  const semEnquadrar = useRef(false);
  const recentes = useRecentes<Recente>("recentes-mapa", mesmoRecente);

  const rodovia = rodovias.find((r) => r.rodovia === rodoviaSel) ?? null;
  const trechoIds = useMemo(
    () => (nivel === "trecho" ? (trechoId && porId[trechoId] ? [trechoId] : []) : (rodovia?.trecho_ids ?? [])),
    [nivel, trechoId, rodovia, porId],
  );
  const chaveSelecao = trechoIds.join(",");
  const { previsao, carregando, erro, probPorTrecho } = usePrevisao(trechoIds);

  const enquadrarTrechos = useCallback((ids: string[]) => {
    const coords = ids.flatMap((id) => porId[id]?.geometry.coordinates.flat() ?? []);
    if (coords.length) setEnquadrar({ chave: Date.now(), limites: limitesDe(coords) });
  }, [porId]);

  // escolheu na lista, na busca ou chegou pela URL: leva o mapa até lá (clique no próprio mapa não mexe na vista)
  useEffect(() => {
    if (!trechos || !chaveSelecao) return;
    if (semEnquadrar.current) {
      semEnquadrar.current = false;
      return;
    }
    enquadrarTrechos(chaveSelecao.split(","));
  }, [chaveSelecao, trechos, enquadrarTrechos]);

  // guarda a seleção nos recentes
  const { adicionar } = recentes;
  useEffect(() => {
    if (nivel === "trecho" && trechoId && porId[trechoId]) {
      adicionar({ tipo: "trecho", id: trechoId, rotulo: porId[trechoId].properties.rotulo });
    } else if (nivel === "rodovia" && rodovia) {
      adicionar({ tipo: "rodovia", id: rodovia.rodovia, rotulo: `${rodovia.rodovia} inteira` });
    }
  }, [nivel, trechoId, rodovia, porId, adicionar]);

  const escolherNivel = (n: Nivel) => atualizarUrl({ nivel: n === "rodovia" ? "rodovia" : null });
  const escolherTrecho = (id: string) => atualizarUrl({ trecho: id, rodovia: null, nivel: null });
  const escolherRodovia = (nome: string) => atualizarUrl({ rodovia: nome, trecho: null, nivel: "rodovia" });
  const limparSelecao = () => atualizarUrl({ trecho: null, rodovia: null });

  function cliqueNoTrecho(id: string) {
    semEnquadrar.current = true;
    // no nível "rodovia", clicar num trecho escolhe a rodovia inteira dele
    if (nivel === "rodovia") escolherRodovia(porId[id].properties.rodovia);
    else escolherTrecho(id);
  }

  const outrosRecentes = recentes.itens.filter((r) => !(r.tipo === "trecho" ? r.id === trechoId : r.id === rodoviaSel));
  const resumoOnde = nivel === "trecho"
    ? (trechoId && porId[trechoId]?.properties.rotulo) || "Nenhum trecho"
    : rodoviaSel ? `${rodoviaSel} inteira` : "Nenhuma rodovia";

  const barra = (
    <>
      <Passo numero={1} titulo="Rede de rodovias" resumo={ROTULO_REDE[filtro]}>
        <FiltroRede valor={filtro} onMudar={setFiltro} />
      </Passo>
      <Passo numero={2} titulo="Onde" resumo={resumoOnde} abertoNoCelular
        acao={chaveSelecao ? (
          <button type="button" onClick={limparSelecao} className={ESTILO.botaoSecundario} title="Limpar seleção">
            <X size={12} aria-hidden /> Limpar
          </button>
        ) : undefined}>
        {outrosRecentes.length > 0 && (
          <div className="mb-3 flex flex-wrap items-center gap-1.5">
            <History size={13} aria-label="Recentes" className="text-texto-fraco" />
            {outrosRecentes.map((r) => (
              <button key={`${r.tipo}-${r.id}`} type="button" className={ESTILO.chip(false)}
                onClick={() => (r.tipo === "trecho" ? escolherTrecho(r.id) : escolherRodovia(r.id))}>
                {r.rotulo}
              </button>
            ))}
            <button type="button" onClick={recentes.limpar} className="text-[11px] text-texto-fraco hover:text-texto">limpar</button>
          </div>
        )}
        <div className="mb-3">
          <Segmentado<Nivel> rotulo="Selecionar por" colunas={2} valor={nivel} onMudar={escolherNivel}
            opcoes={[
              { id: "trecho", conteudo: <><div className="flex items-center justify-center gap-1 font-semibold"><MapPin size={13} aria-hidden />Trecho</div><div className="text-[10px] font-normal text-texto-fraco">10 km na BR · rodovia no município na SC</div></> },
              { id: "rodovia", conteudo: <><div className="flex items-center justify-center gap-1 font-semibold"><Route size={13} aria-hidden />Rodovia inteira</div><div className="text-[10px] font-normal text-texto-fraco">toda a extensão em SC</div></> },
            ]} />
        </div>
        {nivel === "trecho"
          ? <SeletorTrecho filtro={filtro} selecionado={trechoId} onSelecionar={escolherTrecho} />
          : <SeletorRodovia filtro={filtro} selecionada={rodoviaSel} onSelecionar={escolherRodovia} />}
      </Passo>
      <PainelQuando numero={3} />
      <PainelClima numero={4} trechoIds={trechoIds} />
    </>
  );

  return (
    <LayoutMapa barra={barra} emCenario={Object.keys(probPorTrecho).length > 0} selecionou={chaveSelecao}
      cartao={<CartaoResultado tipo={nivel} previsao={previsao} carregando={carregando} erro={erro}
        trechoIds={trechoIds} onFocarTrecho={(id) => enquadrarTrechos([id])} />}
      mapa={<Mapa trechos={trechos} filtroRede={filtro} trechoSelecionado={nivel === "trecho" ? trechoId : null}
        probPorTrecho={probPorTrecho} enquadrar={enquadrar} onClicarTrecho={cliqueNoTrecho} />} />
  );
}

export default function Pagina() {
  // useSearchParams precisa de um Suspense no Next 15
  return (
    <Suspense>
      <MapaDeRisco />
    </Suspense>
  );
}
