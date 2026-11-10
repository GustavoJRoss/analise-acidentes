"use client";

import { ArrowDown, ArrowUp, ChevronRight, MapPin, RotateCw, Route } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { ESTILO, Segmentado } from "@/components/paineis/base";
import FiltroRede, { type FiltroDeRede, passaNoFiltro } from "@/components/paineis/FiltroRede";
import { useDados } from "@/lib/contexto";
import { capitalizar, corHistorico, decimal } from "@/lib/formato";
import { semAcentos } from "@/lib/texto";
import type { Rede } from "@/lib/tipos";
import { useParametro } from "@/lib/url";

type Nivel = "rodovias" | "trechos";
type Ordem = "acidentes_ano" | "densidade" | "mortos" | "extensao_km";
type Direcao = "desc" | "asc";

interface Linha {
  chave: string;
  nome: string;
  rede: Rede;
  municipios: string[];
  extensao_km: number;
  acidentes_ano: number;
  densidade: number;
  mortos: number;
  href: string;
}

const POR_PAGINA = 50;
const FONTE: Record<Rede, string> = { br: "PRF · 2025", sc: "RENAEST · média 2019–2025" };
const ORDENS: { id: Ordem; rotulo: string }[] = [
  { id: "acidentes_ano", rotulo: "Acidentes/ano" },
  { id: "densidade", rotulo: "Por 10 km/ano" },
  { id: "mortos", rotulo: "Mortes" },
  { id: "extensao_km", rotulo: "Extensão" },
];

function SeloRede({ rede }: { rede: Rede }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
      rede === "br" ? "bg-superficie-3 text-texto-suave" : "bg-violet-100 text-violet-800 dark:bg-violet-500/15 dark:text-violet-300"
    }`}>
      {rede === "br" ? "Federal" : "Estadual"}
    </span>
  );
}

function BarraDensidade({ valor, max }: { valor: number; max: number }) {
  return (
    <span className="flex items-center gap-2">
      <span className="relative h-1.5 w-16 overflow-hidden rounded-full bg-superficie-2">
        <span className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${Math.min(valor / max, 1) * 100}%`, background: corHistorico(valor) }} />
      </span>
      <span className="tabular-nums">{decimal(valor)}</span>
    </span>
  );
}

/** Cabeçalho que ordena ao clicar (clicar de novo inverte a direção). */
function Cabecalho({ id, rotulo, ordem, direcao, onOrdenar, direita }: {
  id: Ordem; rotulo: string; ordem: Ordem; direcao: Direcao; onOrdenar: (o: Ordem) => void; direita?: boolean;
}) {
  const ativa = ordem === id;
  const Seta = direcao === "desc" ? ArrowDown : ArrowUp;
  return (
    <th className={`px-4 py-2.5 font-medium ${direita ? "text-right" : ""}`}
      aria-sort={ativa ? (direcao === "desc" ? "descending" : "ascending") : "none"}>
      <button type="button" onClick={() => onOrdenar(id)}
        className={`inline-flex items-center gap-1 rounded hover:text-texto ${ativa ? "text-texto" : ""}`}>
        {rotulo}
        <Seta size={12} aria-hidden className={ativa ? "" : "opacity-0"} />
      </button>
    </th>
  );
}

