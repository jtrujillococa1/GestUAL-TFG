-- El horario resumido (dias/horario) se mantiene por compatibilidad con la
-- cuadrícula semanal. Este detalle conserva las sesiones reales publicadas
-- (fecha y franja) sin confundir semanas distintas del cuatrimestre.
ALTER TABLE actividades
    ADD COLUMN IF NOT EXISTS horario_detallado JSONB NOT NULL DEFAULT '[]'::JSONB,
    ADD COLUMN IF NOT EXISTS fuente_horario VARCHAR(500);

CREATE INDEX IF NOT EXISTS idx_actividades_horario_detallado
    ON actividades USING GIN (horario_detallado);
