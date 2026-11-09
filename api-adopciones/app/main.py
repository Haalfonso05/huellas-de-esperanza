"""API de Adopciones: gestión de solicitudes de adopción."""
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from psycopg.errors import UniqueViolation

from . import mascotas_client
from .database import pool
from .mascotas_client import MascotaNoEncontrada, ServicioMascotasNoDisponible
from .schemas import Decision, EstadoSolicitud, Solicitud, SolicitudCrear

logger = logging.getLogger("api-adopciones")

COLUMNAS = (
    "id, mascota_id, solicitante_nombre, solicitante_email, solicitante_telefono, "
    "direccion, motivo, estado, observacion, creada_en, decidida_en"
)

ERRORES = {
    400: {"description": "La mascota indicada no existe"},
    404: {"description": "Solicitud o mascota no encontrada"},
    409: {"description": "La operación entra en conflicto con el estado actual"},
    503: {"description": "La API de Mascotas no está disponible"},
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(
    title="API de Adopciones - Huellas de Esperanza",
    description=(
        "Registra y gestiona las solicitudes de adopción. Se integra con la "
        "API de Mascotas por HTTP/REST."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


def servicio_caido() -> HTTPException:
    """Error 503 para cuando la API de Mascotas no responde."""
    return HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "La API de Mascotas no está disponible. No se realizó ningún cambio; inténtalo de nuevo.",
    )


@app.get("/health", tags=["Sistema"], summary="Verificar que el servicio y la base de datos responden")
def health():
    with pool.connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok", "servicio": "api-adopciones"}


@app.get("/solicitudes", response_model=list[Solicitud], tags=["Solicitudes"], summary="Listar solicitudes")
def listar_solicitudes(
    estado: Optional[EstadoSolicitud] = Query(default=None),
    mascota_id: Optional[UUID] = Query(default=None),
):
    with pool.connection() as conn:
        return conn.execute(
            f"""
            SELECT {COLUMNAS} FROM solicitudes
            WHERE (%(estado)s::text IS NULL OR estado = %(estado)s)
              AND (%(mascota_id)s::uuid IS NULL OR mascota_id = %(mascota_id)s)
            ORDER BY creada_en DESC
            """,
            {"estado": estado, "mascota_id": mascota_id},
        ).fetchall()


@app.get(
    "/solicitudes/{solicitud_id}",
    response_model=Solicitud,
    responses={404: ERRORES[404]},
    tags=["Solicitudes"],
    summary="Consultar una solicitud",
)
def obtener_solicitud(solicitud_id: UUID):
    with pool.connection() as conn:
        solicitud = conn.execute(
            f"SELECT {COLUMNAS} FROM solicitudes WHERE id = %s", (solicitud_id,)
        ).fetchone()
    if solicitud is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Solicitud no encontrada")
    return solicitud


@app.post(
    "/solicitudes",
    response_model=Solicitud,
    status_code=status.HTTP_201_CREATED,
    responses={k: ERRORES[k] for k in (400, 409, 503)},
    tags=["Solicitudes"],
    summary="Registrar una solicitud",
    description="Verifica por HTTP que la mascota exista y esté disponible antes de registrarla.",
)
def crear_solicitud(datos: SolicitudCrear):
    try:
        disponible = mascotas_client.esta_disponible(datos.mascota_id)
    except MascotaNoEncontrada:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La mascota no existe")
    except ServicioMascotasNoDisponible:
        raise servicio_caido()

    if not disponible:
        raise HTTPException(status.HTTP_409_CONFLICT, "La mascota ya no está disponible")

    try:
        with pool.connection() as conn:
            return conn.execute(
                f"""
                INSERT INTO solicitudes
                    (mascota_id, solicitante_nombre, solicitante_email,
                     solicitante_telefono, direccion, motivo)
                VALUES
                    (%(mascota_id)s, %(solicitante_nombre)s, %(solicitante_email)s,
                     %(solicitante_telefono)s, %(direccion)s, %(motivo)s)
                RETURNING {COLUMNAS}
                """,
                datos.model_dump(),
            ).fetchone()
    except UniqueViolation:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ya tienes una solicitud pendiente para esta mascota",
        )


def _bloquear_pendiente(conn, solicitud_id: UUID) -> dict:
    """Bloquea la solicitud (FOR UPDATE) y valida que siga pendiente."""
    solicitud = conn.execute(
        f"SELECT {COLUMNAS} FROM solicitudes WHERE id = %s FOR UPDATE", (solicitud_id,)
    ).fetchone()
    if solicitud is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Solicitud no encontrada")
    if solicitud["estado"] != "pendiente":
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"La solicitud ya fue {solicitud['estado']}"
        )
    return solicitud


