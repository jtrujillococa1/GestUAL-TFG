-- Permitir comparar alternativas de la misma versión. Su aprobación se
-- serializa con el bloqueo del área y deja obsoletas las demás pendientes.
DROP INDEX IF EXISTS uq_conflicto_pendiente_area;
CREATE INDEX IF NOT EXISTS idx_conflictos_area_version
    ON ordenacion_conflictos_propuestas (area_id, version_base, profesor_bloqueado_id);
