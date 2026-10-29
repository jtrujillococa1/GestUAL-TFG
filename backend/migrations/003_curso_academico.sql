-- Una actividad pertenece a una ordenación de un curso académico concreto.
ALTER TABLE actividades
    ADD COLUMN IF NOT EXISTS curso_academico VARCHAR(20);

DROP INDEX IF EXISTS idx_actividades_identidad_area;
CREATE UNIQUE INDEX IF NOT EXISTS idx_actividades_identidad_area_curso
    ON actividades (
        codigo, tipo, codigo_grupo, COALESCE(area_id, -1), COALESCE(curso_academico, '')
    );
