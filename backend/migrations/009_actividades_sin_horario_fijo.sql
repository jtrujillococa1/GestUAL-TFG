-- Algunas actividades (p. ej. prácticas externas) tienen carga docente, pero
-- no ocupan una franja semanal presencial. Deben poder ordenarse sin inventar
-- un horario ni provocar falsos solapes.
ALTER TABLE actividades
    ADD COLUMN IF NOT EXISTS requiere_horario BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE actividades
    DROP CONSTRAINT IF EXISTS actividades_horario_requerido;

ALTER TABLE actividades
    ADD CONSTRAINT actividades_horario_requerido
    CHECK (
        NOT requiere_horario
        OR (
            BTRIM(COALESCE(dias, '')) <> ''
            AND BTRIM(COALESCE(horario, '')) <> ''
        )
    );

-- Solo se corrigen franjas sintéticas provisionales: un horario real ya
-- confirmado nunca se sustituye automáticamente.
UPDATE actividades
SET requiere_horario = FALSE,
    dias = NULL,
    horario = NULL,
    horario_confirmado = FALSE,
    origen_horario = 'NO_APLICA'
WHERE COALESCE(horario_confirmado, FALSE) = FALSE
  AND origen_horario = 'SINTETICO'
  AND (
      nombre_asignatura ILIKE 'Prácticas Externas%'
      OR caracter ILIKE 'Prácticas Externas%'
  );
