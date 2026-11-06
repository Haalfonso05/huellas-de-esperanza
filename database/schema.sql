-- Huellas de Esperanza: esquema inicial para Supabase (PostgreSQL)
-- Ejecutar completo en: Supabase > SQL Editor

-- =========================================================
-- Tabla de la API de Mascotas
-- =========================================================
CREATE TABLE mascotas (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre      text NOT NULL,
    especie     text NOT NULL CHECK (especie IN ('perro', 'gato', 'otro')),
    raza        text,
    edad_meses  integer CHECK (edad_meses >= 0),
    sexo        text CHECK (sexo IN ('macho', 'hembra')),
    tamano      text CHECK (tamano IN ('pequeno', 'mediano', 'grande')),
    descripcion text,
    foto_url    text,
    estado      text NOT NULL DEFAULT 'disponible'
                CHECK (estado IN ('disponible', 'adoptada')),
    creada_en   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_mascotas_estado ON mascotas (estado);

-- =========================================================
-- Tabla de la API de Adopciones
-- =========================================================
-- mascota_id no tiene llave foránea a propósito: cada servicio es dueño
-- de sus datos y la existencia de la mascota se verifica por HTTP.
CREATE TABLE solicitudes (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    mascota_id          uuid NOT NULL,
    solicitante_nombre  text NOT NULL,
    solicitante_email   text NOT NULL,
    solicitante_telefono text NOT NULL,
    direccion           text NOT NULL,
    motivo              text NOT NULL,
    estado              text NOT NULL DEFAULT 'pendiente'
                        CHECK (estado IN ('pendiente', 'aprobada', 'rechazada')),
    observacion         text,
    creada_en           timestamptz NOT NULL DEFAULT now(),
    decidida_en         timestamptz
);

CREATE INDEX idx_solicitudes_mascota ON solicitudes (mascota_id);
CREATE INDEX idx_solicitudes_estado ON solicitudes (estado);

-- Regla clave: una mascota no puede tener dos adopciones aprobadas.
CREATE UNIQUE INDEX una_aprobada_por_mascota
    ON solicitudes (mascota_id)
    WHERE estado = 'aprobada';

-- Evita que una persona envíe dos solicitudes pendientes para la misma mascota.
CREATE UNIQUE INDEX una_pendiente_por_persona
    ON solicitudes (mascota_id, lower(solicitante_email))
    WHERE estado = 'pendiente';

-- =========================================================
-- Seguridad
-- =========================================================
-- Bloquea el acceso público por la API automática de Supabase.
-- Las APIs de FastAPI se conectan con la cadena de conexión de Postgres.
ALTER TABLE mascotas ENABLE ROW LEVEL SECURITY;
ALTER TABLE solicitudes ENABLE ROW LEVEL SECURITY;

-- =========================================================
-- Datos de prueba para la demo
-- =========================================================
INSERT INTO mascotas (nombre, especie, raza, edad_meses, sexo, tamano, descripcion) VALUES
    ('Luna',   'perro', 'Criolla',   24, 'hembra', 'mediano', 'Juguetona y muy cariñosa con los niños.'),
    ('Rocky',  'perro', 'Labrador',  48, 'macho',  'grande',  'Tranquilo, le encanta salir a caminar.'),
    ('Michi',  'gato',  'Criollo',   12, 'macho',  'pequeno', 'Curioso y acostumbrado a vivir en apartamento.'),
    ('Canela', 'gato',  'Siamés',    36, 'hembra', 'pequeno', 'Algo tímida al inicio, pero muy dulce.');
