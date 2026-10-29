-- La categoría PSI siempre implica gestión delegada. No altera credenciales.
CREATE OR REPLACE FUNCTION normalizar_perfil_psi() RETURNS trigger AS $$
BEGIN
  IF upper(trim(NEW.categoria)) = 'PSI' THEN NEW.es_psi := TRUE; END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS normalizar_perfil_psi ON profesores;
CREATE TRIGGER normalizar_perfil_psi BEFORE INSERT OR UPDATE ON profesores
FOR EACH ROW EXECUTE FUNCTION normalizar_perfil_psi();

CREATE OR REPLACE FUNCTION sincronizar_cuenta_docente_psi() RETURNS trigger AS $$
BEGIN
  UPDATE usuarios SET rol=CASE WHEN NEW.es_psi THEN 'psi' ELSE 'profesor' END
  WHERE id=NEW.usuario_id AND rol IN ('psi','profesor');
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS sincronizar_cuenta_docente_psi ON profesores;
CREATE TRIGGER sincronizar_cuenta_docente_psi AFTER INSERT OR UPDATE ON profesores
FOR EACH ROW EXECUTE FUNCTION sincronizar_cuenta_docente_psi();
UPDATE profesores SET es_psi=TRUE WHERE upper(trim(categoria))='PSI' AND NOT es_psi;
UPDATE usuarios u SET rol='psi' FROM profesores p
WHERE p.usuario_id=u.id AND p.es_psi AND u.rol='profesor';
