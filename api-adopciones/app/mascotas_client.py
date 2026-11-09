"""Cliente HTTP para consumir la API de Mascotas."""
import logging
import os
from uuid import UUID

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("uvicorn.error")

MASCOTAS_API_URL = os.environ["MASCOTAS_API_URL"].rstrip("/")
TIMEOUT = float(os.getenv("MASCOTAS_TIMEOUT", "10"))


class MascotaNoEncontrada(Exception):
    """La API de Mascotas respondió que la mascota no existe."""


class ServicioMascotasNoDisponible(Exception):
    """La API de Mascotas no respondió o respondió con un error."""


def _peticion(metodo: str, ruta: str, **kwargs) -> dict:
    """Envía una petición a la API de Mascotas y devuelve el JSON de la respuesta.

    Lanza MascotaNoEncontrada si responde 404 y ServicioMascotasNoDisponible
    si no responde o devuelve otro error.
    """
    try:
        transporte = httpx.HTTPTransport(retries=2)
        with httpx.Client(timeout=TIMEOUT, transport=transporte) as cliente:
            respuesta = cliente.request(metodo, f"{MASCOTAS_API_URL}{ruta}", **kwargs)
    except httpx.HTTPError as error:
        logger.warning("Fallo la llamada %s %s: %r", metodo, ruta, error)
        raise ServicioMascotasNoDisponible() from error

    if respuesta.status_code == 404:
        raise MascotaNoEncontrada()
    if respuesta.is_error:
        logger.warning("%s %s respondio %s", metodo, ruta, respuesta.status_code)
        raise ServicioMascotasNoDisponible()
    return respuesta.json()


def esta_disponible(mascota_id: UUID) -> bool:
    """Consulta si la mascota está disponible para adopción."""
    datos = _peticion("GET", f"/mascotas/{mascota_id}/disponibilidad")
    return datos["disponible"]


def actualizar_estado(mascota_id: UUID, estado: str) -> None:
    """Cambia el estado de la mascota (disponible o adoptada)."""
    _peticion("PATCH", f"/mascotas/{mascota_id}/estado", json={"estado": estado})
