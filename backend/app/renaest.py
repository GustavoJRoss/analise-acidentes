"""RENAEST (Senatran): acidentes de todas as vias de SC, informados pelo Detran.

Em SC o RENAEST não traz coordenadas, km nem tipo de rodovia: a localização é o município e o nome da via,
digitado à mão. Este módulo baixa a base, separa SC e casa cada endereço com uma via do OpenStreetMap no
mesmo município (veja app/vias.py para as regras de limpeza do texto).

Para cada par (município, endereço), tenta em ordem:
  1. código da rodovia escrito no texto ("ROD SC 405 KM 3")            → metodo = "codigo"
  2. nome igual a um nome do OSM no mesmo município                     → "nome"
  3. mesmo núcleo do nome, ignorando o tipo (RUA x AVENIDA)             → "nucleo"
  4. começo do nome, para textos cortados em 40 caracteres              → "prefixo"
  5. nome parecido (RapidFuzz, nota >= NOTA_MINIMA)                     → "aproximado"
Se a via casada tem `ref` de rodovia no OSM (ex.: "Rodovia José Carlos Daux" → SC-401), o acidente herda o código.
"""
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import shapely
from rapidfuzz import fuzz, process
from shapely.geometry import shape

from . import config
from .vias import codigo_rodovia, esfera, km_do_texto, normalizar, nucleo, ref_principal

URL_CKAN = "https://dados.transportes.gov.br/api/3/action/package_show?id=renaest"
URL_MALHA_IBGE = (f"https://servicodados.ibge.gov.br/api/v3/malhas/estados/{config.CODIGO_IBGE_UF}"
                  "?intrarregiao=municipio&formato=application/vnd.geo%2Bjson&qualidade=intermediaria")
URL_MUNICIPIOS_IBGE = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{config.CODIGO_IBGE_UF}/municipios"

BLOCO_CSV = 500_000
CAMPOS_NOME_OSM = ["name", "alt_name", "official_name", "old_name", "short_name", "loc_name"]
NOTA_MINIMA = 90
TAM_CORTE = 38          # o RENAEST corta o endereço em 40 caracteres


# ---- downloads ----------------------------------------------------------------------------------
def _baixar(url: str, destino: Path, timeout: int = 120) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(destino.suffix + ".parcial")
    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True,
                      headers={"User-Agent": config.USER_AGENT}) as resp:
        resp.raise_for_status()
        with open(temporario, "wb") as f:
            for pedaco in resp.iter_bytes(1 << 20):
                f.write(pedaco)
    temporario.rename(destino)
    return destino


def baixar_renaest(forcar: bool = False) -> Path:
    """Baixa o ZIP mais recente do RENAEST (~530 MB). Se já existe algum ZIP na pasta, usa ele."""
    existentes = sorted(config.PASTA_RENAEST.glob("renaest_*.zip"))
    if existentes and not forcar:
        return existentes[-1]
    recursos = httpx.get(URL_CKAN, timeout=60, headers={"User-Agent": config.USER_AGENT}).json()["result"]["resources"]
    url = recursos[-1]["url"]
    print(f"  baixando {recursos[-1]['name']} ({url.rsplit('/', 1)[-1]})…")
    return _baixar(url, config.PASTA_RENAEST / url.rsplit("/", 1)[-1], timeout=1800)


def baixar_municipios(forcar: bool = False):
    if forcar or not config.ARQ_MUNICIPIOS_GEO.exists():
        _baixar(URL_MALHA_IBGE, config.ARQ_MUNICIPIOS_GEO)
    if forcar or not config.ARQ_MUNICIPIOS_NOMES.exists():
        _baixar(URL_MUNICIPIOS_IBGE, config.ARQ_MUNICIPIOS_NOMES)


def carregar_municipios():
    """(código IBGE → polígono shapely, código IBGE → nome)."""
    geo = json.loads(config.ARQ_MUNICIPIOS_GEO.read_text())
    nomes = {str(m["id"]): m["nome"] for m in json.loads(config.ARQ_MUNICIPIOS_NOMES.read_text())}
    poligonos = {f["properties"]["codarea"]: shape(f["geometry"]) for f in geo["features"]}
    return poligonos, nomes


# ---- extração de SC ------------------------------------------------------------------------------
def extrair_uf(caminho_zip: Path, forcar: bool = False) -> pd.DataFrame:
    """Lê o CSV de acidentes (~2,7 GB, Brasil todo) em blocos, direto do ZIP, guardando só a UF do projeto."""
    if config.ARQ_RENAEST_SC.exists() and not forcar:
        return pd.read_parquet(config.ARQ_RENAEST_SC)
    with zipfile.ZipFile(caminho_zip) as z:
        nome = next(n for n in z.namelist() if n.lower().startswith("acidentes"))
        partes = []
        with z.open(nome) as f:
            for bloco in pd.read_csv(f, sep=";", dtype=str, encoding="latin1", chunksize=BLOCO_CSV):
                partes.append(bloco[bloco["uf_acidente"] == config.UF])
    df = pd.concat(partes, ignore_index=True)
    df.to_parquet(config.ARQ_RENAEST_SC, index=False)
    return df


