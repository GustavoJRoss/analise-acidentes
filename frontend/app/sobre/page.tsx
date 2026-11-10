import { ExternalLink } from "lucide-react";
import type { Metadata } from "next";

import MetricasModelo from "@/components/MetricasModelo";

export const metadata: Metadata = { title: "Sobre os dados" };

const FONTES = [
  {
    nome: "PRF — Dados Abertos", url: "https://www.gov.br/prf/pt-br/acesso-a-informacao/dados-abertos/dados-abertos-da-prf",
    uso: "Acidentes nas rodovias federais (BRs) de 2017 a 2025, com km, coordenadas, data e horário.",
  },
  {
    nome: "RENAEST — Senatran", url: "https://dados.transportes.gov.br/dataset/renaest",
    uso: "Acidentes de todas as vias informados pelos Detrans. Usado para as rodovias estaduais de SC, de jan/2019 a mai/2026.",
  },
  {
    nome: "OpenStreetMap", url: "https://www.openstreetmap.org/copyright",
    uso: "Geometria das rodovias, nomes de vias (para localizar os endereços do RENAEST), rotas (OSRM) e busca (Nominatim).",
  },
  {
    nome: "IBGE — API de malhas", url: "https://servicodados.ibge.gov.br/api/docs/malhas",
    uso: "Limites dos municípios: cortam as rodovias estaduais em trechos e desenham a máscara do mapa.",
  },
  {
    nome: "DNIT — Fatores VMD e UPE por trecho",
    url: "https://www.gov.br/dnit/pt-br/rodovias/operacoes-rodoviarias/faixa-de-dominio",
    uso: "Volume médio diário de veículos (VMD) de cada segmento das BRs, levado para os trechos de 10 km.",
  },
  {
    nome: "Open-Meteo", url: "https://open-meteo.com/",
    uso: "Clima histórico (reanálise ERA5) de todos os dias, para treinar, e previsão do tempo de até 16 dias.",
  },
];

const PASSOS = [
  ["Acidentes", "Os registros da PRF (BRs) e do RENAEST (estaduais) viram uma contagem por trecho, dia e período de 6 h."],
  ["Localização das estaduais", "Em SC o RENAEST não tem coordenadas nem km: o endereço digitado é limpo (abreviações, grafias, texto cortado) e casado com as vias do OpenStreetMap no mesmo município. Ex.: \"ROD JOSE CARLOS DAUX\" e \"SC 401\" viram SC-401. Uma rua só vira rodovia se a maioria das vias com aquele nome no município faz parte dela."],
  ["Trechos", "BRs em trechos de 10 km; rodovias estaduais cortadas pelos limites municipais (a SC-401 em Florianópolis é um trecho). Entram também os trechos sem nenhum acidente registrado, para o modelo aprender o que é um trecho tranquilo."],
  ["Clima", "Chuva, nebulosidade e temperatura de todos os dias, com ou sem acidente — o clima registrado nos boletins só existe quando houve acidente e enviesaria o modelo."],
  ["Modelos", "Um HistGradientBoosting por rede, avaliado prevendo um período que não viu no treino. Na API, uma rota ou rodovia inteira combina os trechos: 1 − Π(1 − pᵢ)."],
];

export default function Sobre() {
  return (
    <main className="h-full overflow-y-auto">
      <article className="mx-auto max-w-3xl space-y-10 px-4 py-8 md:px-6">
        <header className="space-y-2">
          <h1 className="text-2xl font-bold tracking-tight text-texto">Sobre os dados</h1>
          <p className="text-texto-suave">
            Projeto de estudo que estima a chance de ocorrer ao menos um acidente num trecho de rodovia de Santa
            Catarina, num dia, período e clima escolhidos. É a chance de <i>algum</i> acidente no trecho, envolvendo
            qualquer veículo — não o risco individual de quem viaja.
          </p>
        </header>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-texto">Fontes</h2>
          <ul className="grid gap-3 sm:grid-cols-2">
            {FONTES.map((f) => (
              <li key={f.nome} className="rounded-2xl border border-borda bg-superficie p-4">
                <a href={f.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium text-primaria hover:underline">
                  {f.nome} <ExternalLink size={13} aria-hidden />
                </a>
                <p className="mt-1 text-sm text-texto-suave">{f.uso}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-texto">Como funciona</h2>
          <ol className="space-y-3">
            {PASSOS.map(([titulo, texto], i) => (
              <li key={titulo} className="flex gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-texto text-xs font-semibold text-superficie">{i + 1}</span>
                <div className="text-sm text-texto-suave"><b className="text-texto">{titulo}.</b> {texto}</div>
              </li>
            ))}
          </ol>
        </section>

        <section className="space-y-6">
          <h2 className="text-lg font-semibold text-texto">Modelos e resultados</h2>
          <MetricasModelo />
          <p className="text-sm text-texto-suave">
            Nos dois casos não há volume de tráfego: os modelos aprendem sobretudo <i>onde</i> e <i>quando</i> já
            aconteceram acidentes, e o clima muda pouco o resultado. Overpass, OSRM, Nominatim e Open-Meteo são
            serviços públicos gratuitos, com limite de uso.
          </p>
        </section>
      </article>
    </main>
  );
}
