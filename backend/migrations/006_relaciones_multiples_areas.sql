-- Un docente puede prestar servicio en varias áreas. Conservamos area_id como
-- área principal de compatibilidad, y profesor_areas como fuente de verdad.
CREATE TABLE IF NOT EXISTS profesor_areas (
    profesor_id INTEGER NOT NULL REFERENCES profesores(id) ON DELETE CASCADE,
    area_id INTEGER NOT NULL REFERENCES areas(id) ON DELETE RESTRICT,
    PRIMARY KEY (profesor_id, area_id)
);

INSERT INTO profesor_areas (profesor_id, area_id)
SELECT id, area_id
FROM profesores
WHERE area_id IS NOT NULL
ON CONFLICT DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_profesor_areas_area ON profesor_areas (area_id, profesor_id);

-- Las cuotas de ordenación continúan en actividades.area_id: una misma
-- actividad/grupo puede tener una cuota por área. Esta relación expone todas
-- las áreas académicas a las que está asociada la actividad en la interfaz.
CREATE TABLE IF NOT EXISTS actividad_areas (
    actividad_id INTEGER NOT NULL REFERENCES actividades(id) ON DELETE CASCADE,
    area_id INTEGER NOT NULL REFERENCES areas(id) ON DELETE RESTRICT,
    PRIMARY KEY (actividad_id, area_id)
);

INSERT INTO actividad_areas (actividad_id, area_id)
SELECT id, area_id
FROM actividades
WHERE area_id IS NOT NULL
ON CONFLICT DO NOTHING;

-- Las instalaciones anteriores representaban una actividad compartida con una
-- fila de cuota por área. Unificamos su relación académica visible sin tocar
-- esas cuotas ni los repartos ya confirmados.
INSERT INTO actividad_areas (actividad_id, area_id)
SELECT destino.id, origen.area_id
FROM actividades destino
JOIN actividades origen
  ON origen.curso_academico IS NOT DISTINCT FROM destino.curso_academico
 AND origen.codigo = destino.codigo
 AND origen.tipo = destino.tipo
 AND origen.codigo_grupo = destino.codigo_grupo
WHERE origen.area_id IS NOT NULL
ON CONFLICT DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_actividad_areas_area ON actividad_areas (area_id, actividad_id);