@app.post(
    "/solicitudes/{solicitud_id}/aprobar",
    response_model=Solicitud,
    responses={k: ERRORES[k] for k in (404, 409, 503)},
    tags=["Gestión"],
    summary="Aprobar una solicitud",
    description=(
        "Dentro de una transacción: verifica la disponibilidad por HTTP, aprueba la "
        "solicitud, rechaza las demás pendientes de la mascota y la marca como adoptada "
        "en la API de Mascotas. Si la integración falla, no se guarda ningún cambio."
    ),
)
def aprobar_solicitud(solicitud_id: UUID, decision: Optional[Decision] = None):
    """Aprueba la solicitud, rechaza las demás pendientes y marca la mascota como adoptada.

    Si falla la llamada a la API de Mascotas, revierte la transacción y
    devuelve la mascota a disponible.
    """
    observacion = decision.observacion if decision else None
    mascota_id = None
    estado_enviado = False

    try:
        with pool.connection() as conn:
            fila = conn.execute(
                "SELECT mascota_id FROM solicitudes WHERE id = %s", (solicitud_id,)
            ).fetchone()
            if fila is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Solicitud no encontrada")
            mascota_id = fila["mascota_id"]

            # Serializa las aprobaciones de la misma mascota
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s::text, 0))",
                (mascota_id,),
            )
            _bloquear_pendiente(conn, solicitud_id)

            if not mascotas_client.esta_disponible(mascota_id):
                raise HTTPException(status.HTTP_409_CONFLICT, "La mascota ya no está disponible")

            try:
                aprobada = conn.execute(
                    f"""
                    UPDATE solicitudes
                    SET estado = 'aprobada', observacion = %s, decidida_en = now()
                    WHERE id = %s
                    RETURNING {COLUMNAS}
                    """,
                    (observacion, solicitud_id),
                ).fetchone()
            except UniqueViolation:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "La mascota ya tiene una adopción aprobada"
                )

            conn.execute(
                """
                UPDATE solicitudes
                SET estado = 'rechazada', decidida_en = now(),
                    observacion = 'La mascota fue adoptada por otro solicitante'
                WHERE mascota_id = %s AND estado = 'pendiente'
                """,
                (mascota_id,),
            )

            estado_enviado = True
            mascotas_client.actualizar_estado(mascota_id, "adoptada")
        return aprobada

    except HTTPException:
        raise
    except MascotaNoEncontrada:
        raise HTTPException(status.HTTP_409_CONFLICT, "La mascota ya no existe")
    except Exception as error:
        # Compensación: devolver la mascota a disponible
        if estado_enviado:
            try:
                mascotas_client.actualizar_estado(mascota_id, "disponible")
            except Exception:
                logger.exception(
                    "Compensación fallida: revisar el estado de la mascota %s", mascota_id
                )
        if isinstance(error, ServicioMascotasNoDisponible):
            raise servicio_caido()
        raise


@app.post(
    "/solicitudes/{solicitud_id}/rechazar",
    response_model=Solicitud,
    responses={k: ERRORES[k] for k in (404, 409)},
    tags=["Gestión"],
    summary="Rechazar una solicitud",
)
def rechazar_solicitud(solicitud_id: UUID, decision: Optional[Decision] = None):
    """Rechaza una solicitud pendiente."""
    observacion = decision.observacion if decision else None
    with pool.connection() as conn:
        _bloquear_pendiente(conn, solicitud_id)
        return conn.execute(
            f"""
            UPDATE solicitudes
            SET estado = 'rechazada', observacion = %s, decidida_en = now()
            WHERE id = %s
            RETURNING {COLUMNAS}
            """,
            (observacion, solicitud_id),
        ).fetchone()
