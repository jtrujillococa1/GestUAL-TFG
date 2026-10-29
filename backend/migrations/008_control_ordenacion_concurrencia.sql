-- Control de ciclo de vida por área. La versión permite rechazar de forma
-- determinista una edición basada en una pantalla desactualizada.
CREATE TABLE IF NOT EXISTS ordenacion_areas_control (
    area_id INTEGER PRIMARY KEY REFERENCES areas(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 0 CHECK (version >= 0),
    estado VARCHAR(16) NOT NULL DEFAULT 'ABIERTA'
        CHECK (estado IN ('ABIERTA', 'CERRADA')),
    cerrado_por_usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    cerrado_en TIMESTAMPTZ,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Bitácora de cambios relevantes. El detalle conserva el motivo de una
-- reapertura y los metadatos de cada operación sin copiar datos personales.
CREATE TABLE IF NOT EXISTS ordenacion_eventos (
    id BIGSERIAL PRIMARY KEY,
    area_id INTEGER NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
    usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    tipo VARCHAR(40) NOT NULL,
    detalle JSONB NOT NULL DEFAULT '{}'::JSONB,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ordenacion_eventos_area_fecha
    ON ordenacion_eventos (area_id, creado_en DESC);

INSERT INTO ordenacion_areas_control (area_id)
SELECT id FROM areas
ON CONFLICT (area_id) DO NOTHING;
