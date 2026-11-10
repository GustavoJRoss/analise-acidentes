"""Relatório de qualidade dos dados das duas redes (somente leitura).

Uso (dentro de backend/):  python -m scripts.relatorio_dados [--comparar]
Salva em artifacts/relatorio_dados.json. Com --comparar, mostra as métricas de cada modelo em
artifacts/historico_metricas/ lado a lado.
"""
import json
import sys

import pandas as pd

from app import config


def _rede(rede: str) -> dict:
    a = config.REDES[rede]
    if not a.acidentes.exists():
        return {"preparada": False}
    acid = pd.read_parquet(a.acidentes)
    out = {"acidentes": len(acid),
           "acidentes_por_ano": {int(k): int(v) for k, v in acid.groupby(acid["data"].dt.year).size().items()}}
    if a.estado.exists():
        estado = pd.read_parquet(a.estado)
        out["trechos"] = len(estado)
        out["trechos_sem_acidente"] = int((estado["acidentes"] == 0).sum()) if "acidentes" in estado else None
    if a.clima.exists():
        clima = pd.read_parquet(a.clima)
        out["clima"] = {"celulas": int(clima["celula"].nunique()), "inicio": str(clima["data"].min().date()),
                        "fim": str(clima["data"].max().date()), "linhas": len(clima)}
    return out


def _renaest() -> dict:
    if not config.ARQ_RENAEST_VIAS.exists():
        return {"preparado": False}
    cols = ["metodo", "esfera", "via_osm", "data_acidente"]
    r = pd.read_parquet(config.ARQ_RENAEST_VIAS, columns=cols)
    est = r[r["esfera"] == "estadual"]
    tipo = est["via_osm"].fillna("").str.split().str[0]
    return {
        "acidentes_sc": len(r),
        "metodo": r["metodo"].value_counts(normalize=True).round(4).to_dict(),
        "esfera": r["esfera"].value_counts(normalize=True).round(4).to_dict(),
        "estaduais": len(est),
        "estaduais_em_rua_ou_avenida": round(float(tipo.isin(["Rua", "Avenida"]).mean()), 4),
    }


def comparar():
    pasta = config.ARTIFACTS / "historico_metricas"
    linhas = []
    for arq in sorted(pasta.glob("*.json")):
        m = json.loads(arq.read_text())
        for nome, v in m["modelos"].items():
            linhas.append({"arquivo": arq.stem, "modelo": nome, **v})
    print(pd.DataFrame(linhas).to_string(index=False))


def main():
    relatorio = {"br": _rede("br"), "sc": _rede("sc"), "renaest": _renaest()}
    destino = config.ARTIFACTS / "relatorio_dados.json"
    destino.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2))
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    if "--comparar" in sys.argv:
        comparar()


if __name__ == "__main__":
    main()
