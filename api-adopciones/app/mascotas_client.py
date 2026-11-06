"""Cliente HTTP de la API de Mascotas.

Este módulo es el único punto de integración entre los dos servicios: la API
de Adopciones nunca consulta la tabla `mascotas` directamente.
"""
import os
from uuid import UUID

import httpx
from dotenv import load_dotenv

load_dotenv()

MASCOTAS_API_URL = os.environ["MASCOTAS_API_URL"].rstrip("/")
TIMEOUT = float(os.getenv("MASCOTAS_TIMEOUT", "10"))


class MascotaNoEncontrada(Exception):
    """La API de Mascotas respondió que la mascota no existe."""


class ServicioMascotasNoDisponible(Exception):
    """La API de Mascotas no respondió o respondió con un error."""


def _peticion(metodo: str, ruta: str, **kwargs) -> dict:
    try:
        # retries=2 reintenta solo si falla el establecimiento de la conexión.
        transporte = httpx.HTTPTransport(retries=2)
        with httpx.Client(timeout=TIMEOUT, transport=transporte) as cliente:
            respuesta = cliente.request(metodo, f"{MASCOTAS_API_URL}{ruta}", **kwargs)
    except httpx.HTTPError as error:
        raise ServicioMascotasNoDisponible() from error

    if respuesta.status_code == 404:
        raise MascotaNoEncontrada()
    if respuesta.is_error:
        raise ServicioMascotasNoDisponible()
    return respuesta.json()


def esta_disponible(mascota_id: UUID) -> bool:
    datos = _peticion("GET", f"/mascotas/{mascota_id}/disponibilidad")
    return datos["disponible"]


def actualizar_estado(mascota_id: UUID, estado: str) -> None:
    _peticion("PATCH", f"/mascotas/{mascota_id}/estado", json={"estado": estado})
