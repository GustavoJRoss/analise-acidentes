# N3 · Análise Preditiva: o que falta e como implementar

Análise feita em 23/11/2026 a partir do enunciado (`Trabalho_N3_Analise_Preditiva_MLOps.pdf`) e dos slides
(`Apresentacao_Trabalho_N3_MLOps_Catolica_SC.pdf`), comparados com o estado atual do repositório (commit `7f70820`).

## Resumo

O projeto atual é um bom **projeto de ML**: dados públicos tratados, features sem vazamento, divisão temporal,
métricas adequadas ao desbalanceamento e uma interface. A N3 pede outra coisa por cima: um **processo MLOps
automatizado** que, a cada ciclo agendado, recebe dados novos, vota features com três métodos, faz dois algoritmos
competirem, registra tudo no MLflow e decide sozinho se troca o modelo vigente.

**Nada da camada MLOps existe ainda** (sem MLflow, sem GitHub Actions, sem votação, sem segundo algoritmo no
pipeline, sem regra de promoção, sem `cycle_id`/`data_version`). Por outro lado, a parte mais difícil (dados e
features) está pronta e pode ser reaproveitada quase inteira.

Estimativa se entregasse hoje: **~2,5 / 10**. Falta algo como **75–80% do que é avaliado**, mas é trabalho de
engenharia previsível: **~4–6 dias de uma pessoa** (ou 2–3 dias com o grupo dividindo), mais **pelo menos 2 dias
corridos de agendamento rodando** para ter as execuções reais por `schedule`.

