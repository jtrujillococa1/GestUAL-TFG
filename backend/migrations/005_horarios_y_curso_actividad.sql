-- El catálogo docente se gestiona por curso y toda actividad debe disponer de
-- una franja semanal. Una actividad compartida conserva una cuota por área.

DROP INDEX IF EXISTS idx_actividades_identidad_area;

CREATE UNIQUE INDEX IF NOT EXISTS idx_actividades_identidad_area_curso
    ON actividades (
        COALESCE(curso_academico, ''),
        codigo,
        tipo,
        codigo_grupo,
        COALESCE(area_id, -1)
    );

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'actividades_horario_requerido'
    ) THEN
        ALTER TABLE actividades
            ADD CONSTRAINT actividades_horario_requerido
            CHECK (
                BTRIM(COALESCE(dias, '')) <> ''
                AND BTRIM(COALESCE(horario, '')) <> ''
            );
    END IF;
END $$;
