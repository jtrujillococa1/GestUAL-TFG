-- Evita rótulos redundantes cuando la entidad ya incluye "Departamento" o
-- "Área" en su nombre oficial.
UPDATE usuarios
SET apellidos = regexp_replace(apellidos, '^Departamento Departamento[[:space:]]+', 'Departamento ', 'i')
WHERE email LIKE 'responsable.departamento.%@gestual.local';

UPDATE usuarios
SET apellidos = regexp_replace(apellidos, '^Área Área[[:space:]]+', 'Área ', 'i')
WHERE email LIKE 'responsable.area.%@gestual.local';