# ---- casamento endereço → via do OSM ------------------------------------------------------------
def vias_osm_por_municipio(osm: dict, poligonos: dict) -> pd.DataFrame:
    """Uma linha por (via do OSM, variante de nome), com o município onde fica o centro da via."""
    linhas = []
    for e in osm["elements"]:
        tags, centro = e.get("tags", {}), e.get("center")
        if not centro:
            continue
        ref = ref_principal(tags.get("ref"))
        nome_oficial = tags.get("name") or ref
        variantes = {normalizar(tags[c]) for c in CAMPOS_NOME_OSM if tags.get(c)}
        if ref:
            variantes.add(normalizar(ref))
        for v in variantes - {""}:
            linhas.append((e["id"], centro["lon"], centro["lat"], v, nome_oficial, ref))
    df = pd.DataFrame(linhas, columns=["osm_id", "lon", "lat", "nome_norm", "nome_osm", "ref"])

    df["codigo_ibge"] = None
    for cod, poli in poligonos.items():
        dentro = shapely.contains_xy(poli, df["lon"].to_numpy(), df["lat"].to_numpy())
        df.loc[dentro, "codigo_ibge"] = cod
    df = df.dropna(subset=["codigo_ibge"])
    df["nucleo"] = df["nome_norm"].map(nucleo)
    return df


def resumir(grupo: pd.DataFrame) -> tuple:
    """(nome do OSM, ref herdada, fração das vias com esse nome que têm ref).

    Só herda a ref se a maioria das vias com o nome tem ref (FRACAO_MIN_REF), ou se o nome é de rodovia
    ("Rodovia José Carlos Daux") e alguma via com o nome tem ref. Evita que uma rua inteira vire SC-xxx
    porque um único segmento dela faz parte da rodovia. (Antes, `if r` contava NaN como ref e a regra de
    maioria funcionava só por acidente.)
    """
    vias = grupo.drop_duplicates("osm_id")
    com_ref = vias["ref"].notna() & (vias["ref"] != "")
    fracao = float(com_ref.mean()) if len(vias) else 0.0
    refs = Counter(vias.loc[com_ref, "ref"])
    nome_osm = Counter(grupo["nome_osm"]).most_common(1)[0][0]
    # o nome oficial (tag name) diz que é rodovia; alt_name/old_name não bastam
    eh_rodovia = bool(vias["nome_osm"].astype(str).str.startswith("Rodovia").any())
    herda = refs and (fracao >= config.FRACAO_MIN_REF or (eh_rodovia and fracao > 0))
    return nome_osm, (refs.most_common(1)[0][0] if herda else None), round(fracao, 3)


def indice_por_municipio(vias: pd.DataFrame):
    """Para cada município: nome normalizado (ou núcleo) → (nome do OSM, ref herdada, fração com ref)."""
    por_nome, por_nucleo = defaultdict(dict), defaultdict(dict)
    for (cod, nome), g in vias.groupby(["codigo_ibge", "nome_norm"]):
        por_nome[cod][nome] = resumir(g)
    for (cod, nuc), g in vias.groupby(["codigo_ibge", "nucleo"]):
        if len(nuc) >= 4:
            por_nucleo[cod][nuc] = resumir(g)
    return por_nome, por_nucleo


def casar(cod: str, endereco: str, por_nome: dict, por_nucleo: dict):
    """Devolve (nome_osm, ref, fracao_ref, metodo, nota)."""
    ref_texto = codigo_rodovia(endereco)
    if ref_texto:
        return None, ref_texto, 1.0, "codigo", 100.0

    nome = normalizar(endereco)
    nuc = nucleo(nome)
    nomes, nucleos = por_nome.get(cod, {}), por_nucleo.get(cod, {})
    if not nome:
        return None, None, 0.0, "vazio", 0.0
    if nome in nomes:
        return (*nomes[nome], "nome", 100.0)
    if nuc in nucleos:
        return (*nucleos[nuc], "nucleo", 100.0)
    if len(str(endereco).strip()) >= TAM_CORTE and len(nuc) >= 10:
        candidatos = [n for n in nucleos if n.startswith(nuc)]
        if len(candidatos) == 1:
            return (*nucleos[candidatos[0]], "prefixo", 100.0)
    if nucleos and len(nuc) >= 4:
        achado = process.extractOne(nuc, list(nucleos), scorer=fuzz.token_sort_ratio, score_cutoff=NOTA_MINIMA)
        if achado:
            return (*nucleos[achado[0]], "aproximado", float(achado[1]))
    return None, None, 0.0, "sem_casamento", 0.0


def limpar_e_casar(acid: pd.DataFrame, osm_vias: dict, poligonos: dict, nomes_mun: dict) -> pd.DataFrame:
    """Acrescenta a cada acidente: via, rodovia, esfera, método/nota do casamento e km escrito no texto."""
    vias = vias_osm_por_municipio(osm_vias, poligonos)
    por_nome, por_nucleo = indice_por_municipio(vias)

    # o mesmo endereço se repete muito: casa cada par (município, endereço) uma vez só
    pares = acid[["codigo_ibge", "end_acidente"]].drop_duplicates().reset_index(drop=True)
    resultado = [casar(c, e, por_nome, por_nucleo) for c, e in zip(pares["codigo_ibge"], pares["end_acidente"])]
    pares[["via_osm", "rodovia", "fracao_ref", "metodo", "nota"]] = pd.DataFrame(resultado, index=pares.index)
    pares["endereco_limpo"] = pares["end_acidente"].map(normalizar)
    pares["km_texto"] = pares["end_acidente"].map(km_do_texto)

    saida = acid.merge(pares, on=["codigo_ibge", "end_acidente"], how="left")
    saida["municipio"] = saida["codigo_ibge"].map(nomes_mun)
    saida["esfera"] = np.where(saida["metodo"].isin(["vazio", "sem_casamento"]), "desconhecida",
                               saida["rodovia"].map(esfera))
    # nome final da via: rodovia pelo código; senão, o nome do OSM (ou o texto limpo, se nada casou)
    saida["via"] = saida["rodovia"].fillna(saida["via_osm"]).fillna(saida["endereco_limpo"])
    return saida
