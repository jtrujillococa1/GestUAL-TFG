-- Preferencias declaradas por el profesorado. Cada código representa una
-- asignatura y su posición es el orden de interés del docente.
CREATE TABLE IF NOT EXISTS profesor_prioridades_asignaturas (
    profesor_id INTEGER NOT NULL REFERENCES profesores(id) ON DELETE CASCADE,
    asignatura_codigo VARCHAR(100) NOT NULL,
    prioridad INTEGER NOT NULL CHECK (prioridad > 0),
    PRIMARY KEY (profesor_id, asignatura_codigo),
    UNIQUE (profesor_id, prioridad)
);

CREATE INDEX IF NOT EXISTS idx_profesor_prioridades_profesor
    ON profesor_prioridades_asignaturas (profesor_id, prioridad);
