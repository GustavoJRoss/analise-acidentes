# Risco de acidentes nas rodovias de Santa Catarina

Projeto de **análise de dados** construído a partir de dados abertos de acidentes de trânsito: os da **Polícia
Rodoviária Federal (PRF)**, para as BRs, e os do **RENAEST/Senatran**, para as rodovias estaduais. Eles são
cruzados com outras fontes públicas: OpenStreetMap (geometria das rodovias, nomes de vias, rotas e busca de
endereços), IBGE (limites municipais), DNIT (volume de tráfego das BRs) e Open-Meteo (clima histórico e previsão
do tempo).

Há dois modelos preditivos, um para cada rede de rodovias:
- **BRs:** acidentes de 2017–2025 da PRF, em trechos de 10 km;
- **rodovias estaduais (SC-xxx):** acidentes de jan/2019 a mai/2026 do RENAEST, com a rodovia dentro de cada
  município como trecho.

A partir de um **trecho** (ou de uma **rota** entre dois pontos, que pode passar pelas duas redes), de uma
**data**, de um **período do dia** e do **clima**, eles estimam a probabilidade de ocorrer ao menos um acidente.
Tudo isso pode ser explorado numa interface web com mapa.

```
dados_externos/                        bases baixadas pelos scripts (PRF, RENAEST, IBGE, OSM, DNIT; fora do git)
previsao_acidentes_sc.ipynb            notebook de estudo (exploração e primeiro modelo)
estudo_eda_pca.ipynb                   estudo: exploratória, correlação, PCA e modelos com × sem PCA (BRs)
backend/                               Python + FastAPI: dados, treino e API de previsão
frontend/                              Next.js + Leaflet/OpenStreetMap: interface
```

## Fontes de dados

### Base principal: acidentes da PRF

Os arquivos `acidentes{ano}_todas_causas_tipos.csv` de **2017 a 2025** vêm do portal de **Dados Abertos da PRF**:

- Portal: <https://www.gov.br/prf/pt-br/acesso-a-informacao/dados-abertos/dados-abertos-da-prf>
- Seção **Acidentes**, conjunto **"Agrupados por pessoa – Todas as causas e tipos de acidentes"**, um por ano.
- Cada linha é uma **pessoa envolvida** num acidente registrado pela PRF em rodovia federal, com data, horário,
  UF, BR, km, município, causa, tipo, condição meteorológica, coordenadas e estado físico dos envolvidos.
- Formato: CSV com separador `;`, decimal `,` e codificação `latin1`.

Os arquivos (10–14 MB cada, compactados) ficam no Google Drive da PRF. `scripts.preparar_dados` baixa todos
sozinho, com o `gdown`, para `dados_externos/prf/`; os IDs estão em `backend/app/config.py` (`IDS_DRIVE_PRF`).
Se o Google Drive bloquear o download, o erro explica o que fazer: baixe o ZIP do ano no portal e coloque em
`dados_externos/prf/`. Um `acidentes2025_todas_causas_tipos.csv` na raiz do projeto também é aceito. O projeto
usa só os registros de **SC**.

### Dados complementares (APIs públicas)

