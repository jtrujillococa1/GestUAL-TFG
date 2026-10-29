CREATE TABLE IF NOT EXISTS avisos_turno_estado (
    area_id INTEGER PRIMARY KEY REFERENCES areas(id) ON DELETE CASCADE,
    firma TEXT NOT NULL,
    generacion BIGINT NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS avisos_turno_correo (
    id BIGSERIAL PRIMARY KEY,
    area_id INTEGER NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
    profesor_id INTEGER NOT NULL REFERENCES profesores(id) ON DELETE CASCADE,
    generacion BIGINT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'PENDIENTE',
    intentos INTEGER NOT NULL DEFAULT 0,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    enviado_en TIMESTAMPTZ,
    proximo_intento TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error TEXT,
    UNIQUE(area_id, generacion)
);
