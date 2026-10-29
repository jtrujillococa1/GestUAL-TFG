-- Preserva las ordenaciones existentes; las nuevas y las reiniciadas requieren inicio.
DO $$
BEGIN
IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='ordenacion_areas_control' AND column_name='iniciada') THEN
ALTER TABLE ordenacion_areas_control ADD COLUMN iniciada BOOLEAN NOT NULL DEFAULT TRUE;
UPDATE actividades SET horario_confirmado=TRUE WHERE requiere_horario=TRUE
 AND (NULLIF(TRIM(horario),'') IS NOT NULL OR jsonb_array_length(COALESCE(horario_detallado,'[]'::jsonb))>0);
END IF;
END $$;
ALTER TABLE ordenacion_areas_control ALTER COLUMN iniciada SET DEFAULT FALSE;
-- Los horarios actuales se aceptan para la prueba; se mantiene su procedencia.
