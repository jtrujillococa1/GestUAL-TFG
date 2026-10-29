"""Guardas reales del repositorio con cursor controlado; sin PostgreSQL."""
from contextlib import contextmanager
from unittest.mock import Mock
from types import SimpleNamespace
import pytest
import repositories.reparto_repository as modulo
from repositories.reparto_repository import RepartoRepository
from core.exceptions import ConstraintViolation, ConcurrentModification, OrdenacionClosed

class Cursor:
    rowcount = 0
    def __init__(self, plan=None, estado='PENDIENTE', version=3, iniciada=True, cerrada=False):
        self.plan = plan
        self.estado = estado
        self.version = version
        self.iniciada = iniciada
        self.cerrada = cerrada
        self.consultas = []
        self.lotes = []
        self.ultima = ''
    def execute(self, sql, args=None):
        self.ultima = ' '.join(sql.split())
        self.consultas.append((self.ultima, args))
    def executemany(self, sql, args): self.lotes.append(list(args))
    def fetchone(self):
        if self.ultima.startswith('SELECT version, estado'): return (self.version, 'CERRADA' if self.cerrada else 'ABIERTA')
        if self.ultima.startswith('SELECT iniciada'): return (self.iniciada,)
        if self.ultima.startswith('SELECT estado, version_base, propuesta'):
            return None if self.estado is None else (self.estado, 3, {'plan': self.plan})
        if 'RETURNING version' in self.ultima: return (4,)
        raise AssertionError(self.ultima)
    def fetchall(self):
        if self.ultima.startswith('SELECT id, horas_area'): return [(11, 6)]
        if self.ultima.startswith('SELECT profesor.id'): return [(1, 6)]
        raise AssertionError(self.ultima)

@pytest.fixture
def instalar(monkeypatch):
    def preparar(cursor):
        @contextmanager
        def conexion(): yield SimpleNamespace(cursor=lambda: cursor)
        monkeypatch.setattr(modulo, 'conexion_ctx', conexion)
        return RepartoRepository()
    return preparar

@pytest.mark.parametrize('caso,error', [('obsoleta', ConcurrentModification), ('cerrada', OrdenacionClosed), ('preparacion', OrdenacionClosed)])
def test_confirmacion_bloqueada_sin_insertar(instalar, caso, error):
    c = Cursor(version=4 if caso == 'obsoleta' else 3, cerrada=caso == 'cerrada', iniciada=caso != 'preparacion')
    repo = instalar(c)
    with pytest.raises(error):
        repo.confirmar_borrador(1, [dict(actividad_id=11, codigo='A', codigo_grupo='G', tipo='GD', horas=6)], {}, 7, 3, 9)
    assert not any('INSERT INTO reparto_docente (' in sql for sql, _ in c.consultas)
    assert not any(sql.startswith('DELETE') for sql, _ in c.consultas)


def test_confirmacion_inserta_limpia_solo_actividades_y_registra(instalar):
    c = Cursor()
    repo = instalar(c)
    version = repo.confirmar_borrador(1, [dict(actividad_id=11, codigo='A', codigo_grupo='G', tipo='GD', horas=6)], {}, 7, 3, 9)
    assert version == 4
    assert any('INSERT INTO reparto_docente (' in sql and args == (1, 11, 6) for sql, args in c.consultas)
    borrados = [(sql, args) for sql, args in c.consultas if sql.startswith('DELETE')]
    assert len(borrados) == 1 and borrados[0][1] == (1, [11])
    assert 'actividad_id = ANY' in borrados[0][0]
    assert any('INSERT INTO ordenacion_eventos' in sql and args[:3] == (7, 9, 'TURNO_CONFIRMADO') for sql, args in c.consultas)

@pytest.mark.parametrize('caso', ['ausente', 'decidida', 'obsoleta', 'vacia', 'linea', 'actividad_ajena', 'profesor_ajeno', 'negativas', 'cuota', 'carga'])
def test_reparacion_invalida_no_borra_repartos(instalar, caso):
    plan = [dict(profesor_id=1, actividad_id=11, horas=6)]
    c = Cursor(plan=plan)
    if caso == 'ausente': c.estado = None
    if caso == 'decidida': c.estado = 'APROBADA'
    if caso == 'obsoleta': c.version = 4
    if caso == 'vacia': c.plan = []
    if caso == 'linea': c.plan = [{}]
    if caso == 'actividad_ajena': plan[0]['actividad_id'] = 99
    if caso == 'profesor_ajeno': plan[0]['profesor_id'] = 99
    if caso == 'negativas': plan[0]['horas'] = -6
    if caso == 'cuota': plan[0]['horas'] = 5
    if caso == 'carga':
        original = c.fetchall
        c.fetchall = lambda: [(1, 7)] if c.ultima.startswith('SELECT profesor.id') else original()
    repo = instalar(c)
    with pytest.raises(ConcurrentModification if caso == 'obsoleta' else ConstraintViolation):
        repo.decidir_propuesta_conflicto(5, 7, True, 9)
    assert not c.lotes
    assert not any(sql.startswith(('DELETE', 'UPDATE')) for sql, _ in c.consultas)


def test_reparacion_valida_sustituye_solo_area_y_avanza_version(instalar):
    c = Cursor(plan=[dict(profesor_id=1, actividad_id=11, horas=6)])
    resultado = instalar(c).decidir_propuesta_conflicto(5, 7, True, 9)
    assert resultado['estado'] == 'APROBADA' and resultado['version'] == 4
    assert c.lotes == [[(1, 11, 6.0)]]
    borrados = [(sql, args) for sql, args in c.consultas if sql.startswith('DELETE')]
    assert len(borrados) == 3
    assert all('area_id=%s' in sql and args == (7,) for sql, args in borrados)
