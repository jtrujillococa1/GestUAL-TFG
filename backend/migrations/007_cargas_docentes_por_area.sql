-- Un perfil puede pertenecer a varias áreas, pero su carga total no debe
-- duplicarse. Esta columna expresa qué parte de la carga se ordena en cada
-- área y permite que las colas avancen de forma independiente.
ALTER TABLE profesor_areas
    ADD COLUMN IF NOT EXISTS horas_objetivo NUMERIC(8, 1);

-- Conserva los repartos existentes. La carga ya confirmada se respeta y el
-- resto se distribuye de forma equilibrada entre las áreas del perfil.
WITH confirmadas AS (
    SELECT rd.profesor_id, a.area_id, SUM(rd.horas_asignadas) AS horas
    FROM reparto_docente rd
    JOIN actividades a ON a.id = rd.actividad_id
    GROUP BY rd.profesor_id, a.area_id
), resumen AS (
    SELECT pa.profesor_id,
           COUNT(*) AS numero_areas,
           COALESCE(SUM(c.horas), 0) AS horas_confirmadas
    FROM profesor_areas pa
    LEFT JOIN confirmadas c ON c.profesor_id = pa.profesor_id AND c.area_id = pa.area_id
    GROUP BY pa.profesor_id
)
UPDATE profesor_areas pa
SET horas_objetivo = ROUND(
    COALESCE((
        SELECT c.horas
        FROM confirmadas c
        WHERE c.profesor_id = pa.profesor_id AND c.area_id = pa.area_id
    ), 0)
    + GREATEST(p.carga_docente - r.horas_confirmadas, 0) / r.numero_areas,
    1
)
FROM profesores p
JOIN resumen r ON r.profesor_id = p.id
WHERE pa.profesor_id = p.id AND pa.horas_objetivo IS NULL;

ALTER TABLE profesor_areas
    ALTER COLUMN horas_objetivo SET DEFAULT 0,
    ALTER COLUMN horas_objetivo SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_profesor_areas_cola
    ON profesor_areas (area_id, horas_objetivo, profesor_id);
