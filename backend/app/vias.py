"""Limpeza de nomes de vias digitados à mão (RENAEST) para casar com os nomes e códigos do OpenStreetMap.

O campo de endereço do RENAEST é texto livre: "RUA AV. GOV CELSO RAMOS", "ROD  SC 405", "SC355 KM 73.800",
"RODOVIA JOSE CARLOS DAUX" (que é a SC-401)... Aqui ficam as regras que deixam esses textos comparáveis.
"""
import re
import unicodedata

# abreviações frequentes → forma por extenso (aplicadas palavra a palavra)
ABREVIACOES = {
    "AV": "AVENIDA", "AVEN": "AVENIDA", "R": "RUA", "ROD": "RODOVIA", "RDV": "RODOVIA", "EST": "ESTRADA",
    "ESTR": "ESTRADA", "SERV": "SERVIDAO", "SERVID": "SERVIDAO", "TV": "TRAVESSA", "TRAV": "TRAVESSA",
    "AL": "ALAMEDA", "PC": "PRACA", "PCA": "PRACA", "GOV": "GOVERNADOR", "DEP": "DEPUTADO", "DEPUT": "DEPUTADO",
    "PREF": "PREFEITO", "PRES": "PRESIDENTE", "DR": "DOUTOR", "PROF": "PROFESSOR", "PROFA": "PROFESSORA",
    "ENG": "ENGENHEIRO", "JORN": "JORNALISTA", "STA": "SANTA", "STO": "SANTO", "CEL": "CORONEL",
    "CAP": "CAPITAO", "GAL": "GENERAL", "GEN": "GENERAL", "MAL": "MARECHAL", "SEN": "SENADOR",
    "VER": "VEREADOR", "PE": "PADRE", "BRIG": "BRIGADEIRO", "TEN": "TENENTE", "SGT": "SARGENTO",
    "COM": "COMENDADOR", "DES": "DESEMBARGADOR", "MIN": "MINISTRO", "ARQ": "ARQUITETO", "IRM": "IRMA",
    "NSA": "NOSSA", "SRA": "SENHORA",
}

# palavras que dizem o tipo da via; o "núcleo" do nome é o que sobra sem elas
TIPOS_VIA = {
    "RUA", "AVENIDA", "RODOVIA", "ESTRADA", "SERVIDAO", "TRAVESSA", "ALAMEDA", "LINHA", "ACESSO", "VIA",
    "MARGINAL", "PRACA", "BECO", "LARGO", "VIADUTO", "PONTE", "TUNEL", "CAMINHO", "GERAL", "ESTADUAL",
    "FEDERAL", "MUNICIPAL", "CICLOVIA", "VIELA", "LOTEAMENTO", "CONTORNO",
}
PALAVRAS_VAZIAS = {"DE", "DA", "DO", "DAS", "DOS", "E", "D"}

RE_RODOVIA = re.compile(r"\b(SC|BR|SCT|SCA|SCL|SCI)\s*[-–]?\s*(\d{3})\b")
RE_KM = re.compile(r"\bKM\s*[-.:]?\s*(\d{1,3})(?:\s*[.,\s+-]\s*(\d{1,3}))?")
# o que vem depois disso costuma ser complemento ("KM 12", "- PROXIMO AO TREVO", "N 300")
RE_COMPLEMENTO = re.compile(r"\s(KM\b|-\s|N\s?\d|NR\b|NUMERO\b|PROX|ESQ|ESQUINA|SENTIDO|TREVO\b|DEFRONTE).*$")


def sem_acentos(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def normalizar(texto: str | None) -> str:
    """Maiúsculas, sem acento nem pontuação, abreviações expandidas e tipo de via duplicado removido."""
    if not texto:
        return ""
    t = sem_acentos(str(texto)).upper()
    t = RE_COMPLEMENTO.sub("", " " + t).strip()
    t = re.sub(r"[^A-Z0-9 ]", " ", t)
    palavras = [ABREVIACOES.get(p, p) for p in t.split()]
    # "RUA AVENIDA X", "LINHA RODOVIA X": fica o último tipo da sequência inicial
    while len(palavras) > 1 and palavras[0] in TIPOS_VIA and palavras[1] in TIPOS_VIA:
        palavras.pop(0)
    return " ".join(palavras)


def nucleo(nome_normalizado: str) -> str:
    """O nome sem o tipo da via e sem preposições: "AVENIDA BEIRA MAR NORTE" → "BEIRA MAR NORTE"."""
    return " ".join(p for p in nome_normalizado.split() if p not in TIPOS_VIA and p not in PALAVRAS_VAZIAS)


def codigo_rodovia(texto: str | None) -> str | None:
    """'ROD  SC 405 KM 3' → 'SC-405'. Devolve None se o texto não citar uma rodovia por código."""
    if not texto:
        return None
    m = RE_RODOVIA.search(sem_acentos(str(texto)).upper())
    return f"{m.group(1)}-{m.group(2)}" if m else None


def km_do_texto(texto: str | None) -> float | None:
    """'SC355 KM 73.800' → 73.8; 'KM 99 200' → 99.2; 'KM 215' → 215.0."""
    if not texto:
        return None
    m = RE_KM.search(sem_acentos(str(texto)).upper())
    if not m:
        return None
    inteiro, fracao = int(m.group(1)), m.group(2)
    if fracao is None:
        return float(inteiro)
    # "73.800" e "99 200" são metros; "1 5" é decimal
    return inteiro + (int(fracao) / 1000 if len(fracao) == 3 else int(fracao) / 10 ** len(fracao))


def ref_principal(ref: str | None) -> str | None:
    """'SC-401;SC-402' → 'SC-401'. Normaliza 'SC 401' e 'SC401' para 'SC-401'."""
    if not ref:
        return None
    return codigo_rodovia(ref.split(";")[0])


def esfera(ref: str | None) -> str:
    if not isinstance(ref, str) or not ref:
        return "municipal"
    return "federal" if ref.startswith("BR") else "estadual"
