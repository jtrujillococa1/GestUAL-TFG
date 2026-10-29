-- Trazabilidad de una ordenación publicada/importada. Estos campos no crean
-- usuarios ni conceden permisos: solo preservan la procedencia del reparto.

ALTER TABLE profesores
    ADD COLUMN IF NOT EXISTS identificador_origen VARCHAR(100),
    ADD COLUMN IF NOT EXISTS activo_origen BOOLEAN;

CREATE UNIQUE INDEX IF NOT EXISTS idx_profesores_identificador_origen
    ON profesores (identificador_origen)
    WHERE identificador_origen IS NOT NULL;

ALTER TABLE reparto_docente
    ADD COLUMN IF NOT EXISTS codigo_plaza_origen VARCHAR(100),
    ADD COLUMN IF NOT EXISTS id_plaza_origen VARCHAR(100),
    ADD COLUMN IF NOT EXISTS es_profesor_principal BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS coordinador_origen VARCHAR(255),
    ADD COLUMN IF NOT EXISTS origen_reparto VARCHAR(30) NOT NULL DEFAULT 'MANUAL';
