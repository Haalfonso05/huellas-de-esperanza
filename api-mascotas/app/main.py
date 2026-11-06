"""API de Mascotas: registro, consulta y disponibilidad de los animales.

Es la única dueña de la tabla `mascotas`. Otros servicios, como la API de
Adopciones, acceden a estos datos únicamente por HTTP.
"""
import os
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from .database import pool
from .schemas import (
    Disponibilidad,
    Especie,
    EstadoActualizar,
    EstadoMascota,
    Mascota,
    MascotaCrear,
)

COLUMNAS = (
    "id, nombre, especie, raza, edad_meses, sexo, tamano, "
    "descripcion, foto_url, estado, creada_en"
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(
    title="API de Mascotas - Huellas de Esperanza",
    description="Administra el registro, la consulta y la disponibilidad de los animales.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


def no_encontrada() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Mascota no encontrada")


@app.get("/health", tags=["Sistema"], summary="Verificar que el servicio y la base de datos responden")
def health():
    with pool.connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok", "servicio": "api-mascotas"}


@app.get("/mascotas", response_model=list[Mascota], tags=["Mascotas"], summary="Listar mascotas")
def listar_mascotas(
    estado: Optional[EstadoMascota] = Query(default=None),
    especie: Optional[Especie] = Query(default=None),
):
    with pool.connection() as conn:
        return conn.execute(
            f"""
            SELECT {COLUMNAS} FROM mascotas
            WHERE (%(estado)s::text IS NULL OR estado = %(estado)s)
              AND (%(especie)s::text IS NULL OR especie = %(especie)s)
            ORDER BY creada_en DESC, nombre
            """,
            {"estado": estado, "especie": especie},
        ).fetchall()


@app.get("/mascotas/{mascota_id}", response_model=Mascota, tags=["Mascotas"], summary="Consultar una mascota")
def obtener_mascota(mascota_id: UUID):
    with pool.connection() as conn:
        mascota = conn.execute(
            f"SELECT {COLUMNAS} FROM mascotas WHERE id = %s", (mascota_id,)
        ).fetchone()
    if mascota is None:
        raise no_encontrada()
    return mascota


@app.get(
    "/mascotas/{mascota_id}/disponibilidad",
    response_model=Disponibilidad,
    tags=["Integración"],
    summary="Verificar si una mascota está disponible",
)
def consultar_disponibilidad(mascota_id: UUID):
    with pool.connection() as conn:
        fila = conn.execute(
            "SELECT estado FROM mascotas WHERE id = %s", (mascota_id,)
        ).fetchone()
    if fila is None:
        raise no_encontrada()
    return {
        "mascota_id": mascota_id,
        "estado": fila["estado"],
        "disponible": fila["estado"] == "disponible",
    }


@app.post(
    "/mascotas",
    response_model=Mascota,
    status_code=status.HTTP_201_CREATED,
    tags=["Mascotas"],
    summary="Registrar una mascota",
)
def crear_mascota(datos: MascotaCrear):
    with pool.connection() as conn:
        return conn.execute(
            f"""
            INSERT INTO mascotas
                (nombre, especie, raza, edad_meses, sexo, tamano, descripcion, foto_url)
            VALUES
                (%(nombre)s, %(especie)s, %(raza)s, %(edad_meses)s, %(sexo)s,
                 %(tamano)s, %(descripcion)s, %(foto_url)s)
            RETURNING {COLUMNAS}
            """,
            datos.model_dump(),
        ).fetchone()


@app.patch(
    "/mascotas/{mascota_id}/estado",
    response_model=Mascota,
    tags=["Integración"],
    summary="Actualizar el estado de una mascota",
    description=(
        "La usa la API de Adopciones al aprobar una solicitud. Es idempotente: "
        "repetir la misma petición no cambia el resultado, así que se puede "
        "reintentar con seguridad si hubo un fallo de red."
    ),
)
def actualizar_estado(mascota_id: UUID, datos: EstadoActualizar):
    with pool.connection() as conn:
        mascota = conn.execute(
            f"UPDATE mascotas SET estado = %s WHERE id = %s RETURNING {COLUMNAS}",
            (datos.estado, mascota_id),
        ).fetchone()
    if mascota is None:
        raise no_encontrada()
    return mascota
