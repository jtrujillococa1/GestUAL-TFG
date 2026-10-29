-- Correcciones puntuales de adjudicaciones ya confirmadas.
-- Una devolución no borra el resto de la ordenación: crea una revisión
-- prioritaria para el profesor afectado y conserva el motivo en la bitácora.
CREATE TABLE IF NOT EXISTS ordenacion_revisiones (
    id BIGSERIAL PRIMARY KEY,
    area_id INTEGER NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
    profesor_id INTEGER NOT NULL REFERENCES profesores(id) ON DELETE CASCADE,
    actividad_id INTEGER NOT NULL REFERENCES actividades(id) ON DELETE CASCADE,
    horas_devuelta NUMERIC(10,2) NOT NULL CHECK (horas_devuelta > 0),
    motivo TEXT NOT NULL CHECK (char_length(trim(motivo)) >= 3),
    devuelta_por_usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    estado VARCHAR(16) NOT NULL DEFAULT 'PENDIENTE'
        CHECK (estado IN ('PENDIENTE', 'RESUELTA')),
    creada_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resuelta_en TIMESTAMPTZ,
    resuelta_por_usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_revision_pendiente_actividad_profesor
    ON ordenacion_revisiones (area_id, profesor_id, actividad_id)
    WHERE estado = 'PENDIENTE';

CREATE INDEX IF NOT EXISTS idx_ordenacion_revisiones_area_pendiente
    ON ordenacion_revisiones (area_id, creada_en ASC)
    WHERE estado = 'PENDIENTE';