function Rankings() {
  const { trechos, rodovias, temEstaduais, erro, recarregar } = useDados();
  const router = useRouter();
  // filtros na URL: o link compartilhado abre o mesmo ranking
  const [nivel, setNivel] = useParametro<Nivel>("ver", "rodovias", ["rodovias", "trechos"]);
  const [filtro, setFiltro] = useParametro<FiltroDeRede>("rede", "todas", ["todas", "br", "sc"]);
  const [municipio, setMunicipio] = useParametro<string>("municipio", "");
  // o texto digitado fica num estado local (cursor estável) e vai para a URL com um pequeno atraso
  const [buscaUrl, setBuscaUrl] = useParametro<string>("q", "");
  const [busca, setBusca] = useState(buscaUrl);
  const [ordem, setOrdem] = useParametro<Ordem>("ordem", "acidentes_ano", ORDENS.map((o) => o.id));
  const [direcao, setDirecao] = useParametro<Direcao>("dir", "desc", ["desc", "asc"]);
  const [limite, setLimite] = useState(POR_PAGINA);

  useEffect(() => setLimite(POR_PAGINA), [nivel, filtro, municipio, busca, ordem, direcao]);
  useEffect(() => {
    const t = setTimeout(() => setBuscaUrl(busca.trim()), 300);
    return () => clearTimeout(t);
  }, [busca, setBuscaUrl]);

  function ordenar(o: Ordem) {
    if (o === ordem) setDirecao(direcao === "desc" ? "asc" : "desc");
    else {
      setOrdem(o);
      setDirecao("desc");
    }
  }

  const linhas = useMemo<Linha[]>(() => {
    if (nivel === "rodovias") {
      return rodovias.map((r) => ({
        chave: r.rodovia, nome: r.rodovia, rede: r.rede, municipios: r.municipios, extensao_km: r.extensao_km,
        acidentes_ano: r.acidentes_ano, densidade: r.densidade, mortos: r.mortos,
        href: `/?rodovia=${encodeURIComponent(r.rodovia)}`,
      }));
    }
    return (trechos?.features ?? []).map(({ properties: t }) => ({
      chave: t.trecho_id, nome: t.rotulo, rede: t.rede, municipios: [capitalizar(t.municipio)],
      extensao_km: t.comprimento_km, acidentes_ano: t.acidentes_ano, densidade: t.densidade, mortos: t.mortos,
      href: `/?trecho=${encodeURIComponent(t.trecho_id)}`,
    }));
  }, [nivel, rodovias, trechos]);

  const municipios = useMemo(
    () => [...new Set(linhas.flatMap((l) => l.municipios))].sort((a, b) => a.localeCompare(b, "pt-BR")),
    [linhas],
  );

  const filtradas = useMemo(() => {
    const q = semAcentos(busca.trim().toLowerCase());
    const sinal = direcao === "desc" ? -1 : 1;
    return linhas
      .filter((l) => passaNoFiltro(l.rede, filtro)
        && (!municipio || l.municipios.includes(municipio))
        && (!q || semAcentos(`${l.nome} ${l.municipios.join(" ")}`.toLowerCase()).includes(q)))
      .sort((a, b) => sinal * (a[ordem] - b[ordem]));
  }, [linhas, filtro, municipio, busca, ordem, direcao]);

  const visiveis = filtradas.slice(0, limite);
  const maxDensidade = Math.max(...filtradas.map((l) => l.densidade), 1);
  const cidades = (l: Linha) => l.municipios.length > 3
    ? `${l.municipios.slice(0, 3).join(", ")} +${l.municipios.length - 3}` : l.municipios.join(", ");
  const temFiltro = filtro !== "todas" || municipio || busca;

  return (
    <main className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl space-y-5 px-4 py-6 md:px-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-texto">Rankings</h1>
          <p className="mt-1 text-sm text-texto-suave">
            Onde mais acontecem acidentes nas rodovias de SC. Clique numa linha para abrir no mapa de risco.
          </p>
        </div>

        {erro && (
          <div className={`flex items-start gap-3 ${ESTILO.erro}`}>
            <span className="flex-1">{erro}</span>
            <button type="button" onClick={recarregar} className={ESTILO.botaoSecundario}>
              <RotateCw size={12} aria-hidden /> Tentar de novo
            </button>
          </div>
        )}

        {temEstaduais && filtro === "todas" && (
          <p className={ESTILO.aviso}>
            <b>Compare dentro da mesma rede.</b> As BRs usam os registros da PRF de 2025; as estaduais, a média
            2019–2025 do RENAEST (informado pelo Detran), que inclui muitos acidentes sem vítima. As duas fontes contam
            acidentes de formas diferentes.
          </p>
        )}

        <div className="grid gap-3 rounded-2xl border border-borda bg-superficie p-4 md:grid-cols-[1fr_1.4fr] lg:grid-cols-[0.9fr_1.3fr_1fr_1fr]">
          <div>
            <div className={`mb-1.5 ${ESTILO.rotuloSecao}`}>Ver por</div>
            <Segmentado<Nivel> rotulo="Nível" colunas={2} valor={nivel} onMudar={setNivel}
              opcoes={[
                { id: "rodovias", conteudo: <span className="flex items-center justify-center gap-1"><Route size={13} aria-hidden />Rodovias</span> },
                { id: "trechos", conteudo: <span className="flex items-center justify-center gap-1"><MapPin size={13} aria-hidden />Trechos</span> },
              ]} />
          </div>
          <div>
            <div className={`mb-1.5 ${ESTILO.rotuloSecao}`}>Rede</div>
            <FiltroRede valor={filtro} onMudar={setFiltro} />
          </div>
          <label className="block">
            <span className={`mb-1.5 block ${ESTILO.rotuloSecao}`}>Município</span>
            <select value={municipio} onChange={(e) => setMunicipio(e.target.value)} className={`w-full ${ESTILO.campo}`}>
              <option value="">Todos</option>
              {municipios.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </label>
          <label className="block">
            <span className={`mb-1.5 block ${ESTILO.rotuloSecao}`}>Buscar</span>
            <input type="search" value={busca} onChange={(e) => setBusca(e.target.value)}
              placeholder="BR-101, SC-401…" className={`w-full ${ESTILO.campo}`} />
          </label>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm text-texto-suave">
            {filtradas.length.toLocaleString("pt-BR")} {nivel === "rodovias" ? "rodovias" : "trechos"}
            {temFiltro && (
              <button type="button" className="ml-2 text-xs text-primaria hover:underline"
                onClick={() => { setFiltro("todas"); setMunicipio(""); setBusca(""); }}>
                limpar filtros
              </button>
            )}
          </span>
          {/* no celular não há cabeçalho de tabela: a ordenação fica nos chips */}
          <div className="flex flex-wrap items-center gap-1.5 text-xs md:hidden">
            <span className="text-texto-fraco">Ordenar por</span>
            {ORDENS.map((o) => (
              <button key={o.id} type="button" onClick={() => ordenar(o.id)} className={`inline-flex items-center gap-1 ${ESTILO.chip(ordem === o.id)}`}>
                {o.rotulo}
                {ordem === o.id && (direcao === "desc" ? <ArrowDown size={11} aria-hidden /> : <ArrowUp size={11} aria-hidden />)}
              </button>
            ))}
          </div>
        </div>

        {/* tabela no desktop: a linha inteira abre no mapa; o nome continua sendo um link de verdade (teclado, nova aba) */}
        <div className="hidden overflow-hidden rounded-2xl border border-borda bg-superficie md:block">
          <table className="w-full text-left text-sm">
            <thead className="bg-superficie-2 text-xs text-texto-fraco">
              <tr>
                <th className="px-4 py-2.5 font-medium">#</th>
                <th className="px-4 py-2.5 font-medium">{nivel === "rodovias" ? "Rodovia" : "Trecho"}</th>
                <th className="px-4 py-2.5 font-medium">Municípios</th>
                <Cabecalho id="extensao_km" rotulo="Extensão" ordem={ordem} direcao={direcao} onOrdenar={ordenar} direita />
                <Cabecalho id="acidentes_ano" rotulo="Acidentes/ano" ordem={ordem} direcao={direcao} onOrdenar={ordenar} direita />
                <Cabecalho id="densidade" rotulo="Por 10 km/ano" ordem={ordem} direcao={direcao} onOrdenar={ordenar} />
                <Cabecalho id="mortos" rotulo="Mortes" ordem={ordem} direcao={direcao} onOrdenar={ordenar} direita />
                <th className="px-4 py-2.5 font-medium">Fonte</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-borda">
              {visiveis.map((l, i) => (
                <tr key={l.chave} onClick={() => router.push(l.href)}
                  className="group cursor-pointer text-texto-suave transition hover:bg-superficie-2">
                  <td className="px-4 py-2 tabular-nums text-texto-fraco">{i + 1}</td>
                  <td className="px-4 py-2">
                    <Link href={l.href} onClick={(e) => e.stopPropagation()}
                      className="flex items-center gap-2 whitespace-nowrap font-medium text-texto group-hover:text-primaria">
                      <SeloRede rede={l.rede} />{l.nome}
                    </Link>
                  </td>
                  <td className="max-w-56 truncate px-4 py-2" title={l.municipios.join(", ")}>{cidades(l)}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{decimal(l.extensao_km)} km</td>
                  <td className="px-4 py-2 text-right font-medium tabular-nums text-texto">{decimal(l.acidentes_ano)}</td>
                  <td className="px-4 py-2"><BarraDensidade valor={l.densidade} max={maxDensidade} /></td>
                  <td className="px-4 py-2 text-right tabular-nums">{l.mortos}</td>
                  <td className="px-4 py-2 text-xs text-texto-fraco">
                    <span className="flex items-center justify-between gap-2">
                      {FONTE[l.rede]}
                      <ChevronRight size={14} aria-hidden className="opacity-0 transition group-hover:opacity-100" />
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* cartões no celular */}
        <ul className="space-y-2 md:hidden">
          {visiveis.map((l, i) => (
            <li key={l.chave}>
              <Link href={l.href} className="block rounded-2xl border border-borda bg-superficie p-3 active:bg-superficie-2">
                <div className="flex items-center gap-2">
                  <span className="w-6 text-xs tabular-nums text-texto-fraco">{i + 1}</span>
                  <SeloRede rede={l.rede} />
                  <span className="min-w-0 flex-1 truncate font-medium text-texto">{l.nome}</span>
                  <span className="text-sm font-semibold tabular-nums text-texto">{decimal(l.acidentes_ano)}/ano</span>
                </div>
                <div className="mt-1.5 flex items-center justify-between gap-2 pl-8 text-xs text-texto-suave">
                  <span className="min-w-0 truncate">{cidades(l)} · {decimal(l.extensao_km)} km</span>
                  <BarraDensidade valor={l.densidade} max={maxDensidade} />
                </div>
              </Link>
            </li>
          ))}
        </ul>

        {filtradas.length > limite && (
          <div className="flex justify-center">
            <button type="button" onClick={() => setLimite((n) => n + POR_PAGINA)} className={ESTILO.botaoSecundario}>
              Mostrar mais {Math.min(POR_PAGINA, filtradas.length - limite)} de {(filtradas.length - limite).toLocaleString("pt-BR")} restantes
            </button>
          </div>
        )}

        {filtradas.length === 0 && trechos && (
          <p className="py-10 text-center text-sm text-texto-fraco">Nada encontrado com esses filtros.</p>
        )}
        {!trechos && !erro && <div className="h-64 animate-pulse rounded-2xl border border-borda bg-superficie" />}
      </div>
    </main>
  );
}

export default function Pagina() {
  return (
    <Suspense>
      <Rankings />
    </Suspense>
  );
}
