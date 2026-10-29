-- Propuestas supervisadas de reparación. El solver solo guarda una propuesta;
-- ningún reparto cambia hasta que un responsable o administrador la aprueba.
CREATE TABLE IF NOT EXISTS ordenacion_conflictos_propuestas (
    id BIGSERIAL PRIMARY KEY,
    area_id INTEGER NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
    profesor_bloqueado_id INTEGER NOT NULL REFERENCES profesores(id) ON DELETE CASCADE,
    version_base INTEGER NOT NULL CHECK (version_base >= 0),
    estado VARCHAR(16) NOT NULL DEFAULT 'PENDIENTE'
        CHECK (estado IN ('PENDIENTE', 'APROBADA', 'RECHAZADA', 'OBSOLETA')),
    propuesta JSONB NOT NULL,
    creada_por_usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    creada_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decidida_por_usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    decidida_en TIMESTAMPTZ,
    motivo_rechazo TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_conflicto_pendiente_area
    ON ordenacion_conflictos_propuestas (area_id)
    WHERE estado = 'PENDIENTE';

CREATE INDEX IF NOT EXISTS idx_conflictos_area_fecha
    ON ordenacion_conflictos_propuestas (area_id, creada_en DESC);
