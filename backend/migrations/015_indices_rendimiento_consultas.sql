-- Índices para las pantallas de consulta más frecuentes con catálogos grandes.
-- Son aditivos e idempotentes: no modifican registros ni reglas de negocio.
CREATE INDEX IF NOT EXISTS idx_actividades_area
    ON actividades (area_id);

CREATE INDEX IF NOT EXISTS idx_areas_departamento
    ON areas (departamento_id);

CREATE INDEX IF NOT EXISTS idx_profesores_usuario
    ON profesores (usuario_id);

CREATE INDEX IF NOT EXISTS idx_reparto_docente_actividad_profesor
    ON reparto_docente (actividad_id, profesor_id);

CREATE INDEX IF NOT EXISTS idx_reparto_docente_profesor_actividad
    ON reparto_docente (profesor_id, actividad_id);
