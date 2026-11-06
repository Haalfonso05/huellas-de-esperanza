"""Modelos de entrada y salida de la API de Mascotas."""
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

Especie = Literal["perro", "gato", "otro"]
Sexo = Literal["macho", "hembra"]
Tamano = Literal["pequeno", "mediano", "grande"]
EstadoMascota = Literal["disponible", "adoptada"]


class MascotaCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=80, examples=["Luna"])
    especie: Especie
    raza: Optional[str] = Field(default=None, max_length=80)
    edad_meses: Optional[int] = Field(default=None, ge=0, le=600)
    sexo: Optional[Sexo] = None
    tamano: Optional[Tamano] = None
    descripcion: Optional[str] = Field(default=None, max_length=1000)
    foto_url: Optional[str] = Field(default=None, max_length=500)


class Mascota(MascotaCrear):
    id: UUID
    estado: EstadoMascota
    creada_en: datetime


class Disponibilidad(BaseModel):
    mascota_id: UUID
    estado: EstadoMascota
    disponible: bool


class EstadoActualizar(BaseModel):
    estado: EstadoMascota
