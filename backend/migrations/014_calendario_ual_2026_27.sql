-- Calendario oficial UAL 2026/27, curso de las actividades actualmente cargadas.
INSERT INTO calendario_docente_periodos
    (curso_academico, tipo_estudio, cuatrimestre, fecha_inicio, fecha_fin, descripcion, fuente)
VALUES
    ('2026/2027', 'GRADO', 'PRIMERO', '2026-09-10', '2026-12-22', 'Docencia de grado, primer cuatrimestre', 'Calendario académico UAL 2026/27'),
    ('2026/2027', 'GRADO', 'SEGUNDO', '2027-02-15', '2027-05-28', 'Docencia de grado, segundo cuatrimestre', 'Calendario académico UAL 2026/27'),
    ('2026/2027', 'MASTER', 'PRIMERO', '2026-10-05', '2027-01-22', 'Docencia de máster, primer cuatrimestre', 'Calendario académico UAL 2026/27'),
    ('2026/2027', 'MASTER', 'SEGUNDO', '2027-02-24', '2027-05-31', 'Docencia de máster, segundo cuatrimestre', 'Calendario académico UAL 2026/27')
ON CONFLICT (curso_academico, tipo_estudio, cuatrimestre) DO UPDATE
SET fecha_inicio=EXCLUDED.fecha_inicio, fecha_fin=EXCLUDED.fecha_fin,
    descripcion=EXCLUDED.descripcion, fuente=EXCLUDED.fuente;

INSERT INTO calendario_docente_excepciones
    (curso_academico, fecha, tipo, nombre, bloquea_docencia, fuente)
VALUES
    ('2026/2027', '2026-10-12', 'FESTIVO_NACIONAL', 'Fiesta Nacional de España', TRUE, 'Calendario laboral Andalucía 2026'),
    ('2026/2027', '2026-11-02', 'FESTIVO_NACIONAL', 'Todos los Santos (traslado)', TRUE, 'Calendario laboral Andalucía 2026'),
    ('2026/2027', '2026-12-07', 'FESTIVO_NACIONAL', 'Día de la Constitución Española (traslado)', TRUE, 'Calendario laboral Andalucía 2026'),
    ('2026/2027', '2026-12-08', 'FESTIVO_NACIONAL', 'Inmaculada Concepción', TRUE, 'Calendario laboral Andalucía 2026'),
    ('2026/2027', '2027-03-01', 'FESTIVO_AUTONOMICO', 'Día de Andalucía (traslado)', TRUE, 'Calendario laboral Andalucía 2027'),
    ('2026/2027', '2027-03-25', 'FESTIVO_AUTONOMICO', 'Jueves Santo', TRUE, 'Calendario laboral Andalucía 2027'),
    ('2026/2027', '2027-03-26', 'FESTIVO_NACIONAL', 'Viernes Santo', TRUE, 'Calendario laboral Andalucía 2027')
ON CONFLICT (curso_academico, fecha, tipo, nombre) DO UPDATE
SET bloquea_docencia=EXCLUDED.bloquea_docencia, fuente=EXCLUDED.fuente;
