from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

Periodo = Literal["madrugada", "manha", "tarde", "noite"]
CategoriaClima = Literal["ceu_claro", "nublado", "chuva", "chuva_forte"]


class Ponto(BaseModel):
    lat: float = Field(ge=-34, le=6)
    lon: float = Field(ge=-74, le=-34)


class ClimaPersonalizado(BaseModel):
    chuva_mm: float = Field(ge=0, le=500)
    nebulosidade: float = Field(ge=0, le=100)
    temperatura: Optional[float] = Field(default=None, ge=-20, le=50)


class PedidoPrevisao(BaseModel):
    trecho_ids: list[str] = Field(min_length=1, max_length=200)
    data: date
    periodo: Periodo
    clima: CategoriaClima = "ceu_claro"
    clima_personalizado: Optional[ClimaPersonalizado] = None


class PedidoRota(BaseModel):
    origem: Ponto
    destino: Ponto
