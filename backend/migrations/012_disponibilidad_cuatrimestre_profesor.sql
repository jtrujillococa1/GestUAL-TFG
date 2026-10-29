ALTER TABLE profesores
    ADD COLUMN IF NOT EXISTS disponibilidad_cuatrimestre VARCHAR(10) NOT NULL DEFAULT 'AMBOS';

UPDATE profesores
SET disponibilidad_cuatrimestre = 'AMBOS'
WHERE disponibilidad_cuatrimestre IS NULL
   OR disponibilidad_cuatrimestre NOT IN ('PRIMERO', 'SEGUNDO', 'AMBOS');

ALTER TABLE profesores
    DROP CONSTRAINT IF EXISTS profesores_disponibilidad_cuatrimestre_check;

ALTER TABLE profesores
    ADD CONSTRAINT profesores_disponibilidad_cuatrimestre_check
    CHECK (disponibilidad_cuatrimestre IN ('PRIMERO', 'SEGUNDO', 'AMBOS'));
