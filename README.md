# Risco de acidentes nas BRs de Santa Catarina

Projeto de **análise de dados** construído a partir dos **dados abertos da Polícia Rodoviária Federal (PRF)**,
cruzados com dados de outras APIs públicas: OpenStreetMap (geometria das rodovias, rotas e busca de endereços) e
Open-Meteo (clima histórico e previsão do tempo).

Com esses dados foi treinado um modelo preditivo sobre os acidentes registrados em 2025 nas rodovias federais de
SC. A partir de um **trecho de 10 km de BR** (ou de uma **rota** entre dois pontos), de uma **data**, de um
**período do dia** e do **clima**, ele estima a probabilidade de ocorrer ao menos um acidente. Tudo isso pode ser
explorado numa interface web com mapa.

```
acidentes2025_todas_causas_tipos.csv   base da PRF (baixe do portal, veja "Fontes de dados"; fora do git)
previsao_acidentes_sc.ipynb            notebook de estudo (exploração e primeiro modelo)
backend/                               Python + FastAPI: dados, treino e API de previsão
frontend/                              Next.js + Leaflet/OpenStreetMap: interface
```

## Fontes de dados

### Base principal: acidentes da PRF

O arquivo `acidentes2025_todas_causas_tipos.csv` vem do portal de **Dados Abertos da PRF**:

- Portal: <https://www.gov.br/prf/pt-br/acesso-a-informacao/dados-abertos/dados-abertos-da-prf>
- Seção **Acidentes**, conjunto **"Agrupados por pessoa – Todas as causas e tipos de acidentes"**, ano **2025**.
- Cada linha é uma **pessoa envolvida** num acidente registrado pela PRF em rodovia federal, com data, horário,
  UF, BR, km, município, causa, tipo, condição meteorológica, coordenadas e estado físico dos envolvidos.
- Formato: CSV com separador `;`, decimal `,` e codificação `latin1`.

O arquivo tem cerca de 220 MB e **não está no repositório**. Para rodar o projeto, baixe o CSV de 2025 no portal
(vem compactado em `.zip`), extraia e coloque `acidentes2025_todas_causas_tipos.csv` na raiz desta pasta. O
projeto usa só os registros de **SC**.

### Dados complementares (APIs públicas)

| Fonte | Uso no projeto |
|---|---|
| [OpenStreetMap / Overpass API](https://overpass-api.de/) | Geometria das BRs em SC, para desenhar os trechos no mapa |
| [OSRM](https://project-osrm.org/) | Cálculo de rotas entre origem e destino |
| [Nominatim](https://nominatim.org/) | Busca de endereços (geocodificação) |
| [Open-Meteo](https://open-meteo.com/) | Clima histórico de 2025 (reanálise ERA5) para treinar o modelo e previsão do tempo de até 16 dias |
| Tiles do OpenStreetMap | Mapa base da interface |

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
.venv/bin/python -m scripts.preparar_dados   # CSV → parquet + geometria OSM + clima Open-Meteo (~2 min)
.venv/bin/python -m scripts.treinar          # treina, avalia e salva em artifacts/ (~15 s)
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Os downloads externos ficam em cache em `backend/artifacts/`. Para baixar tudo de novo, use
`python -m scripts.preparar_dados --forcar`.

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
| Dados | `backend/app/dados.py` | Filtra SC e passa de uma linha por pessoa para uma linha por acidente. Define o trecho (BR + faixa de 10 km) e o período do dia |
| Mapa | `backend/app/osm.py` | Baixa a geometria das BRs no Overpass/OSM. Cada ponto da via recebe o km do acidente mais próximo da mesma BR |
| Clima | `backend/app/clima.py` | Baixa chuva, nebulosidade e temperatura **de todos os dias** de 2025 no Open-Meteo, numa grade de 0,25° |
| Features | `backend/app/features.py` | Calendário (feriados, fim de semana, verão), período, localização, clima e histórico do trecho. É o **mesmo código** no treino e na API |
| Modelo | `backend/scripts/treinar.py` | HistGradientBoosting sobre trecho × dia × período (350 mil linhas). Avalia com split temporal (treina em jan–set, testa em out–dez) e depois retreina com o ano todo |
| API | `backend/app/main.py` | `/api/trechos`, `/api/prever`, `/api/rota` (OSRM), `/api/busca` (Nominatim), `/api/clima-previsto`, `/api/modelo` |

**Por que não usar o clima do CSV da PRF?** Esse campo só existe quando houve acidente. O modelo nunca veria
"dia de chuva sem acidente", e o resultado seria vazamento de informação. Por isso o clima vem do Open-Meteo,
medido em todos os dias.

## Resultados (teste out–dez/2025)

| Modelo | ROC-AUC | PR-AUC |
|---|---|---|
| HistGradientBoosting com clima (em uso) | 0,817 | 0,154 |
| HistGradientBoosting sem clima | 0,817 | 0,156 |
| Só o histórico do trecho no período | 0,805 | 0,146 |
| Chute aleatório | 0,5 | 0,023 |

## Limitações (também explicadas na interface)

- **Só um ano de dados** e **nenhum dado de tráfego**: o modelo aprende sobretudo *onde* os acidentes já
  aconteceram.
- **O clima quase não muda o resultado** e a chuva forte aparece *reduzindo* a chance de acidente no trecho. A
  explicação provável é que menos gente viaja com chuva. O alvo é "algum acidente no trecho", não o risco de
  cada motorista.
- Não há opção de neblina: o histórico do Open-Meteo (ERA5) praticamente não registra neblina.
- Só entram os trechos com ao menos um acidente em 2025. O km dos pontos do OSM é aproximado.
- Overpass, OSRM, Nominatim e Open-Meteo são serviços públicos gratuitos, com limite de uso. Para produção, use
  instâncias próprias ou planos pagos.

## Próximos passos

- Incluir 2017–2024 do portal da PRF, para ter sazonalidade real e trechos sem acidente.
- Incluir o volume de tráfego (VMDa do DNIT) por trecho.
- Criar um alvo de gravidade (acidente com vítima grave ou fatal).