| Fonte | Uso no projeto |
|---|---|
| [OpenStreetMap / Overpass API](https://overpass-api.de/) | Geometria das BRs e rodovias estaduais em SC e nomes de todas as vias (para casar os endereços do RENAEST) |
| [IBGE – API de malhas](https://servicodados.ibge.gov.br/api/docs/malhas) | Limites dos municípios (trechos estaduais e máscara do mapa) |
| [OSRM](https://project-osrm.org/) | Cálculo de rotas entre origem e destino |
| [Nominatim](https://nominatim.org/) | Busca de endereços (geocodificação) |
| [DNIT – Fatores VMD e UPE por trecho](https://www.gov.br/dnit/pt-br/rodovias/operacoes-rodoviarias/faixa-de-dominio) | Volume médio diário (VMD) de cada segmento SNV das BRs, lido do PDF e levado para os trechos de 10 km |
| [Open-Meteo](https://open-meteo.com/) | Clima histórico (reanálise ERA5) para treinar os modelos e previsão do tempo de até 16 dias |
| Tiles do OpenStreetMap | Mapa base da interface (no tema escuro, os mesmos tiles invertidos por CSS) |

### Rodovias estaduais: RENAEST

O [RENAEST/Senatran](https://dados.transportes.gov.br/dataset/renaest) reúne acidentes de todas as vias
(municipais, estaduais e federais) informados pelos Detrans. É baixado automaticamente: um ZIP de cerca de
530 MB, guardado em `dados_externos/`, fora do git.

Em SC, porém, não vêm coordenadas, km, tipo de rodovia nem clima. A localização disponível é o município e o nome
da via, em texto livre. Por isso o projeto limpa esse nome (`backend/app/vias.py`) e o casa com as vias do
OpenStreetMap no mesmo município (`backend/app/renaest.py`). Assim, por exemplo, "RODOVIA JOSE CARLOS DAUX",
"SC 401" e "ROD GOV ADERBAL RAMOS DA SILV" passam a contar todos como SC-401.

Cerca de 90% dos acidentes casam com uma via. Os que não casam ficam sem via: nenhum recebe rodovia por chute.
Uma rua casada pelo nome só herda o código de rodovia se a maioria das vias do OSM com esse nome no município
faz parte da rodovia, ou se o nome oficial é "Rodovia …". Assim, uma rua inteira não vira SC-xxx porque um
único segmento dela é rodovia.

Os dados do OpenStreetMap são © colaboradores do OpenStreetMap, sob licença ODbL. Os dados do Open-Meteo estão
sob CC BY 4.0.

## Como rodar

Pré-requisitos: Python **3.12+** e Node 20+ com pnpm. O Python 3.9 que vem com o macOS não consegue abrir
conexão HTTPS com o Overpass e o OSRM.

### 1. Backend: preparar os dados, treinar e subir a API

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
# BRs (PRF)
.venv/bin/python -m scripts.preparar_dados         # PRF 2017–2025 → parquet + geometria OSM + VMD DNIT + clima
.venv/bin/python -m scripts.treinar                # treina, avalia e salva em artifacts/ (~15 s)
# rodovias estaduais (RENAEST) — opcional: sem isso o app mostra só as BRs
.venv/bin/python -m scripts.preparar_estaduais     # baixa RENAEST/IBGE/OSM, casa endereços, clima 2019–2026
.venv/bin/python -m scripts.treinar --rede sc      # salva em artifacts/estaduais/
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Os downloads ficam em cache: o clima em `backend/artifacts/` (por ano e por célula, compartilhado entre as
redes) e a PRF, o RENAEST, o IBGE, o DNIT e as vias do OSM em `dados_externos/`. Para baixar tudo de novo, use
`--forcar` no script de preparação.

`python -m scripts.relatorio_dados --comparar` mostra a qualidade dos dados (acidentes por ano, casamento de
endereços, trechos sem acidente, cobertura do clima) e as métricas de cada versão em
`artifacts/historico_metricas/`.

O clima de vários anos passa do limite por minuto do Open-Meteo gratuito. O script espera e continua sozinho. Se
ele parar, rode de novo: os lotes já baixados ficam guardados.

Testes: `.venv/bin/python -m pytest`. Para rodar sem chamar os serviços do OSM, acrescente `-m "not externo"`.

### 2. Frontend

```bash
cd frontend
pnpm install
pnpm dev        # http://localhost:3000
```

O Next repassa `/api/*` para o backend (veja `next.config.ts` e `BACKEND_URL` em `.env.example`), por isso não
é preciso configurar CORS.

## Como funciona

| Etapa | Onde | O que faz |
|---|---|---|
| Dados PRF | `backend/app/dados.py` | Baixa 2017–2025, filtra SC e passa de uma linha por pessoa para uma linha por acidente. Valida datas e coordenadas. Define o trecho (BR + faixa de 10 km) e o período do dia |
| Dados RENAEST | `backend/app/renaest.py`, `backend/app/vias.py` | Baixa o RENAEST e separa SC. Limpa o endereço digitado e o casa com uma via do OSM no mesmo município (código no texto, nome, nome sem o tipo, prefixo de texto cortado, nome parecido) |
| Mapa | `backend/app/osm.py` | BRs: pontos da via a até 300 m de um acidente recebem o km dele, e o km dos pontos entre eles é interpolado. Estaduais: cada rodovia é cortada pelos limites municipais. Nas duas redes entram também trechos sem nenhum acidente |
| Tráfego | `backend/app/trafego.py` | Lê o PDF de VMD do DNIT (SC) e calcula o VMD de cada trecho de 10 km, ponderado pela extensão |
| Clima | `backend/app/clima.py` | Baixa chuva, nebulosidade e temperatura **de todos os dias** no Open-Meteo, numa grade de 0,25° |
| Features | `backend/app/features.py` | Calendário (feriados, fim de semana, verão, pandemia), período, localização, clima, histórico do trecho (até o dia anterior: taxa e acidentes nos últimos 12 meses), VMD (BRs) e nível de notificação do RENAEST (estaduais). É o **mesmo código** no treino e na API |
| Modelos | `backend/scripts/treinar.py` | HistGradientBoosting sobre trecho × dia × período, um por rede, com split temporal. Os 180 primeiros dias ficam fora do treino (histórico curto demais) |
| API | `backend/app/main.py`, `backend/app/modelo.py` | `/api/trechos`, `/api/prever` (combina as duas redes numa rota), `/api/rota` (OSRM), `/api/busca` (Nominatim), `/api/clima-previsto`, `/api/modelo` |

**Por que não usar o clima do CSV da PRF?** Esse campo só existe quando houve acidente. O modelo nunca veria
"dia de chuva sem acidente", e o resultado seria vazamento de informação. Por isso o clima vem do Open-Meteo,
medido em todos os dias.

## Resultados

**BRs** (PRF; 249 trechos; treina em jul/2017–dez/2024 e testa em 2025):

| Modelo | ROC-AUC | PR-AUC |
|---|---|---|
| HistGradientBoosting com clima (em uso) | 0,825 | 0,145 |
| HistGradientBoosting sem clima | 0,825 | 0,144 |
| Só o histórico do trecho no período | 0,818 | 0,135 |
| Chute aleatório | 0,5 | 0,021 |

**Rodovias estaduais** (RENAEST; 443 trechos rodovia × município; treina em jul/2019–mai/2025 e testa em
jun/2025–mai/2026):

| Modelo | ROC-AUC | PR-AUC |
|---|---|---|
| HistGradientBoosting com clima (em uso) | 0,896 | 0,328 |
| HistGradientBoosting sem clima | 0,895 | 0,328 |
| Só o histórico do trecho no período | 0,894 | 0,315 |
| Chute aleatório | 0,5 | 0,029 |

Os números não são diretamente comparáveis com as versões anteriores (1 ano de PRF, só trechos com acidente),
porque o período de teste e o universo de trechos mudaram. A evolução de cada mudança está em
`artifacts/historico_metricas/`.

Com 2017–2025, a chuva forte passou a *aumentar* um pouco a chance prevista nas duas redes. Ainda assim, o clima
não melhora as métricas, nem quando o teste é restrito a noites, verão ou dias de chuva
(`clima_por_subconjunto` em `metricas.json`). O VMD do DNIT também quase não pesa: com nove anos de histórico,
a taxa de acidentes do trecho já carrega o efeito do tráfego.

## Interface

| Página | O que faz |
|---|---|
| Mapa de risco (`/`) | Filtra por rede (todas, BRs, estaduais) e escolhe um **trecho** ou a **rodovia inteira**. Mostra a probabilidade no cenário (data, período, clima) e o que mais pesa. A seleção fica na URL (`?trecho=…`, `?rodovia=…`) |
| Planejar viagem (`/viagem`) | Rota origem → destino (OSRM), com os trechos de BR e estaduais da viagem na ordem |
| Rankings (`/rankings`) | Rodovias ou trechos com mais acidentes, filtráveis por rede, município e busca. Cada linha abre no mapa |
| Sobre os dados (`/sobre`) | Fontes, como funciona, métricas dos dois modelos e limitações |

O tema claro/escuro segue o sistema e pode ser trocado no header. A escolha fica salva no navegador.

## Limitações (também explicadas na interface)

- Os modelos aprendem sobretudo *onde* e *quando* os acidentes já aconteceram. O ganho sobre a regra simples
  "histórico do trecho no período" é pequeno.
- **VMD de uma única data:** o volume de tráfego do DNIT é fixo por trecho e não varia com o dia ou a época do
  ano. Não existe VMD para as rodovias estaduais.
- **Rodovias estaduais sem posição exata:** em SC o RENAEST não traz coordenadas nem km. O trecho é a rodovia
  inteira dentro do município, e o local vem de um endereço digitado e casado por nome. Um trecho sem acidente
  pode ser só um endereço que não casou.
- **Notificação do RENAEST varia** (queda em 2024): o modelo recebe o nível de notificação dos 180 dias
  anteriores. Na API, vale o último nível conhecido.
- **Histórico fixo na API:** para qualquer data escolhida, a API usa o histórico do trecho no fim da base. Por
  isso a janela recente é de 12 meses, que muda pouco de um mês para outro.
- As duas bases contam acidentes de formas diferentes: o RENAEST inclui muitos registros sem vítima. Por isso as
  probabilidades das duas redes não são diretamente comparáveis entre si.
- Não há opção de neblina: o histórico do Open-Meteo (ERA5) praticamente não registra neblina.
- Nas BRs, todo trecho de 10 km com geometria teve algum acidente em 2017–2025. Os "trechos seguros" aparecem
  como anos e dias sem acidente, não como trechos sem nenhum.
- O km dos pontos do OSM é aproximado (interpolado entre acidentes). Feriados estaduais e municipais não entram.
- Overpass, OSRM, Nominatim e Open-Meteo são serviços públicos gratuitos, com limite de uso. Para produção, use
  instâncias próprias ou planos pagos.

## Próximos passos

- Criar um alvo de gravidade (acidente com vítima grave ou fatal).
- Incluir a PRF de 2026 (já publicada no portal) e atualizar o VMD do DNIT quando sair nova versão.
- Usar o km escrito no endereço do RENAEST (12% dos acidentes estaduais) para dividir as rodovias estaduais
  longas em trechos menores.