> ⚠️ O que tem prazo físico: a evidência de execução **pelo gatilho `schedule`** ("execução manual não substitui a
> agendada") e o **histórico de pelo menos dois ciclos**. O workflow precisa estar no `main` e rodando por cron
> alguns dias antes da entrega. Fazer isso primeiro.

## Situação por critério

| # | Critério (1,0 cada) | Hoje | O que já existe | O que falta |
|---|---|---|---|---|
| 1 | Problema, dados e avaliação | ~0,75 | Problema, alvo, fontes/licenças, PR-AUC justificada, divisão temporal (README e notebook) | Métrica e protocolo **em `config.yaml`**; separar **validação** (decisões de cada ciclo) de **teste** (reservado); explicar como dados novos chegam |
| 2 | ETL e engenharia de atributos | ~0,5 | `dados.py`, `features.py` (histórico até o dia anterior), clima por climatologia | Notebook `01_etl`; diagnóstico antes/depois; `Pipeline`/`ColumnTransformer` ajustado só no treino; incorporar lote novo **sem duplicar**; `data_version` |
| 3 | Três métodos de seleção | 0 | Importância por permutação (1 método, só no teste) | SelectKBest + importância de RF + RFE no notebook `02`, ajustados só no treino |
| 4 | Votação | 0 | — | Regra prévia (≥ 2 de 3, top-k, mínimo, desempate), tabela de votos, conjunto final usado pelos dois modelos |
| 5 | Dois algoritmos | ~0,25 | HGB vs linha de base ingênua; Regressão Logística testada só nos estudos | Modelo A e B no mesmo pipeline, mesmas features, mesma partição, mesma métrica |
| 6 | MLflow | 0 | `metricas.json` e `historico_metricas/` (rastreio manual) | Runs com params/métricas/artefatos/modelo, `cycle_id`, `data_version`; **persistir entre execuções** |
| 7 | Workflow único agendado | 0 | `rodar.sh` (local) | `.github/workflows/pipeline_mlops.yml` com `schedule` + `workflow_dispatch`, executando 01→04 em sequência |
| 8 | Eleição, promoção e previsões | ~0,25 | `scripts/prever.py` e a API preveem com o modelo | Comparação automática A×B, desafio contra o vigente com limiar, `models/modelo_vigente.json`, notebook `05` |
| 9 | Repositório, relatório, evidências | ~0,5 | README excelente, testes, Release com artefatos | `reports/relatorio_n3.pdf`, pasta `evidencias/`, README com execução agendada e consulta ao MLflow |
| 10 | Recurso adicional | 0 | A interface web existe, mas não está ligada aos ciclos | Ver sugestão abaixo |

## Decisões de desenho (recomendadas)

### Escopo: só a rede **BR (PRF)**

A rede estadual depende de casar endereços do RENAEST (~530 MB) e de Overpass, o que é pesado e frágil para rodar em
CI. A rede BR usa artefatos pequenos já prontos: `acidentes.parquet` (2 MB, 74.572 acidentes 2017–2025),
`trechos.parquet` (249 trechos), `clima.parquet` (4 MB). Cabem no git e o runner não precisa baixar nada do
Google Drive (que costuma bloquear o `gdown`). A rede SC pode ser citada como extensão futura.

### Como "dados novos" chegam: **replay cronológico em lotes**

A PRF publica com atraso e de forma irregular, então esperar dados reais não gera ciclos a tempo. Solução honesta
e reprodutível, comum em trabalhos de MLOps:

- `data/raw/base_inicial.parquet`: acidentes de 2017 a **dez/2023**.
- `data/raw/lotes/2024-01.parquet` … `2024-12.parquet`: um lote por mês de 2024 (12 lotes ⇒ 12 ciclos possíveis).
- `data/raw/teste_reservado.parquet`: **2025 inteiro**, nunca usado em decisão; só reportado (avaliação final).
- `data/estado/lotes_consumidos.json`: quais lotes já entraram. Cada ciclo incorpora **o próximo lote pendente**
  (deduplicando por id do acidente) e gera `data_version = sha256` do conjunto consumido (ex.: `v2024-03-a1b2c3`).
- `cycle_id = <data>-<github.run_id>` (ou `local-<timestamp>` fora do CI).

O relatório deve dizer claramente que é uma simulação de chegada de dados e por quê. Se a PRF de 2026 for usada,
o mesmo `src/ingestao.py` aceita um arquivo real em `data/raw/lotes/` sem mudar nada.

### Protocolo de avaliação (fixo em `config.yaml`)

- **Métrica principal: PR-AUC** (`average_precision`), direção `maximize`. Justificativa já existe: 2% de
  positivos, acurácia não serve.
- Para um ciclo com dados até `D`: **treino** = tudo antes de `D − 6 meses`; **validação** = últimos 6 meses
  (`[D − 6m, D)`); **teste** = 2025, reservado.
- A×B e desafiante×vigente são comparados **na validação do ciclo atual**. O vigente foi treinado num ciclo anterior,
  com corte mais antigo, então também não viu essa janela: comparação justa e sem vazamento.
- Regra de promoção (em `config.yaml`): promover se `PR-AUC_desafiante ≥ PR-AUC_vigente + 0,002` **e** checagens de
  qualidade passarem (ROC-AUC ≥ 0,75; razão prevista/observada entre 0,8 e 1,25 — já existe `calibracao()` em
  `treinar.py`). Sem vigente (primeiro ciclo) ⇒ promove o vencedor.

### Seleção e votação de features (notebook 02)

Candidatas: as ~20 de `FEATURES["br"]` em `backend/app/features.py`. Tudo ajustado **só no treino do ciclo**, numa
amostra estratificada de ~200 mil linhas (a base tem ~3 milhões; RFE na base toda seria lento no runner).

| Método | Implementação | Voto |
|---|---|---|
| SelectKBest | `mutual_info_classif` (captura não linearidade; categóricas via `OrdinalEncoder`) | top-k |
| Random Forest | `RandomForestClassifier(n_estimators=200, max_depth=12, class_weight="balanced")`, `feature_importances_` | top-k |
| RFE | `RFE(LogisticRegression(class_weight="balanced"), n_features_to_select=k)` sobre dados escalados/one-hot agregados por feature original | top-k |

Regra (fixada no `config.yaml` antes de rodar): `k = 10`; eleita se tiver **≥ 2 votos**; se ficarem menos de
`min_features = 6`, completa pela **média dos rankings** (desempate também pela média). Saída: tabela de votos
(feature × método, ranking e score), lista final, tudo logado no MLflow como params + `votacao.csv`.

Observação útil para o relatório: `taxa_historica_periodo` e `acid_ult_365d` provavelmente ganham 3 votos, e as de
clima tendem a cair, o que confirma a conclusão 3 do README (clima quase não acrescenta). Bom ponto de discussão.

### Competição (notebook 03)

- **Modelo A — Regressão Logística**: `Pipeline(ColumnTransformer[SimpleImputer + StandardScaler para numéricas,
  OneHotEncoder(handle_unknown="ignore") para categóricas], LogisticRegression(class_weight="balanced", max_iter=1000))`.
- **Modelo B — HistGradientBoosting**: o `novo_modelo()` atual de `treinar.py` (com restrição monotônica), dentro de
  um `Pipeline` com o mesmo pré-processamento de categorias.
- Mesmas features eleitas, mesma partição, `random_state` fixo. Cada um vira um run MLflow com `cycle_id`,
  `data_version`, `papel=candidato`, params, métricas de validação (PR-AUC, ROC-AUC, Brier, calibração, top-10%) e o
  pipeline serializado (`mlflow.sklearn.log_model`). Como o pré-processamento fica **dentro do Pipeline**, o modelo
  serializado já carrega as transformações e a lista de features, como o enunciado exige.

### Promoção (notebook 04) e manifesto

`src/promocao.py` lê as métricas dos dois runs do ciclo, elege o vencedor, carrega o vigente (de
`models/vigente/`), avalia o vigente na **validação deste ciclo**, aplica a regra e grava
`models/modelo_vigente.json`:

```json
{
  "cycle_id": "2026-11-25-1234567",
  "data_version": "v2024-03-a1b2c3",
  "decisao": "promovido",             // ou "mantido"
  "motivo": "PR-AUC 0.1512 ≥ 0.1478 + 0.002; checagens ok",
  "modelo": {"algoritmo": "HistGradientBoosting", "run_id": "…", "caminho": "models/vigente/model"},
  "features": ["taxa_historica_periodo", "acid_ult_365d", "…"],
  "metrica": {"nome": "pr_auc", "desafiante": 0.1512, "vigente_anterior": 0.1478},
  "historico": [ … decisões anteriores … ]
}
```

Modelos anteriores são preservados em `models/historico/<cycle_id>/` (e no MLflow). Um run `papel=decisao` registra
a decisão. Se qualquer notebook falhar, o `nbconvert` sai com erro e o workflow para antes do 04: **não há promoção
indevida**.

### MLflow persistente entre execuções

O runner do GitHub é descartável. Recomendo **versionar o estado no próprio repositório**:

- `mlflow.set_tracking_uri("sqlite:///mlops/mlflow.db")` e artefatos em `mlops/mlartifacts/` (cada modelo tem
  < 1 MB; 12 ciclos × 2 modelos ≈ 20 MB, aceitável).
- No fim do workflow: `git add mlops/ models/ data/estado/ evidencias/` → commit `"ciclo <cycle_id> [skip ci]"` →
  push (permissão `contents: write`). O próximo ciclo começa já com o vigente e o histórico.
- Além disso, `actions/upload-artifact` com notebooks executados, logs e `mlflow.db` (evidência baixável).
- Consulta: `mlflow ui --backend-store-uri sqlite:///mlops/mlflow.db` (documentar no README).

Alternativa sem commits automáticos: servidor MLflow gratuito no DagsHub (token em Secret). Funciona, mas cria
dependência externa e o professor precisaria de acesso; o sqlite versionado é mais auditável.

### Workflow único

```yaml
# .github/workflows/pipeline_mlops.yml
name: pipeline-mlops
on:
  schedule:
    - cron: "17 9 * * *"     # diário, 06:17 BRT; minuto "quebrado" porque o GitHub atrasa crons em :00
  workflow_dispatch:
permissions:
  contents: write
concurrency: { group: pipeline-mlops, cancel-in-progress: false }
jobs:
  ciclo:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: pip install -r requirements-mlops.txt
      - name: Identificadores do ciclo
        run: echo "CYCLE_ID=$(date -u +%Y%m%d)-${{ github.run_id }}" >> $GITHUB_ENV
      - name: 01 ETL
        run: jupyter nbconvert --to notebook --execute notebooks/01_etl.ipynb --output-dir evidencias/$CYCLE_ID
      - name: 02 Votação de features
        run: jupyter nbconvert --to notebook --execute notebooks/02_votacao_features.ipynb --output-dir evidencias/$CYCLE_ID
      - name: 03 Treino e competição
        run: jupyter nbconvert --to notebook --execute notebooks/03_treino_competicao.ipynb --output-dir evidencias/$CYCLE_ID
      - name: 04 Seleção e promoção
        run: jupyter nbconvert --to notebook --execute notebooks/04_selecao_promocao.ipynb --output-dir evidencias/$CYCLE_ID
      - name: 05 Previsões
        run: jupyter nbconvert --to notebook --execute notebooks/05_previsoes.ipynb --output-dir evidencias/$CYCLE_ID
      - name: Persistir estado
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add mlops models data/estado evidencias
          git commit -m "ciclo $CYCLE_ID (${{ github.event_name }}) [skip ci]" && git push
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: ciclo-${{ env.CYCLE_ID }}
          path: |
            evidencias/${{ env.CYCLE_ID }}
            mlops/mlflow.db
```

Os notebooks se comunicam por arquivos em caminhos fixos (`data/processed/ciclo_atual/…`) e pelo
`data/estado/ciclo_atual.json` (cycle_id, data_version, features eleitas, run_ids). O `github.event_name` entra no
MLflow como tag `gatilho=schedule|workflow_dispatch`, que é a prova pedida no critério 7.

## Estrutura proposta no repositório

Reaproveita `backend/app` (fonte única das features, usada também pela API) e acrescenta a estrutura do enunciado:

```
.github/workflows/pipeline_mlops.yml
config/config.yaml                  métrica, direção, protocolo, k, regra de votação, algoritmos, limiar
data/raw/                           base_inicial, lotes/AAAA-MM, teste_reservado (parquet, BR)
data/processed/                     gerado por ciclo (no .gitignore)
data/estado/                        lotes_consumidos.json, ciclo_atual.json
notebooks/01_etl.ipynb … 05_previsoes.ipynb
src/ingestao.py                     próximo lote, deduplicação, data_version
src/preprocessamento.py             montar_base() (vem de treinar.py), ColumnTransformer, splits
src/features.py                     3 métodos + votação
src/modelagem.py                    modelos A/B, avaliação, log no MLflow
src/promocao.py                     regra, manifesto, histórico de modelos
mlops/mlflow.db, mlops/mlartifacts/ estado MLflow versionado
models/modelo_vigente.json, models/vigente/, models/historico/
evidencias/<cycle_id>/              notebooks executados, votacao.csv, comparacao.csv, logs
reports/relatorio_n3.pdf
requirements-mlops.txt              pandas, numpy, scikit-learn, pyarrow, mlflow, nbconvert, ipykernel, pyyaml
```

`src/` importa de `backend/app` (`features.adicionar_calendario`, `adicionar_historico_treino`, `clima`), então não
há duplicação. A função `montar_base()` de `backend/scripts/treinar.py` deve ir para `src/preprocessamento.py` e ser
importada de volta pelo `treinar.py`.

Atenção de compatibilidade: o projeto usa **pandas 3.1 e numpy 2.5**. Conferir logo no início se a versão do MLflow
instalada aceita essas versões; se não, fixar a combinação que funciona em `requirements-mlops.txt`.

## Critério 10: sugestão

Precisa ser útil, integrado ao fluxo e demonstrado. Duas opções que conversam com o que o projeto já descobriu:

1. **Monitor de drift com alerta (recomendado).** Necessidade real: o README já mostra que trechos "mudam de
   patamar" de um ano para outro (BR-280 em Araquari) e que a notificação varia no tempo. A cada ciclo, comparar o
   lote novo com o treino: PSI das features eleitas, taxa de acidentes do lote vs. esperado pelo vigente, e lista
   dos trechos cuja taxa observada saiu do intervalo previsto. Se passar de um limiar (ex.: PSI > 0,2), o workflow
   escreve no **Job Summary** e **abre uma issue** no GitHub (`gh issue create`, já disponível no runner). Fica
   registrado no MLflow (`drift_psi_max`, `alerta=1`). Para provar que o alerta dispara, o notebook 05 roda o
   mesmo monitor sobre o mês de abr/2020 (pandemia, tráfego despencou) contra o treino de 2019: deve passar do
   limiar, e os lotes normais de 2024 não.
2. **Interface ligada ao modelo vigente.** A API passa a carregar o modelo de `models/modelo_vigente.json`, e a página
   "Sobre" mostra o ciclo atual, a decisão, a tabela de votos e o histórico de ciclos. Aproveita o frontend pronto,
   mas dá mais trabalho e é mais difícil de "provar" no relatório.

## Ordem de trabalho sugerida

| Ordem | Tarefa | Esforço | Quem pode pegar |
|---|---|---|---|
| 1 | Gerar `data/raw` (base inicial, 12 lotes de 2024, teste 2025) a partir dos parquets atuais; `config.yaml`; `src/ingestao.py` | 0,5 dia | dados |
| 2 | **Workflow mínimo** já agendado (01 que só ingere + MLflow loga `cycle_id`/`data_version` + commit do estado). Colocar no `main` e deixar o cron rodar | 0,5 dia | qualquer um |
| 3 | Notebook 01 + `src/preprocessamento.py` (diagnóstico antes/depois, splits treino/validação/teste) | 0,5–1 dia | dados |
| 4 | Notebook 02 + `src/features.py` (3 métodos, votação, log) | 1 dia | modelagem |
| 5 | Notebook 03 + `src/modelagem.py` (A/B, Pipelines, log no MLflow) | 0,5–1 dia | modelagem |
| 6 | Notebook 04 + `src/promocao.py` (regra, manifesto, histórico) e notebook 05 (previsões, comparação de ciclos) | 1 dia | modelagem |
| 7 | Critério 10 (drift + issue) | 0,5–1 dia | qualquer um |
| 8 | README (seção MLOps), `evidencias/`, prints do Actions e do MLflow, `reports/relatorio_n3.pdf` | 1 dia | apresentação |

Os passos 3–6 vão substituindo as etapas do workflow do passo 2 sem mudar o YAML, então o cron continua gerando
ciclos reais enquanto o resto é implementado. Na véspera da entrega, conferir: ≥ 2 execuções com gatilho
`schedule` sem erro, pelo menos uma decisão "promovido" e uma "mantido" (o replay de 2024 tende a produzir as duas),
e o MLflow abrindo localmente com todos os ciclos.

## Riscos

- **Cron do GitHub atrasa ou é pulado** em horários cheios, e é desativado após 60 dias sem atividade no repositório.
  Usar minuto quebrado e começar cedo.
- **Commit automático no `main`** pode conflitar com pushes do grupo. Usar `concurrency`, `git pull --rebase` antes do
  push, ou persistir numa branch própria (`mlops-estado`) que o workflow faz checkout no início.
- **Tempo do runner**: a base BR tem ~3 milhões de linhas (249 trechos × ~3.000 dias × 4 períodos). HGB e LR cabem
  em minutos nos 7 GB do runner; a seleção de features deve usar amostra.
- **O que o professor quer ver** é processo, não acurácia (slide 20). As decisões "mantido" são tão boas como
  evidência quanto as "promovido".
