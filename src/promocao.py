"""Eleição do vencedor do ciclo e promoção controlada do modelo vigente.

Regra (config.yaml → promocao), fixada antes dos ciclos:
  1. vencedor do ciclo = candidato com maior métrica principal na validação do ciclo;
  2. checagens de qualidade do vencedor: ROC-AUC mínimo e calibração (razão prevista/observada) dentro da faixa;
  3. sem vigente → promove (se as checagens falharem, promove assim mesmo e registra o aviso: é preciso um modelo);
  4. com vigente → o vigente é reavaliado NA MESMA validação; promove só se vencedor ≥ vigente + limiar e as
     checagens passarem. Caso contrário, mantém o vigente.
"""
import json
import shutil
from datetime import datetime, timezone

import joblib

from .comum import estado


def eleger(candidatos: dict[str, dict], metrica: str, direcao: str) -> str:
    sinal = 1 if direcao == "maximize" else -1
    return max(candidatos, key=lambda nome: sinal * candidatos[nome][metrica])


def checagens(m: dict, cfg_promocao: dict) -> list[str]:
    falhas = []
    if m["roc_auc"] < cfg_promocao["roc_auc_min"]:
        falhas.append(f"ROC-AUC {m['roc_auc']:.3f} < {cfg_promocao['roc_auc_min']}")
    if not cfg_promocao["calibracao_min"] <= m["razao_prevista_observada"] <= cfg_promocao["calibracao_max"]:
        falhas.append(f"calibração {m['razao_prevista_observada']:.2f} fora de "
                      f"[{cfg_promocao['calibracao_min']}, {cfg_promocao['calibracao_max']}]")
    return falhas


def decidir(candidatos: dict[str, dict], vigente: dict | None, cfg: dict) -> dict:
    """candidatos: nome → métricas na validação; vigente: métricas do vigente na MESMA validação (ou None)."""
    metrica, direcao = cfg["avaliacao"]["metrica"], cfg["avaliacao"]["direcao"]
    p = cfg["promocao"]
    vencedor = eleger(candidatos, metrica, direcao)
    m = candidatos[vencedor]
    falhas = checagens(m, p)
    base = {"vencedor_ciclo": vencedor, "metrica": metrica, "valor_vencedor": m[metrica], "falhas_qualidade": falhas}

    if vigente is None:
        aviso = f" (aviso: {'; '.join(falhas)})" if falhas else ""
        return base | {"decisao": "promovido", "valor_vigente": None,
                       "motivo": f"primeiro ciclo: não há modelo vigente{aviso}"}

    sinal = 1 if direcao == "maximize" else -1
    melhoria = sinal * (m[metrica] - vigente[metrica])
    base |= {"valor_vigente": vigente[metrica], "melhoria": round(melhoria, 5)}
    if falhas:
        return base | {"decisao": "mantido", "motivo": "vencedor reprovado nas checagens: " + "; ".join(falhas)}
    if melhoria >= p["limiar_melhoria"]:
        return base | {"decisao": "promovido",
                       "motivo": f"{metrica} {m[metrica]:.4f} supera o vigente ({vigente[metrica]:.4f}) "
                                 f"em {melhoria:.4f} ≥ {p['limiar_melhoria']}"}
    return base | {"decisao": "mantido",
                   "motivo": f"{metrica} {m[metrica]:.4f} vs vigente {vigente[metrica]:.4f}: melhoria "
                             f"{melhoria:.4f} < limiar {p['limiar_melhoria']}"}


# --- persistência do vigente ---------------------------------------------------------------------------------

def _pasta(cfg):
    return estado(cfg, "modelos")


def manifesto_path(cfg):
    return _pasta(cfg) / "modelo_vigente.json"


def ler_manifesto(cfg) -> dict | None:
    arq = manifesto_path(cfg)
    return json.loads(arq.read_text()) if arq.exists() else None


def carregar_vigente(cfg):
    """(pipeline, manifesto) do modelo vigente, ou (None, None) no primeiro ciclo."""
    man = ler_manifesto(cfg)
    if man is None or man.get("vigente") is None:
        return None, man
    return joblib.load(_pasta(cfg) / man["vigente"]["arquivo"]), man


def registrar(cfg, ciclo: dict, decisao: dict, candidato: dict, modelo_candidato) -> dict:
    """Atualiza models/: promove (arquivando o anterior em models/historico/) ou mantém, e reescreve o manifesto."""
    pasta = _pasta(cfg)
    (pasta / "vigente").mkdir(parents=True, exist_ok=True)
    man = ler_manifesto(cfg) or {"vigente": None, "historico": []}

    if decisao["decisao"] == "promovido":
        anterior = man.get("vigente")
        if anterior:
            destino = pasta / "historico" / anterior["cycle_id"]
            destino.mkdir(parents=True, exist_ok=True)
            shutil.move(pasta / anterior["arquivo"], destino / "modelo.joblib")
            anterior["arquivo"] = str((destino / "modelo.joblib").relative_to(pasta))
        joblib.dump(modelo_candidato, pasta / "vigente" / "modelo.joblib")
        man["vigente"] = {
            "cycle_id": ciclo["cycle_id"], "data_version": ciclo["data_version"],
            "algoritmo": candidato["algoritmo"], "run_id": candidato["run_id"],
            "features": ciclo["features_eleitas"], "metrica": decisao["metrica"],
            "valor_validacao": decisao["valor_vencedor"], "fim_dos_dados": ciclo["fim_dos_dados"],
            "arquivo": "vigente/modelo.joblib",
            "promovido_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    man["ultimo_ciclo"] = ciclo["cycle_id"]
    man["historico"].append({
        "cycle_id": ciclo["cycle_id"], "data_version": ciclo["data_version"], "gatilho": ciclo.get("gatilho"),
        "lotes_novos": ciclo["lotes_novos"], "features_eleitas": ciclo["features_eleitas"],
        "candidatos": ciclo["candidatos"], **decisao,
        "vigente_apos": man["vigente"]["cycle_id"] if man["vigente"] else None,
    })
    manifesto_path(cfg).write_text(json.dumps(man, ensure_ascii=False, indent=2))
    return man
