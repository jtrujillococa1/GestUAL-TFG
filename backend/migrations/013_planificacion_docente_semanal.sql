-- Calendario académico y planificación derivada de las adjudicaciones.
-- La ordenación continúa siendo la fuente de verdad de las horas; estas tablas
-- solo materializan las sesiones concretas para poder consultarlas por semana.

CREATE TABLE IF NOT EXISTS calendario_docente_periodos (
    id BIGSERIAL PRIMARY KEY,
    curso_academico VARCHAR(20) NOT NULL,
    tipo_estudio VARCHAR(30) NOT NULL DEFAULT 'GRADO',
    cuatrimestre VARCHAR(10) NOT NULL CHECK (cuatrimestre IN ('PRIMERO', 'SEGUNDO')),
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    descripcion VARCHAR(300),
    fuente VARCHAR(500),
    CONSTRAINT calendario_docente_periodos_fechas_validas CHECK (fecha_fin >= fecha_inicio),
    CONSTRAINT uq_calendario_docente_periodo UNIQUE (curso_academico, tipo_estudio, cuatrimestre)
);

CREATE TABLE IF NOT EXISTS calendario_docente_excepciones (
    id BIGSERIAL PRIMARY KEY,
    curso_academico VARCHAR(20) NOT NULL,
    fecha DATE NOT NULL,
    tipo VARCHAR(30) NOT NULL CHECK (tipo IN (
        'FESTIVO_NACIONAL', 'FESTIVO_AUTONOMICO', 'FESTIVO_LOCAL',
        'NO_LECTIVO_UAL', 'PRESENTACION_UAL'
    )),
    nombre VARCHAR(300) NOT NULL,
    bloquea_docencia BOOLEAN NOT NULL DEFAULT TRUE,
    fuente VARCHAR(500),
    CONSTRAINT uq_calendario_docente_excepcion UNIQUE (curso_academico, fecha, tipo, nombre)
);

CREATE INDEX IF NOT EXISTS idx_calendario_docente_excepciones_curso_fecha
    ON calendario_docente_excepciones (curso_academico, fecha);

CREATE TABLE IF NOT EXISTS planificacion_docente_sesiones (
    id BIGSERIAL PRIMARY KEY,
    actividad_id INTEGER NOT NULL REFERENCES actividades(id) ON DELETE CASCADE,
    profesor_id INTEGER NOT NULL REFERENCES profesores(id) ON DELETE CASCADE,
    reparto_id INTEGER REFERENCES reparto_docente(id) ON DELETE SET NULL,
    curso_academico VARCHAR(20) NOT NULL,
    fecha DATE,
    hora_inicio TIME,
    hora_fin TIME,
    horas NUMERIC(8,2) NOT NULL CHECK (horas > 0),
    orden_adjudicacion INTEGER NOT NULL CHECK (orden_adjudicacion > 0),
    orden_sesion INTEGER NOT NULL CHECK (orden_sesion > 0),
    estado VARCHAR(30) NOT NULL DEFAULT 'PLANIFICADA'
        CHECK (estado IN ('PLANIFICADA', 'AJUSTE_PENDIENTE', 'PENDIENTE_HORARIO')),
    origen VARCHAR(30) NOT NULL DEFAULT 'AUTOMATICO'
        CHECK (origen IN ('AUTOMATICO', 'MANUAL')),
    observacion TEXT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT planificacion_sesion_coherente CHECK (
        (estado = 'PLANIFICADA' AND fecha IS NOT NULL AND hora_inicio IS NOT NULL AND hora_fin IS NOT NULL AND hora_fin > hora_inicio)
        OR (estado <> 'PLANIFICADA' AND fecha IS NULL AND hora_inicio IS NULL AND hora_fin IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_planificacion_docente_profesor_semana
    ON planificacion_docente_sesiones (profesor_id, curso_academico, fecha, hora_inicio);
CREATE INDEX IF NOT EXISTS idx_planificacion_docente_actividad
    ON planificacion_docente_sesiones (actividad_id, orden_adjudicacion, orden_sesion);

-- Fechas oficiales UAL 2025/26: se registran los periodos docentes para grado
-- y máster. Los periodos ya excluyen vacaciones intercuatrimestrales.
INSERT INTO calendario_docente_periodos
    (curso_academico, tipo_estudio, cuatrimestre, fecha_inicio, fecha_fin, descripcion, fuente)
VALUES
    ('2025/26', 'GRADO', 'PRIMERO', '2025-09-04', '2025-12-19', 'Docencia de grado, primer cuatrimestre', 'Calendario académico UAL 2025/26'),
    ('2025/26', 'GRADO', 'SEGUNDO', '2026-02-09', '2026-05-29', 'Docencia de grado, segundo cuatrimestre', 'Calendario académico UAL 2025/26'),
    ('2025/26', 'MASTER', 'PRIMERO', '2025-10-06', '2026-01-24', 'Docencia de máster, primer cuatrimestre', 'Calendario académico UAL 2025/26'),
    ('2025/26', 'MASTER', 'SEGUNDO', '2026-02-23', '2026-05-30', 'Docencia de máster, segundo cuatrimestre', 'Calendario académico UAL 2025/26')
ON CONFLICT (curso_academico, tipo_estudio, cuatrimestre) DO UPDATE
SET fecha_inicio=EXCLUDED.fecha_inicio, fecha_fin=EXCLUDED.fecha_fin,
    descripcion=EXCLUDED.descripcion, fuente=EXCLUDED.fuente;

-- Festivos nacionales, autonómicos y presentación UAL que afectan al curso.
INSERT INTO calendario_docente_excepciones
    (curso_academico, fecha, tipo, nombre, bloquea_docencia, fuente)
VALUES
    ('2025/26', '2025-09-04', 'PRESENTACION_UAL', 'Jornada de presentación UAL', TRUE, 'Calendario académico UAL 2025/26'),
    ('2025/26', '2025-09-05', 'PRESENTACION_UAL', 'Jornada de presentación UAL', TRUE, 'Calendario académico UAL 2025/26'),
    ('2025/26', '2025-10-13', 'FESTIVO_NACIONAL', 'Fiesta Nacional de España (traslado)', TRUE, 'Calendario laboral Andalucía 2025'),
    ('2025/26', '2025-12-08', 'FESTIVO_NACIONAL', 'Inmaculada Concepción', TRUE, 'Calendario laboral Andalucía 2025'),
    ('2025/26', '2026-04-02', 'FESTIVO_AUTONOMICO', 'Jueves Santo', TRUE, 'Calendario laboral Andalucía 2026'),
    ('2025/26', '2026-04-03', 'FESTIVO_AUTONOMICO', 'Viernes Santo', TRUE, 'Calendario laboral Andalucía 2026'),
    ('2025/26', '2026-05-01', 'FESTIVO_NACIONAL', 'Fiesta del Trabajo', TRUE, 'Calendario laboral Andalucía 2026')
ON CONFLICT (curso_academico, fecha, tipo, nombre) DO UPDATE
SET bloquea_docencia=EXCLUDED.bloquea_docencia, fuente=EXCLUDED.fuente;
