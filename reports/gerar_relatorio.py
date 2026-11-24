"""Gera reports/relatorio_n3.pdf a partir do estado real do pipeline (manifesto, evidências e MLflow).

Uso (da raiz):  .venv/bin/python3.12 reports/gerar_relatorio.py
O workflow agendado roda este script ao fim de cada ciclo, então o relatório versionado sempre reflete o
último ciclo executado. Com MLOPS_SAIDA definido, lê o estado de outra pasta (ex.: .mlops-local).
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import pandas as pd  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,  # noqa: E402
                                TableStyle)

from src.comum import caminho, carregar_config, estado  # noqa: E402

REPO_URL = "https://github.com/GustavoJRoss/analise-acidentes"
INTEGRANTES = ["Gustavo Ross", "Kevin C. El Azar", "Guilherme Assis", "Bredley Bauer", "Gabriel Coelho",
               "Gustavo Haiduk"]
SAIDA = RAIZ / "reports" / "relatorio_n3.pdf"

# --- fontes: TTF com acentos e símbolos (≥, →, ×); sem elas, Helvetica e troca dos símbolos -------------------
FONTES = [("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
          ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
FONTE, FONTE_B, TTF = "Helvetica", "Helvetica-Bold", False
for normal, negrito in FONTES:
    if Path(normal).exists() and Path(negrito).exists():
        pdfmetrics.registerFont(TTFont("Corpo", normal))
        pdfmetrics.registerFont(TTFont("Corpo-B", negrito))
        pdfmetrics.registerFontFamily("Corpo", normal="Corpo", bold="Corpo-B", italic="Corpo", boldItalic="Corpo-B")
        FONTE, FONTE_B, TTF = "Corpo", "Corpo-B", True
        break


def t(s) -> str:
    """Texto seguro para a fonte em uso (e para o mini-HTML do Paragraph)."""
    s = "" if s is None else str(s)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if not TTF:
        for a, b in {"≥": "&gt;=", "≤": "&lt;=", "→": "-&gt;", "×": "x", "−": "-"}.items():
            s = s.replace(a, b)
    return s


VINHO = colors.HexColor("#7A1C35")
CINZA = colors.HexColor("#F3EFF0")
base = getSampleStyleSheet()
E = {
    "titulo": ParagraphStyle("titulo", parent=base["Title"], fontName=FONTE_B, fontSize=20, textColor=VINHO, leading=24),
    "sub": ParagraphStyle("sub", parent=base["Normal"], fontName=FONTE, fontSize=11, alignment=TA_CENTER, leading=15),
    "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName=FONTE_B, fontSize=14, textColor=VINHO,
                         spaceBefore=12, spaceAfter=6, keepWithNext=1),
    "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName=FONTE_B, fontSize=11.5, spaceBefore=8, spaceAfter=4,
                         keepWithNext=1),
    "p": ParagraphStyle("p", parent=base["BodyText"], fontName=FONTE, fontSize=9.5, leading=13.5, spaceAfter=5),
    "cel": ParagraphStyle("cel", parent=base["BodyText"], fontName=FONTE, fontSize=7.8, leading=9.6),
    "celb": ParagraphStyle("celb", parent=base["BodyText"], fontName=FONTE_B, fontSize=7.8, leading=9.6,
                           textColor=colors.white),
    "nota": ParagraphStyle("nota", parent=base["BodyText"], fontName=FONTE, fontSize=8, leading=10.5,
                           textColor=colors.HexColor("#555555")),
}


def P(texto, estilo="p"):
    return Paragraph(texto, E[estilo])


def tabela(linhas, larguras=None, cabecalho=True):
    dados = [[Paragraph(t(c) if not str(c).startswith("<b>") else str(c), E["celb" if (cabecalho and i == 0) else "cel"])
              for c in linha] for i, linha in enumerate(linhas)]
    tb = Table(dados, colWidths=larguras, repeatRows=1 if cabecalho else 0)
    estilo = [("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BBBBBB")),
              ("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA])]
    if cabecalho:
        estilo.append(("BACKGROUND", (0, 0), (-1, 0), VINHO))
    tb.setStyle(TableStyle(estilo))
    return tb


def bullets(itens):
    return [P("• " + i) for i in itens]


def ler_json(p: Path, padrao=None):
    return json.loads(p.read_text()) if p.exists() else padrao


def fmt(v, casas=4):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{v:.{casas}f}" if isinstance(v, float) else str(v)


NOMES = {"logistica": "A · Regressão Logística", "hist_gradient_boosting": "B · HistGradientBoosting"}
GATILHOS = {"schedule": "schedule", "workflow_dispatch": "manual", "local": "local"}


def gat(h) -> str:
    return GATILHOS.get(h.get("gatilho"), h.get("gatilho") or "—")


def demo_drift(cfg) -> dict:
    """Recalcula a demonstração do monitor (abr/2020 × abr/2024) a partir de data/raw."""
    from src import drift, ingestao, preprocessamento as pp
    trechos = pd.read_parquet(caminho(cfg["dados"]["trechos"]))
    clima = pd.read_parquet(caminho(cfg["dados"]["clima"]))
    acid = ingestao.acidentes_limpos(cfg, ingestao.lotes_disponiveis(cfg))
    b = pp.montar(pp.tratar(acid, trechos, acid["data"].max()), trechos, clima)
    out = {}
    for mes in ["2020-04", "2024-04"]:
        r = drift.monitorar(*drift.recorte_mensal(b, pd.Timestamp(mes + "-01")), pp.CANDIDATAS, cfg)
        out[mes] = r
    return out


def main():
    cfg = carregar_config()
    man = ler_json(estado(cfg, "modelos") / "modelo_vigente.json")
    if not man:
        sys.exit("Sem models/modelo_vigente.json: rode ao menos um ciclo antes de gerar o relatório.")
    hist = man["historico"]
    ultimo = hist[-1]
    ev = estado(cfg, "evidencias") / ultimo["cycle_id"]
    diag = ler_json(ev / "diagnostico.json", {})
    drift_ult = ler_json(ev / "drift.json", {})
    teste = ler_json(ev / "metricas_teste_2025.json", {})
    votacao = pd.read_csv(ev / "votacao.csv") if (ev / "votacao.csv").exists() else None
    agendados = [h for h in hist if h.get("gatilho") == "schedule"]
    gerado = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    s = []
    # ---------------------------------------------------------------- capa
    s += [Spacer(1, 3 * cm), P("Trabalho Avaliativo N3 · Análise Preditiva", "sub"), Spacer(1, 6),
          P("Pipeline MLOps para risco de acidentes nas rodovias federais de Santa Catarina", "titulo"),
          Spacer(1, 10),
          P("Votação de features, competição de modelos e atualização automatizada", "sub"), Spacer(1, 1.2 * cm),
          P("Católica de Santa Catarina · Engenharia de Software e Engenharia de Inteligência Artificial", "sub"),
          P("Prof. M. Sc. Rodrigo Hagstrom", "sub"), Spacer(1, 1 * cm),
          P("<b>Integrantes:</b> " + ", ".join(INTEGRANTES), "sub"), Spacer(1, 6),
          P(f"<b>Repositório:</b> {REPO_URL}", "sub"),
          P(f"Relatório gerado automaticamente em {gerado} a partir do ciclo <b>{t(ultimo['cycle_id'])}</b> "
            f"({len(hist)} ciclo(s) registrados, {len(agendados)} pelo gatilho schedule).", "sub"),
          PageBreak()]

    # ---------------------------------------------------------------- 1. problema e dados
    s += [P("1. Problema, dados e avaliação", "h1"),
          P("<b>Problema.</b> Classificação binária: haverá <b>ao menos um acidente</b> num trecho de 10 km de "
            "rodovia federal (BR) em Santa Catarina, num dia e num período de 6 horas (madrugada, manhã, tarde, "
            "noite)? A resposta orienta onde e quando concentrar fiscalização e atenção. "
            "<b>Unidade de observação:</b> trecho × dia × período (249 trechos). <b>Alvo:</b> "
            "<i>teve_acidente</i> (cerca de 2% de positivos)."),
          tabela([["Fonte", "Conteúdo", "Licença / acesso"],
                  ["PRF – Dados Abertos", "Acidentes 2017–2025, uma linha por pessoa envolvida", "Dados abertos do governo federal"],
                  ["Open-Meteo (ERA5)", "Chuva, nebulosidade e temperatura diárias por célula de ~25 km", "CC BY 4.0"],
                  ["DNIT", "Volume médio diário de veículos (VMD) por segmento", "Dados abertos do governo federal"],
                  ["OpenStreetMap", "Geometria das BRs para definir os trechos (inclusive os sem acidente)", "ODbL"]],
                 [3.2 * cm, 8.8 * cm, 5 * cm]),
          Spacer(1, 6),
          P("<b>Métrica principal: PR-AUC</b> (average precision), a maximizar. Com 2% de positivos, acurácia não "
            "informa nada (prever sempre \"sem acidente\" acerta 98%); a PR-AUC mede a qualidade da ordenação dos "
            "casos de maior risco. ROC-AUC, Brier, calibração e captura dos 10% de maior risco são reportados como "
            "apoio."),
          P("<b>Protocolo, definido antes do treino</b> (<i>config/config.yaml</i>): para um ciclo com dados até D, "
            "treino = tudo antes de D − 6 meses; validação = os 6 meses finais. Todas as decisões recorrentes "
            "(votação, A × B, desafiante × vigente) usam só treino e validação. <b>2025 é o teste reservado</b>: "
            "nunca participa de uma decisão e só é usado na avaliação final do notebook 05."),
          P("<b>Chegada de novos registros.</b> Replay cronológico de dados reais: a base inicial vai até dez/2023 e "
            "cada ciclo agendado incorpora o próximo mês de 2024 (<i>data/raw/lotes/AAAA-MM.parquet</i>), sem "
            "duplicar (chave id do acidente + id da pessoa). A PRF publica com atraso e de forma irregular; o replay "
            "permite demonstrar ciclos reais com dados reais. Um arquivo novo da PRF pode entrar como lote sem mudar "
            "o código."),
          P("<b>Limitações dos dados:</b> só acidentes registrados pela PRF; VMD de uma única data e ausente em "
            "parte dos trechos; clima numa grade de ~25 km; sem feriados municipais.")]

    # ---------------------------------------------------------------- 2. arquitetura
    s += [P("2. Arquitetura do fluxo único", "h1"),
          P("Um único workflow (<i>.github/workflows/pipeline_mlops.yml</i>) com gatilho <b>schedule</b> (todo dia às "
            "06:17 de Brasília) e <b>workflow_dispatch</b> (depuração) executa um ciclo inteiro, em sequência, num "
            "só job. Cada notebook é um passo: se algum falhar, o job para antes da promoção e nada é persistido."),
          tabela([["Passo", "Notebook / arquivo", "O que faz", "Código reutilizado"],
                  ["0", "pytest tests", "Testa as regras de votação, promoção, ingestão e drift", "tests/test_mlops.py"],
                  ["1", "01_etl.ipynb", "Próximo lote, cycle_id e data_version, diagnóstico, limpeza, base, divisão temporal, drift",
                   "src/ingestao.py, src/preprocessamento.py, src/drift.py, backend/app/dados.py"],
                  ["2", "02_votacao_features.ipynb", "Três métodos de seleção e votação", "src/features.py"],
                  ["3", "03_treino_competicao.ipynb", "Treina e avalia os modelos A e B", "src/modelagem.py"],
                  ["4", "04_selecao_promocao.ipynb", "Vencedor do ciclo, confronto com o vigente, promoção ou manutenção", "src/promocao.py"],
                  ["5", "05_previsoes.ipynb", "Previsões de 2025 com o vigente, comparação de ciclos, demonstração do drift", "src/modelagem.py, src/drift.py"],
                  ["6", "commit do estado", "Grava mlops/, models/, data/estado/, evidencias/ e reports/ no repositório", "workflow"],
                  ["7", "upload-artifact", "Publica evidências, manifesto e banco do MLflow como artefato baixável", "workflow"]],
                 [1.1 * cm, 3.6 * cm, 7.0 * cm, 5.3 * cm]),
          Spacer(1, 6),
          P("<b>Persistência entre execuções.</b> O executor do GitHub Actions é descartável; por isso o MLflow usa "
            "um banco sqlite (<i>mlops/mlflow.db</i>) e artefatos em <i>mlops/mlartifacts/</i>, commitados ao fim de "
            "cada ciclo junto com o modelo vigente e o registro dos lotes já consumidos. O ciclo seguinte começa do "
            "estado deixado pelo anterior. Todos os runs de um ciclo compartilham <b>cycle_id</b> e "
            "<b>data_version</b>. O modelo é salvo como <i>Pipeline</i> do scikit-learn, com o pré-processamento e "
            "a lista de features juntos, o que garante previsões consistentes."),
          PageBreak()]

    # ---------------------------------------------------------------- 3. ETL
    s += [P("3. ETL e engenharia de atributos", "h1"),
          P("Os lotes chegam <b>brutos</b>, como a PRF publica: uma linha por pessoa envolvida, tudo como texto, "
            "decimais com vírgula. O notebook 01 refaz o tratamento a cada ciclo. Números do último ciclo "
            f"(<i>{t(ultimo['cycle_id'])}</i>, data_version <i>{t(ultimo['data_version'])}</i>):")]
    bruto, limpo = diag.get("bruto", {}), diag.get("apos_tratamento", {})
    if bruto:
        s.append(tabela([["Diagnóstico dos dados brutos", "Valor"]] + [[k, v] for k, v in bruto.items()],
                        [10 * cm, 4 * cm]))
        s.append(Spacer(1, 4))
        s.append(tabela([["Após limpeza e tratamento", "Valor"],
                         ["Acidentes (uma linha por acidente)", limpo.get("linhas")],
                         ["Acidentes descartados", bruto.get("acidentes distintos", 0) - (limpo.get("linhas") or 0)],
                         ["ids duplicados", limpo.get("ids_duplicados")],
                         ["Coordenada fora de SC / trecho desconhecido",
                          f"{limpo.get('coordenada_fora_de_sc')} / {limpo.get('trecho_desconhecido')}"],
                         ["Outliers sinalizados (mais de 10 mortos)", limpo.get("outlier_mortos_gt_10")],
                         ["Período coberto", " a ".join(limpo.get("periodo_dados", []))]],
                        [10 * cm, 4 * cm]))
    s += [Spacer(1, 6), P("<b>Tratamentos e justificativas:</b>")]
    s += bullets([
        "Uma linha por acidente: vítimas somadas por acidente e tipo principal (ordem_tipo_acidente = 1), com "
        "desempate determinístico. O alvo é por acidente, não por pessoa.",
        "Descartados acidentes sem BR, km ou coordenada, ou com coordenada fora de SC: não é possível atribuí-los a "
        "um trecho.",
        "Datas em dois formatos (AAAA-MM-DD e DD/MM/AAAA, usado em anos antigos) padronizadas; datas inválidas "
        "interrompem o ciclo.",
        "Vítimas ausentes = 0 (a PRF deixa em branco quando não há). Outliers de vítimas são sinalizados, mas "
        "mantidos: são reais e o alvo é binário.",
        "Base completa trecho × dia × período, inclusive trechos e dias sem acidente, para não enviesar o modelo "
        "só para os trechos perigosos.",
        "Histórico do trecho (taxa geral, taxa no período, acidentes nos últimos 365 dias) calculado só até o dia "
        "anterior, sem vazamento; clima medido em todos os dias (Open-Meteo), não o campo de clima da PRF, que só "
        "existe quando houve acidente; calendário com feriados nacionais (inclusive móveis), véspera, verão e "
        "pandemia.",
        "Imputação (mediana), escala e codificação (one-hot ou ordinal) ficam dentro dos Pipeline/ColumnTransformer "
        "dos modelos e são ajustadas só no treino.",
    ])
    s.append(P("Dicionário completo dos 20 atributos candidatos: notebook 01, seção \"Dicionário de atributos\".", "nota"))

    # ---------------------------------------------------------------- 4. votação
    v = cfg["votacao"]
    s += [P("4. Três métodos de seleção e votação das features", "h1"),
          P("No notebook 02, ajustados <b>só com o treino do ciclo</b> (amostra estratificada de "
            f"{v['amostra']:_} linhas): (1) <b>SelectKBest</b> com informação mútua; (2) importância de ".replace("_", ".")
            + "<b>Random Forest</b> (200 árvores, classes balanceadas); (3) <b>RFE</b> com Regressão Logística, que "
            "elimina uma feature por vez (categóricas viram uma coluna cada via TargetEncoder com validação cruzada "
            "interna). Cada método produz um ranking completo."),
          P(f"<b>Regra fixada antes</b> (config.yaml): cada método vota nas suas k = {v['k']} melhores; a feature é "
            f"eleita com ≥ {v['min_votos']} de 3 votos; se sobrarem menos de {v['min_features']}, completa-se pela "
            "menor média de ranking, que também desempata e ordena. Votos, rankings, conjunto final, parâmetros e "
            "cycle_id são registrados no MLflow.")]
    if votacao is not None:
        linhas = [["Feature", "SelectKBest (rank)", "Random Forest (rank)", "RFE (rank)", "Votos", "Média rank", "Eleita"]]
        for _, r in votacao.iterrows():
            linhas.append([r["feature"],
                           f"{'● ' if r['voto_selectkbest_mi'] else ''}{r['rank_selectkbest_mi']}",
                           f"{'● ' if r['voto_random_forest'] else ''}{r['rank_random_forest']}",
                           f"{'● ' if r['voto_rfe_logistica'] else ''}{r['rank_rfe_logistica']}",
                           int(r["votos"]), r["media_ranking"], "sim" if r["eleita"] else "não"])
        s += [P(f"Tabela de votos do ciclo {t(ultimo['cycle_id'])} (● = o método votou na feature):", "h2"),
              tabela(linhas, [4 * cm, 2.4 * cm, 2.6 * cm, 2 * cm, 1.3 * cm, 1.8 * cm, 1.4 * cm])]
    if len(hist) >= 2:
        a, b = hist[-2], hist[-1]
        entrou = sorted(set(b["features_eleitas"]) - set(a["features_eleitas"]))
        saiu = sorted(set(a["features_eleitas"]) - set(b["features_eleitas"]))
        s.append(P(f"Em relação ao ciclo anterior, entraram: {', '.join(entrou) or 'nenhuma'}; saíram: "
                   f"{', '.join(saiu) or 'nenhuma'}."))
    s.append(PageBreak())

    # ---------------------------------------------------------------- 5. competição
    s += [P("5. Competição entre os dois algoritmos", "h1"),
          P("No notebook 03, <b>Modelo A — Regressão Logística</b> (imputação pela mediana + padronização + one-hot) e "
            "<b>Modelo B — HistGradientBoosting</b> (mesmos hiperparâmetros do modelo da interface do projeto, com "
            "restrição monotônica nas taxas históricas) são treinados com <b>as mesmas features eleitas</b>, o mesmo "
            "treino, a mesma validação, a mesma métrica e seed 42. Cada um é um run do MLflow com parâmetros, "
            "métricas e o modelo serializado.")]
    linhas = [["Ciclo", "Gatilho", "Modelo", "PR-AUC", "ROC-AUC", "Brier", "Calibr.", "Top 10%"]]
    for h in hist:
        for nome, c in h["candidatos"].items():
            m = c["metricas"]
            linhas.append([h["cycle_id"], gat(h), NOMES.get(nome, nome), fmt(m["pr_auc"]),
                           fmt(m["roc_auc"]), fmt(m["brier"], 5), fmt(m["razao_prevista_observada"], 3),
                           f"{m['captura_top_10pct']:.0%}"])
    s += [tabela(linhas, [3.6 * cm, 1.9 * cm, 3.8 * cm, 1.5 * cm, 1.7 * cm, 1.5 * cm, 1.4 * cm, 1.6 * cm]),
          P("Métricas na validação de cada ciclo (6 meses finais dos dados do ciclo). Calibr. = média prevista ÷ "
            "taxa observada (1 = calibrado). Top 10% = parcela dos períodos com acidente que caem nos 10% de maior "
            "risco previsto.", "nota")]
    venceu_b = sum(1 for h in hist if h["vencedor_ciclo"] == "hist_gradient_boosting")
    s.append(P(f"O HistGradientBoosting venceu {venceu_b} de {len(hist)} ciclo(s). A diferença para a Regressão "
               "Logística é pequena, coerente com o projeto: a maior parte do sinal está no histórico do trecho."))

    # ---------------------------------------------------------------- 6. promoção
    p = cfg["promocao"]
    s += [P("6. Eleição do vencedor e promoção controlada", "h1"),
          P("Regra fixada antes (config.yaml), aplicada automaticamente no notebook 04:"),
          *bullets([
              "Vencedor do ciclo = candidato com maior PR-AUC na validação.",
              f"Checagens de qualidade: ROC-AUC ≥ {p['roc_auc_min']} e calibração (prevista ÷ observada) entre "
              f"{p['calibracao_min']} e {p['calibracao_max']}.",
              "Sem modelo vigente (primeiro ciclo): o vencedor é promovido.",
              "Com vigente: o vigente é reavaliado <b>na mesma validação do ciclo</b> (que ele não viu, porque foi "
              f"treinado num ciclo anterior com corte mais antigo). O vencedor só é promovido se superar o vigente em "
              f"≥ {p['limiar_melhoria']} de PR-AUC e passar nas checagens; senão, o vigente é mantido.",
              "A decisão vai para models/modelo_vigente.json (identificação, versão dos dados, features, métrica, "
              "run_id e histórico de todos os ciclos) e para um run do MLflow. O modelo substituído é arquivado em "
              "models/historico/.",
          ])]
    linhas = [["Ciclo", "Gatilho", "data_version", "Lote novo", "Venc.", "PR-AUC venc.", "PR-AUC vigente", "Decisão"]]
    for h in hist:
        linhas.append([h["cycle_id"], gat(h), h["data_version"], ", ".join(h["lotes_novos"]) or "base",
                       NOMES.get(h["vencedor_ciclo"], h["vencedor_ciclo"]).split(" · ")[0], fmt(h["valor_vencedor"]),
                       fmt(h.get("valor_vigente")), h["decisao"]])
    s += [tabela(linhas, [3.8 * cm, 2.0 * cm, 2.8 * cm, 1.5 * cm, 1.3 * cm, 1.7 * cm, 1.7 * cm, 2.2 * cm]), Spacer(1, 4)]
    s.append(tabela([["Ciclo", "Motivo registrado"]] + [[h["cycle_id"], h["motivo"]] for h in hist], [3.8 * cm, 13.2 * cm]))
    vg = man["vigente"]
    s.append(P(f"<b>Modelo vigente:</b> {t(NOMES.get(vg['algoritmo'], vg['algoritmo']))}, promovido no ciclo "
               f"{t(vg['cycle_id'])} (data_version {t(vg['data_version'])}, run_id {t(vg['run_id'])}), PR-AUC de "
               f"validação {fmt(vg['valor_validacao'])}, {len(vg['features'])} features."))

    # ---------------------------------------------------------------- 7. previsões
    s += [P("7. Previsões com o modelo vigente (teste reservado 2025)", "h1"),
          P("O notebook 05 carrega o vigente pelo manifesto (o Pipeline já traz o pré-processamento e as features) e "
            "prevê <b>todos os trechos × dias × períodos de 2025</b>, registros que nunca participaram da seleção de "
            "features, do treino ou da promoção. Também lista os trechos de maior risco, mostra uma previsão linha "
            "a linha e compara os ciclos registrados.")]
    if teste:
        s.append(tabela([["Métrica em 2025", "Valor"], ["PR-AUC", fmt(teste["pr_auc"])], ["ROC-AUC", fmt(teste["roc_auc"])],
                         ["Brier", fmt(teste["brier"], 5)], ["Prevista ÷ observada", fmt(teste["razao_prevista_observada"], 3)],
                         ["Captura nos 10% de maior risco", f"{teste['captura_top_10pct']:.0%}"],
                         ["Captura nos 5% de maior risco", f"{teste['captura_top_5pct']:.0%}"],
                         ["Referência: chute aleatório", "PR-AUC ≈ 0,021 · top 10% captura 10%"]], [8 * cm, 6 * cm]))
    s.append(PageBreak())

    # ---------------------------------------------------------------- 8. evidências
    s += [P("8. Evidências de execução", "h1"),
          tabela([["Evidência", "Onde verificar"],
                  ["Execuções do workflow e logs", f"{REPO_URL}/actions/workflows/pipeline_mlops.yml"],
                  ["Commits automáticos de cada ciclo", "git log --grep \"ciclo \" (\"ciclo <cycle_id> (schedule) [skip ci]\")"],
                  ["Histórico MLflow (todos os ciclos)", "mlops/mlflow.db + mlops/mlartifacts/ · abrir com: MLOPS_SAIDA= bash mlops.sh --ui"],
                  ["Decisões e modelo vigente", "models/modelo_vigente.json, models/vigente/, models/historico/"],
                  ["Notebooks executados de cada ciclo", "evidencias/<cycle_id>/notebooks/"],
                  ["Diagnóstico, votação, comparação, decisão, drift, previsões", "evidencias/<cycle_id>/*.json, *.csv"],
                  ["Pacote completo por execução", "artefato \"ciclo-<cycle_id>\" de cada execução no GitHub Actions"],
                  ["Reprodução local", "bash mlops.sh (ver README, seção Pipeline MLOps)"]],
                 [5.5 * cm, 11.5 * cm]),
          Spacer(1, 6),
          P("<b>Ciclos registrados até a geração deste relatório</b> (gatilho: schedule = execução agendada; "
            "manual = workflow_dispatch, usado para depuração):")]
    s.append(tabela([["Ciclo (cycle_id)", "Gatilho", "data_version", "Decisão", "Vigente após"]] +
                    [[h["cycle_id"], gat(h), h["data_version"], h["decisao"], h["vigente_apos"]] for h in hist],
                    [4.3 * cm, 2.2 * cm, 3.4 * cm, 2.4 * cm, 4.7 * cm]))
    if not agendados:
        s.append(P("Ainda não há ciclo executado pelo gatilho schedule no momento desta geração. O workflow regenera "
                   "este relatório a cada ciclo; a versão no repositório reflete sempre o último ciclo.", "nota"))

    # ---------------------------------------------------------------- 9. critério 10
    d = cfg["drift"]
    s += [P("9. Recurso adicional (critério 10): monitor de drift com alerta", "h1"),
          P("<b>Problema identificado.</b> Na análise do projeto, os maiores erros do modelo vieram de trechos que "
            "mudaram de patamar de um ano para outro, e a pandemia mudou bruscamente o tráfego em 2020. Um pipeline "
            "que retreina sozinho pode absorver uma mudança dessas sem que ninguém perceba."),
          P("<b>Justificativa.</b> A promoção controlada protege contra um modelo pior, mas não avisa que os dados "
            "mudaram. O monitor torna a mudança visível a cada ciclo e chama uma pessoa quando ela é relevante."),
          P("<b>Solução implementada</b> (<i>src/drift.py</i>, limites em config.yaml): compara o mês mais recente do "
            "ciclo com o <b>mesmo mês dos 3 anos anteriores</b> (referência sazonal), medindo o PSI de cada feature e "
            f"a razão entre as taxas de acidentes. Alerta quando o PSI passa de {d['psi_alerta']} ou a razão sai de "
            f"[{d['razao_taxa_min']}, {d['razao_taxa_max']}]. Clima e calendário são reportados mas não alertam, porque "
            "variam naturalmente entre anos (feriados móveis, meses mais quentes). Esses limites foram ajustados depois "
            "de observar falsos alarmes em meses normais de 2024."),
          P("<b>Ponto de integração.</b> Roda dentro do notebook 01 em todo ciclo agendado; registra drift_psi_max, "
            "drift_razao_taxa e alerta_drift no MLflow e drift.json nas evidências; com alerta, escreve no resumo da "
            "execução do GitHub Actions e <b>abre uma issue</b> no repositório. É coberto por testes automáticos.")]
    if drift_ult:
        maior = next(iter(drift_ult["psi"]), "—")
        s.append(P(f"<b>Resultado no último ciclo:</b> PSI máximo {drift_ult['psi_max']:.3f} ({t(maior)}), taxa de "
                   f"acidentes {drift_ult['razao_taxa']}× a referência; alerta: {'sim' if drift_ult['alerta'] else 'não'}."))
    try:
        demo = demo_drift(cfg)
        s.append(tabela([["Mês avaliado", "Alerta", "PSI máximo (feature)", "Taxa ÷ referência", "Motivo do alerta"]] +
                        [[m, "sim" if r["alerta"] else "não", f"{r['psi_max']:.3f} ({next(iter(r['psi']))})",
                          f"{r['razao_taxa']:.3f}", "; ".join(r["motivos"]) or "nenhum: dentro dos limites"]
                         for m, r in demo.items()],
                        [2.2 * cm, 1.3 * cm, 3.6 * cm, 2.4 * cm, 7.5 * cm]))
        s.append(P("O PSI alto nos dois meses vem do clima (temperatura e nebulosidade), que é reportado mas não "
                   "dispara alerta; o que distingue abril/2020 é a queda real na taxa de acidentes.", "nota"))
        s.append(P("<b>Resultado demonstrado:</b> o monitor dispara em abril/2020 (início da pandemia, queda de "
                   "acidentes em relação a abril dos anos anteriores) e não dispara em abril/2024, um mês normal.", "p"))
    except Exception as exc:  # o relatório não deve falhar por causa da demonstração
        s.append(P(f"(demonstração não recalculada: {t(exc)})", "nota"))

    # ---------------------------------------------------------------- 10. limitações e conclusões
    s += [P("10. Limitações", "h1"),
          *bullets([
              "A chegada de dados é simulada por replay cronológico de 2024 (dados reais, na ordem real); com 12 "
              "lotes, depois de 12 ciclos o pipeline passa a retreinar sobre os mesmos dados.",
              "O modelo promovido é o treinado até o início da janela de validação: não é retreinado com os 6 meses "
              "mais recentes, para que o modelo em uso seja exatamente o que foi avaliado e auditado.",
              "Na seleção de features, cada método usa uma amostra de 200 mil linhas do treino, para caber no "
              "executor gratuito do GitHub Actions.",
              "O GitHub pode atrasar ou pular execuções agendadas em horários de pico, e desativa agendamentos após "
              "60 dias sem atividade no repositório.",
              "Os limites do monitor de drift foram calibrados com poucos meses de referência; mais ciclos permitiriam "
              "ajustá-los melhor.",
              "Limitações dos dados descritas na seção 1 (só acidentes registrados, VMD de uma data, clima em grade).",
          ]),
          P("11. Conclusões", "h1"),
          *bullets([
              "O pipeline executa, num único workflow agendado, o ciclo completo exigido: dados novos com versão, "
              "ETL, votação entre três métodos, competição entre dois algoritmos, registro no MLflow, promoção "
              "controlada e previsões com o modelo vigente.",
              "Todas as decisões são automáticas, reproduzíveis e auditáveis: as regras estão em config.yaml, testadas "
              "em tests/test_mlops.py, e cada decisão fica no manifesto, no MLflow e em evidencias/.",
              "A votação é estável no núcleo (histórico do trecho, localização, BR e delegacia) e varia nas features de "
              "clima e calendário, coerente com a conclusão do projeto de que o risco é sobretudo uma questão de "
              "onde.",
              "A regra de promoção mostrou seu papel: ganhos pequenos, abaixo do limiar, não trocam o modelo; ganhos "
              "consistentes trocam.",
              "O monitor de drift acrescenta uma camada de observabilidade que a promoção sozinha não oferece.",
          ])]

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setFont(FONTE, 7.5)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(2 * cm, 1.2 * cm, "Católica de Santa Catarina · Análise Preditiva · Trabalho N3")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"página {doc.page}")
        canvas.restoreState()

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(SAIDA), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                            bottomMargin=1.8 * cm, title="Relatório N3 · Pipeline MLOps", author=", ".join(INTEGRANTES))
    doc.build(s, onFirstPage=rodape, onLaterPages=rodape)
    print(f"{SAIDA} gerado ({len(hist)} ciclos, {len(agendados)} por schedule)")


if __name__ == "__main__":
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    main()
