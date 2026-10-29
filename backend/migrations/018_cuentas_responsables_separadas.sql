-- Separa las cuentas institucionales de los perfiles docentes ya existentes.
-- La cuenta original conserva el perfil y pasa a ser PROFESOR/PSI. Se crea una
-- cuenta de gestión por cada departamento o área asignado, con la contraseña
-- vigente como contraseña inicial para no bloquear el acceso durante la
-- migración. Ambas cuentas se podrán cambiar de forma independiente después.
DO $$
DECLARE
    registro RECORD;
    nuevo_usuario_id INTEGER;
    correo_gestion TEXT;
BEGIN
    FOR registro IN
        SELECT d.id, d.codigo, d.nombre, d.responsable_departamento_id AS usuario_id,
               u.password_hash
        FROM departamentos d
        JOIN usuarios u ON u.id=d.responsable_departamento_id
        JOIN profesores p ON p.usuario_id=u.id
    LOOP
        correo_gestion := 'responsable.departamento.' || lower(regexp_replace(registro.codigo, '[^a-zA-Z0-9]+', '-', 'g')) || '@gestual.local';
        SELECT id INTO nuevo_usuario_id FROM usuarios WHERE email=correo_gestion;
        IF nuevo_usuario_id IS NULL THEN
            INSERT INTO usuarios (nombre, apellidos, email, password_hash, rol, activo)
            VALUES ('Responsable', 'Departamento ' || regexp_replace(registro.nombre, '^Departamento[[:space:]]+', '', 'i'), correo_gestion, registro.password_hash, 'responsable_departamento', TRUE)
            RETURNING id INTO nuevo_usuario_id;
        END IF;
        UPDATE departamentos SET responsable_departamento_id=nuevo_usuario_id WHERE id=registro.id;
        UPDATE usuarios u
        SET rol=CASE WHEN p.es_psi THEN 'psi' ELSE 'profesor' END
        FROM profesores p
        WHERE u.id=registro.usuario_id AND p.usuario_id=u.id;
    END LOOP;

    FOR registro IN
        SELECT a.id, a.codigo, a.nombre, a.responsable_area_id AS usuario_id,
               u.password_hash
        FROM areas a
        JOIN usuarios u ON u.id=a.responsable_area_id
        JOIN profesores p ON p.usuario_id=u.id
    LOOP
        correo_gestion := 'responsable.area.' || lower(regexp_replace(registro.codigo, '[^a-zA-Z0-9]+', '-', 'g')) || '@gestual.local';
        SELECT id INTO nuevo_usuario_id FROM usuarios WHERE email=correo_gestion;
        IF nuevo_usuario_id IS NULL THEN
            INSERT INTO usuarios (nombre, apellidos, email, password_hash, rol, activo)
            VALUES ('Responsable', 'Área ' || regexp_replace(registro.nombre, '^Área[[:space:]]+', '', 'i'), correo_gestion, registro.password_hash, 'responsable_area', TRUE)
            RETURNING id INTO nuevo_usuario_id;
        END IF;
        UPDATE areas SET responsable_area_id=nuevo_usuario_id WHERE id=registro.id;
        UPDATE usuarios u
        SET rol=CASE WHEN p.es_psi THEN 'psi' ELSE 'profesor' END
        FROM profesores p
        WHERE u.id=registro.usuario_id AND p.usuario_id=u.id;
    END LOOP;
END $$;
