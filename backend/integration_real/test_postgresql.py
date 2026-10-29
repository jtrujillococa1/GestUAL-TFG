"""Cuatro escenarios contra PostgreSQL real, sin mocks de repositorio o conexión."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import json
import time
import pytest
from psycopg.errors import CheckViolation
from repositories.reparto_repository import RepartoRepository
from core.exceptions import ConcurrentModification

def snapshot(db):
    with db() as c:
        return {t:c.execute('SELECT * FROM '+t+' ORDER BY 1').fetchall() for t in
                ['reparto_docente','reparto_docente_borrador','ordenacion_areas_control','ordenacion_eventos']}

def test_confirmacion_persistida(db,draft):
    repo=RepartoRepository()
    assert repo.confirmar_borrador(101,draft,{},10,0,1)==1
    with db() as c:
        assert c.execute('SELECT profesor_id,actividad_id,horas_asignadas FROM reparto_docente ORDER BY actividad_id').fetchall()==[(101,1001,6),(201,2001,6)]
        assert c.execute('SELECT count(*) FROM reparto_docente_borrador').fetchone()[0]==0
        assert c.execute('SELECT version FROM ordenacion_areas_control WHERE area_id=10').fetchone()[0]==1
        event=c.execute('SELECT area_id,usuario_id,tipo,detalle FROM ordenacion_eventos').fetchone()
        assert event[:3]==(10,1,'TURNO_CONFIRMADO') and event[3]['profesor_id']==101

def test_error_intermedio_revierte_toda_la_confirmacion(db,draft):
    # El rechazo se produce en PostgreSQL al registrar el evento, después de
    # insertar, limpiar el borrador y avanzar la versión. No se simula rollback.
    with db() as c:
        c.execute("ALTER TABLE ordenacion_eventos ADD CONSTRAINT fallo_controlado CHECK(tipo <> 'TURNO_CONFIRMADO')")
    before=snapshot(db)
    try:
        with pytest.raises(CheckViolation):
            RepartoRepository().confirmar_borrador(101,draft,{},10,0,1)
        assert snapshot(db)==before
    finally:
        with db() as c:c.execute('ALTER TABLE ordenacion_eventos DROP CONSTRAINT fallo_controlado')

def test_reparacion_persistida_solo_en_su_area(db):
    with db() as c:
        c.execute('INSERT INTO reparto_docente(profesor_id,actividad_id,horas_asignadas) VALUES(101,1001,5),(102,1002,6)')
        plan={'plan':[{'profesor_id':101,'actividad_id':1001,'horas':6},{'profesor_id':102,'actividad_id':1002,'horas':6}]}
        proposal=c.execute("INSERT INTO ordenacion_conflictos_propuestas(area_id,profesor_bloqueado_id,version_base,propuesta,creada_por_usuario_id) VALUES(10,101,0,%s::jsonb,1) RETURNING id",(json.dumps(plan),)).fetchone()[0]
        external=c.execute('SELECT * FROM reparto_docente WHERE actividad_id=2001').fetchall()
    result=RepartoRepository().decidir_propuesta_conflicto(proposal,10,True,1)
    assert result['estado']=='APROBADA' and result['version']==1
    with db() as c:
        assert c.execute('SELECT profesor_id,actividad_id,horas_asignadas FROM reparto_docente WHERE actividad_id<>2001 ORDER BY actividad_id').fetchall()==[(101,1001,6),(102,1002,6)]
        assert c.execute('SELECT * FROM reparto_docente WHERE actividad_id=2001').fetchall()==external
        assert c.execute('SELECT estado,decidida_por_usuario_id FROM ordenacion_conflictos_propuestas WHERE id=%s',(proposal,)).fetchone()==('APROBADA',1)
        assert c.execute("SELECT count(*) FROM ordenacion_eventos WHERE tipo='CONFLICTO_APROBADO' AND area_id=10").fetchone()[0]==1
        assert c.execute('SELECT version FROM ordenacion_areas_control WHERE area_id=20').fetchone()[0]==0

def test_confirmaciones_concurrentes_misma_version(db,draft):
    barrier=Barrier(2,timeout=10)
    def confirm():
        barrier.wait()
        try:return RepartoRepository().confirmar_borrador(101,draft,{},10,0,1)
        except ConcurrentModification:return 'obsoleta'
    # Mantener la fila bloqueada permite comprobar que ambas conexiones reales
    # llegan a competir por ella antes de dejar que una confirme.
    with db() as gate, ThreadPoolExecutor(max_workers=2) as pool:
        gate.execute('SELECT version FROM ordenacion_areas_control WHERE area_id=10 FOR UPDATE')
        futures=[pool.submit(confirm) for _ in range(2)]
        waiting=0
        try:
            end=time.monotonic()+10
            while time.monotonic()<end:
                with db() as observer:
                    waiting=observer.execute("SELECT count(*) FROM pg_stat_activity WHERE datname='gestual_test' AND wait_event_type='Lock'").fetchone()[0]
                if waiting>=2:break
                time.sleep(.05)
        finally:
            gate.commit()
        results=[f.result(timeout=20) for f in futures]
        assert waiting>=2,'Deben competir dos conexiones PostgreSQL reales.'
    assert results.count(1)==1 and results.count('obsoleta')==1
    with db() as c:
        assert c.execute('SELECT count(*),sum(horas_asignadas) FROM reparto_docente WHERE profesor_id=101').fetchone()==(1,6)
        assert c.execute('SELECT version FROM ordenacion_areas_control WHERE area_id=10').fetchone()[0]==1
        assert c.execute("SELECT count(*) FROM ordenacion_eventos WHERE tipo='TURNO_CONFIRMADO'").fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM reparto_docente_borrador').fetchone()[0]==0
