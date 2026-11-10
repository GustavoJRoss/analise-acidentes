"""Demonstração de uso pela linha de comando: uma nova entrada → probabilidade explicada.

Usa os mesmos artefatos e o mesmo código da API (app.modelo.PrevisaoCombinada).

Uso (dentro de backend/):
  python -m scripts.prever --rodovia BR-101 --km 205 --data 2026-12-20 --periodo noite --clima chuva_forte
  python -m scripts.prever --rodovia SC-401 --municipio Florianópolis --periodo tarde
  python -m scripts.prever --endereco "Ponte Hercílio Luz, Florianópolis" --periodo manha   # usa o Nominatim (OSM)
  python -m scripts.prever --trecho 101-200 --data 2026-12-24 --periodo noite
"""
import argparse
import re
from datetime import date

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from app import config
from app.modelo import PrevisaoCombinada
from app.vias import sem_acentos

PERIODOS = list(config.PERIODOS)
CLIMAS = ["ceu_claro", "nublado", "chuva", "chuva_forte"]
DIST_MAX_ENDERECO_M = 2000


def _rodovia(texto: str) -> tuple[str, int]:
    """'BR-101', 'br 101', '101' → ('br', 101); 'SC-401', 'sc401' → ('sc', 401)."""
    m = re.fullmatch(r"\s*(BR|SC)?[\s-]*(\d+)\s*", texto.upper())
    if not m:
        raise SystemExit(f"Rodovia inválida: {texto!r} (use, por exemplo, BR-101 ou SC-401)")
    return ("sc" if m.group(1) == "SC" else "br"), int(m.group(2))


def _por_endereco(servico: PrevisaoCombinada, endereco: str) -> str:
    from app.rotas import buscar_endereco  # só aqui: chama um serviço público (Nominatim)

    achados = buscar_endereco(endereco)
    if not achados:
        raise SystemExit(f"Endereço não encontrado em SC: {endereco!r}")
    lugar = achados[0]
    pontos = pd.concat([pd.read_parquet(config.REDES[r].pontos_via) for r in servico.servicos], ignore_index=True)
    arvore = BallTree(np.radians(pontos[["lat", "lon"]].values), metric="haversine")
    dist, idx = arvore.query(np.radians([[lugar["lat"], lugar["lon"]]]), k=1)
    dist_m = float(dist[0, 0]) * 6_371_000
    if dist_m > DIST_MAX_ENDERECO_M:
        raise SystemExit(f"{lugar['nome']} fica a {dist_m / 1000:.1f} km da rodovia modelada mais próxima.")
    print(f"Endereço: {lugar['nome']} (a {dist_m:.0f} m da rodovia)")
    return str(pontos["trecho_id"].iat[int(idx[0, 0])])


def resolver_trecho(servico: PrevisaoCombinada, args) -> str:
    if args.trecho:
        return args.trecho
    if args.endereco:
        return _por_endereco(servico, args.endereco)
    if not args.rodovia:
        raise SystemExit("Informe --trecho, --endereco ou --rodovia (com --km ou --municipio).")
    rede, numero = _rodovia(args.rodovia)
    if rede not in servico.servicos:
        raise SystemExit(f"A rede {rede!r} não foi preparada (faltam os artefatos).")
    estado = servico.servicos[rede].estado
    if rede == "br":
        if args.km is None:
            raise SystemExit("Para BRs, informe --km.")
        tid = f"{numero}-{int(args.km // config.TAMANHO_TRECHO_KM * config.TAMANHO_TRECHO_KM)}"
        if tid not in estado.index:
            raise SystemExit(f"BR-{numero} km {args.km:g} não está entre os trechos modelados.")
        return tid
    if not args.municipio:
        raise SystemExit("Para rodovias estaduais, informe --municipio.")
    alvo = sem_acentos(args.municipio).upper().strip()
    achados = estado[(estado["rodovia"] == f"SC-{numero}")
                     & (estado["municipio"].map(lambda m: sem_acentos(m).upper()) == alvo)]
    if achados.empty:
        municipios = sorted(estado.loc[estado["rodovia"] == f"SC-{numero}", "municipio"])
        raise SystemExit(f"SC-{numero} em {args.municipio!r} não está entre os trechos modelados. "
                         f"Municípios dessa rodovia: {', '.join(municipios) or 'nenhum'}")
    return str(achados.index[0])


def _pct(p: float) -> str:
    return f"{p * 100:.1f}%".replace(".", ",")


def mostrar(r: dict):
    t = r["trechos"][0]
    c = r["cenario"]
    marcas = [nome for chave, nome in [("feriado", "feriado"), ("vespera_ou_pos_feriado", "véspera/pós-feriado"),
                                       ("fim_de_semana", "fim de semana"), ("temporada_verao", "verão")] if c[chave]]
    acid_ano = f"{t['acidentes_ano']:g}".replace(".", ",")
    local = t["rotulo"] if t["municipio"] in t["rotulo"] else f"{t['rotulo']} ({t['municipio']})"
    print(f"\nTrecho:   {local} — {acid_ano} acidentes/ano em média")
    print(f"Cenário:  {c['data']}, {c['periodo']}, clima {c['clima']}"
          + (f" ({', '.join(marcas)})" if marcas else ""))
    print(f"\nChance de ao menos um acidente neste trecho e período: {_pct(r['probabilidade'])}")
    if r["razao_media"]:
        razao = f"{r['razao_media']:.2f}".replace(".", ",")
        print(f"Média histórica do trecho nesse período do dia:      {_pct(r['media_referencia'])}"
              f"  → {razao}× a média")
    print("\nO que mais pesa (comparado com a referência):")
    for f in r["fatores"][:3]:
        print(f"  {f['efeito_relativo'] * 100:+4.0f}%  {f['fator']}")
    print("\nAviso: a estimativa vem de acidentes registrados (PRF/RENAEST) e reflete sobretudo o histórico do"
          "\ntrecho; não é uma garantia de segurança nem considera obras, eventos ou o seu modo de dirigir.")


def main(argv=None) -> dict:
    p = argparse.ArgumentParser(description="Probabilidade de acidente num trecho de rodovia de SC.")
    p.add_argument("--trecho", help="ID do trecho, ex.: 101-200 ou 'SC-401|4205407'")
    p.add_argument("--rodovia", help="BR-101, SC-401…")
    p.add_argument("--km", type=float, help="km da BR (trechos de 10 km)")
    p.add_argument("--municipio", help="município (rodovias estaduais)")
    p.add_argument("--endereco", help="endereço ou lugar em SC (busca no OpenStreetMap)")
    p.add_argument("--data", type=date.fromisoformat, default=date.today(), help="AAAA-MM-DD (padrão: hoje)")
    p.add_argument("--periodo", choices=PERIODOS, default="tarde")
    p.add_argument("--clima", choices=CLIMAS, default="ceu_claro")
    args = p.parse_args(argv)

    servico = PrevisaoCombinada()
    tid = resolver_trecho(servico, args)
    if not servico.conhece(tid):
        raise SystemExit(f"Trecho desconhecido: {tid}")
    resultado = servico.prever([tid], pd.Timestamp(args.data), args.periodo, args.clima)
    mostrar(resultado)
    return resultado


if __name__ == "__main__":
    main()
