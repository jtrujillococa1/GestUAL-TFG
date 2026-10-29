CREATE TABLE IF NOT EXISTS importaciones_catalogo (
    id SERIAL PRIMARY KEY,
    huella VARCHAR(64) NOT NULL UNIQUE,
    curso_academico VARCHAR(20) NOT NULL,
    filas_csv INTEGER NOT NULL,
    actividades_creadas INTEGER NOT NULL,
    profesores_creados INTEGER NOT NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT NOW()
);
