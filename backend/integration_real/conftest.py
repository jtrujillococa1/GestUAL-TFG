"""Entorno real exclusivo de pruebas; nunca utiliza backend/.env."""
import os
from pathlib import Path

if os.environ.get('GESTUAL_REAL_TESTS') != '1':
    raise RuntimeError('Use el ejecutor aislado: GESTUAL_REAL_TESTS=1.')
TEST_ENV = dict(DB_HOST='127.0.0.1', DB_PORT='55432', DB_NAME='gestual_test',
                DB_USER='postgres', DB_PASSWORD='gestual-test-local',
                JWT_SECRET_KEY='gestual-isolated-tests-only-secret-20261027')
os.environ.update(TEST_ENV)
os.environ.pop('SMTP_HOST', None)
os.environ.pop('SMTP_FROM', None)

import pytest
import psycopg
from psycopg import sql
from db.connection import DB_CONFIG, cerrar_pool
from core.auth import get_password_hash

HERE = Path(__file__).resolve().parent
PASSWORD = 'Gestual-Pruebas-2026!'
MARKER = 'GestUAL isolated automated tests; disposable'

def connect():
    assert DB_CONFIG['dbname'] == 'gestual_test'
    assert DB_CONFIG['host'] == '127.0.0.1' and DB_CONFIG['port'] == 55432
    return psycopg.connect(**DB_CONFIG)

@pytest.fixture(scope='session', autouse=True)
def database_schema():
    with connect() as conn:
        marker = conn.execute("SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0]
        if marker != MARKER:
            tables = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()
            assert not tables, 'No se inicializa una base no vacía sin la marca de pruebas.'
            conn.execute((HERE/'schema.sql').read_text(encoding='utf-8-sig'))
            conn.execute('SET search_path TO public')
            for migration in sorted((HERE.parent/'migrations').glob('*.sql')):
                conn.execute(migration.read_text(encoding='utf-8-sig'))
            conn.execute(sql.SQL('COMMENT ON DATABASE gestual_test IS {}').format(sql.Literal(MARKER)))
    yield
    cerrar_pool()

@pytest.fixture
def db(database_schema):
    cerrar_pool()
    with connect() as conn:
        assert conn.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0] == MARKER
        tables = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()
        conn.execute(sql.SQL('TRUNCATE {} RESTART IDENTITY CASCADE').format(sql.SQL(',').join(sql.Identifier('public',x[0]) for x in tables)))
        password_hash = get_password_hash(PASSWORD)
        conn.execute("INSERT INTO categoria_pesos(categoria,peso) VALUES('CU',1)")
        for uid,name in [(1,'Ana'),(2,'Bruno'),(3,'Carla')]:
            conn.execute("INSERT INTO usuarios(id,nombre,apellidos,email,password_hash,rol) VALUES (%s,%s,'Pruebas',%s,%s,'profesor')",(uid,name,name.lower()+'@gestual.example.org',password_hash))
        conn.execute("INSERT INTO departamentos(id,codigo,nombre) VALUES(1,'DTEST','Departamento de prueba')")
        conn.execute("INSERT INTO areas(id,codigo,nombre,departamento_id) VALUES(10,'ATEST','Área principal de prueba',1),(20,'BTEST','Área independiente de prueba',1)")
        for pid,uid,name,area,date in [(101,1,'Ana',10,'2000-01-01'),(102,2,'Bruno',10,'2010-01-01'),(201,3,'Carla',20,'2000-01-01')]:
            conn.execute("INSERT INTO profesores(id,usuario_id,nombre,apellidos,categoria,fecha_ingreso,carga_docente,area_id) VALUES(%s,%s,%s,'Pruebas','CU',%s,6,%s)",(pid,uid,name,date,area))
            conn.execute('INSERT INTO profesor_areas(profesor_id,area_id,horas_objetivo) VALUES(%s,%s,6)',(pid,area))
        for aid,code,name,area in [(1001,'TEST01','Asignatura Alfa',10),(1002,'TEST02','Asignatura Beta',10),(2001,'TEST03','Asignatura Externa',20)]:
            conn.execute("""INSERT INTO actividades(id,codigo,nombre_asignatura,tipo,codigo_grupo,grupo,duracion,turno,
                horas_asignatura,horas_actividad,horas_area,area_id,requiere_horario,curso_academico,tipo_estudio)
                VALUES(%s,%s,%s,'GD','A','A','PRIMER CUATRIMESTRE','MANANA',6,6,6,%s,FALSE,'2026/2027','GRADO')""",(aid,code,name,area))
        conn.execute("INSERT INTO ordenacion_areas_control(area_id,version,estado,iniciada) VALUES(10,0,'ABIERTA',TRUE),(20,0,'ABIERTA',TRUE)")
        conn.execute('INSERT INTO reparto_docente(profesor_id,actividad_id,horas_asignadas) VALUES(201,2001,6)')
    yield connect
    cerrar_pool()

@pytest.fixture
def draft(db):
    with db() as conn:
        conn.execute('INSERT INTO reparto_docente_borrador(profesor_id,actividad_id,horas_asignadas) VALUES(101,1001,6)')
    return [dict(actividad_id=1001,codigo='TEST01',codigo_grupo='A',tipo='GD',horas=6)]
