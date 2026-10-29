-- El calendario muestra el horario oficial completo de cada actividad a todos
-- sus docentes adjudicados. Estas columnas conservan, por separado, la cuota
-- real adjudicada a cada uno para no confundir presencia semanal y carga POD.
ALTER TABLE planificacion_docente_sesiones
    ADD COLUMN IF NOT EXISTS horas_adjudicadas NUMERIC(8,2),
    ADD COLUMN IF NOT EXISTS es_horario_referencia BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_planificacion_docente_profesor_referencia
    ON planificacion_docente_sesiones (profesor_id, curso_academico, es_horario_referencia);
