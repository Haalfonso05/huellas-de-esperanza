"""Modelos de entrada y salida de la API de Adopciones."""
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

EstadoSolicitud = Literal["pendiente", "aprobada", "rechazada"]


class SolicitudCrear(BaseModel):
    mascota_id: UUID
    solicitante_nombre: str = Field(min_length=2, max_length=120)
    solicitante_email: EmailStr
    solicitante_telefono: str = Field(min_length=7, max_length=20)
    direccion: str = Field(min_length=5, max_length=200)
    motivo: str = Field(min_length=10, max_length=1000)


class Solicitud(BaseModel):
    id: UUID
    mascota_id: UUID
    solicitante_nombre: str
    solicitante_email: str
    solicitante_telefono: str
    direccion: str
    motivo: str
    estado: EstadoSolicitud
    observacion: Optional[str]
    creada_en: datetime
    decidida_en: Optional[datetime]


class Decision(BaseModel):
    observacion: Optional[str] = Field(default=None, max_length=500)
