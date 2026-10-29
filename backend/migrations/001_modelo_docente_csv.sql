-- Metadatos preservados de la exportación institucional de ordenación docente.
-- Es una migración aditiva: las actividades existentes siguen siendo válidas.

ALTER TABLE actividades
    ADD COLUMN IF NOT EXISTS nombre_asignatura VARCHAR(255),
    ADD COLUMN IF NOT EXISTS tipo_estudio VARCHAR(20),
    ADD COLUMN IF NOT EXISTS codigo_plan VARCHAR(50),
    ADD COLUMN IF NOT EXISTS nombre_plan VARCHAR(255),
    ADD COLUMN IF NOT EXISTS codigo_centro VARCHAR(50),
    ADD COLUMN IF NOT EXISTS nombre_centro VARCHAR(255),
    ADD COLUMN IF NOT EXISTS ciclo VARCHAR(50),
    ADD COLUMN IF NOT EXISTS curso VARCHAR(50),
    ADD COLUMN IF NOT EXISTS caracter VARCHAR(100),
    ADD COLUMN IF NOT EXISTS actividad_oficial_id VARCHAR(50),
    ADD COLUMN IF NOT EXISTS nombre_actividad VARCHAR(255),
    ADD COLUMN IF NOT EXISTS codigo_grupo_oficial VARCHAR(50),
    ADD COLUMN IF NOT EXISTS horario_confirmado BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS origen_horario VARCHAR(30) NOT NULL DEFAULT 'PENDIENTE';

-- Una misma actividad/grupo puede tener una cuota distinta en más de un área.
ALTER TABLE actividades
    DROP CONSTRAINT IF EXISTS actividades_codigo_tipo_codigo_grupo_key;

CREATE UNIQUE INDEX IF NOT EXISTS idx_actividades_identidad_area
    ON actividades (codigo, tipo, codigo_grupo, COALESCE(area_id, -1));

CREATE INDEX IF NOT EXISTS idx_actividades_identificador_oficial
    ON actividades (actividad_oficial_id, codigo_grupo_oficial);
