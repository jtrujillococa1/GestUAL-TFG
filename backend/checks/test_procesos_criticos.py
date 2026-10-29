"""Regresión de procesos críticos; repositorios simulados, modelos reales."""
from types import SimpleNamespace
from unittest.mock import Mock
from contextlib import contextmanager
import pytest
from core.exceptions import IncompleteTurn, ViabilityLost, OrdenacionClosed, OrdenacionFinished, ConcurrentModification
from services import ordenacion_service as modulo
from services.ordenacion_service import OrdenacionService

@pytest.fixture
def escenario(monkeypatch):
    servicio = OrdenacionService()
    profesor = dict(id=1, nombre='Ana', apellidos='García', area_id=7,
                    area_ids=[7], carga_docente=6, horas_objetivo_por_area={7: 6})
    actividad = dict(id=11, codigo='A', codigo_grupo='G', grupo='G', tipo='GD',
                     area_id=7, horas_totales=6, requiere_horario=False)
    eleccion = dict(profesor='García, Ana', actividad_id=11, codigo='A',
                    codigo_grupo='G', grupo='G', tipo='GD', horas=6)
    servicio.profesor_repo = Mock()
    servicio.profesor_repo.find_for_ordenacion.return_value = [profesor]
    servicio.actividad_repo = Mock()
    servicio.actividad_repo.find_for_ordenacion.return_value = [actividad]
    servicio.reparto_repo = Mock()
    servicio.reparto_repo.get_control_area.return_value = dict(version=3, cerrada=False, iniciada=True)
    servicio.reparto_repo.find_all_confirmadas.return_value = []
    servicio.reparto_repo.find_borrador_by_profesor.return_value = [eleccion]
    servicio.reparto_repo.confirmar_borrador.return_value = 4
    servicio.mapeo_repo = Mock()
    servicio.mapeo_repo.get_mapeos.return_value = {'prof_a_id': {'García, Ana': 1}, 'actividad_a_id': {}}
    servicio.get_profesor_actual = Mock(return_value='García, Ana')
    servicio.get_estado = Mock(return_value=SimpleNamespace(profesor_actual=None))
    motor = Mock(return_value={'viable': True})
    monkeypatch.setattr(modulo, 'resolver_reparto_en_area', motor)
    calendario = Mock()
    monkeypatch.setattr('services.planificacion_docente_service.PlanificacionDocenteService', lambda: calendario)
    cache = Mock()
    monkeypatch.setattr(modulo.solver_cache, 'clear', cache)
    return servicio, motor, calendario, cache

@pytest.mark.parametrize('caso,excepcion', [
    ('cerrada', OrdenacionClosed), ('preparacion', OrdenacionClosed),
    ('terminada', OrdenacionFinished), ('vacio', IncompleteTurn),
    ('incompleto', IncompleteTurn), ('exceso', IncompleteTurn),
    ('inviable', ViabilityLost),
])
def test_confirmacion_rechazada_no_escribe(escenario, caso, excepcion):
    s, motor, calendario, cache = escenario
    control = s.reparto_repo.get_control_area.return_value
    if caso == 'cerrada': control['cerrada'] = True
    if caso == 'preparacion': control['iniciada'] = False
    if caso == 'terminada': s.get_profesor_actual.return_value = None
    if caso == 'vacio': s.reparto_repo.find_borrador_by_profesor.return_value = []
    if caso in ('incompleto', 'exceso'):
        s.reparto_repo.find_borrador_by_profesor.return_value[0]['horas'] = 5 if caso == 'incompleto' else 7
    if caso == 'inviable': motor.return_value = {'viable': False, 'diagnostico': ['Sin reparto factible']}
    with pytest.raises(excepcion): s.confirmar_turno(7, 3, 9)
    s.reparto_repo.confirmar_borrador.assert_not_called()
    calendario.regenerar_actividades.assert_not_called()
    cache.assert_not_called()

@pytest.mark.parametrize('fallo_calendario', [False, True])
def test_confirmacion_valida_persiste_y_actualiza_proyecciones(escenario, fallo_calendario):
    s, motor, calendario, cache = escenario
    if fallo_calendario: calendario.regenerar_actividades.side_effect = RuntimeError('Proyección no disponible')
    resultado = s.confirmar_turno(7, 3, 9)
    assert resultado.ok and resultado.version == 4 and resultado.ordenacion_terminada
    s.reparto_repo.confirmar_borrador.assert_called_once_with(1, s.reparto_repo.find_borrador_by_profesor.return_value, {}, 7, 3, 9)
    calendario.regenerar_actividades.assert_called_once_with([11])
    cache.assert_called_once()
    s.mapeo_repo.clear_cache.assert_called_once()
    assert motor.call_args.args[3] == 7


def test_version_obsoleta_impide_efectos_posteriores(escenario):
    s, motor, calendario, cache = escenario
    s.reparto_repo.confirmar_borrador.side_effect = ConcurrentModification('Estado modificado')
    with pytest.raises(ConcurrentModification): s.confirmar_turno(7, 2, 9)
    assert s.reparto_repo.confirmar_borrador.call_args.args[4] == 2
    calendario.regenerar_actividades.assert_not_called()
    cache.assert_not_called()

@pytest.mark.parametrize('aprobar,fallo', [(False, False), (True, False), (True, True)])
def test_decision_reparacion_y_calendario(escenario, aprobar, fallo):
    s, _, calendario, cache = escenario
    s.reparto_repo.decidir_propuesta_conflicto.return_value = {'estado': 'APROBADA' if aprobar else 'RECHAZADA'}
    s.actividad_repo.find_for_ordenacion.return_value.append({'id': 12, 'area_id': 8})
    if fallo: calendario.regenerar_actividades.side_effect = RuntimeError('Sin calendario')
    resultado = s.decidir_propuesta_conflicto(5, 7, aprobar, 9, 'Revisión')
    s.reparto_repo.decidir_propuesta_conflicto.assert_called_once_with(5, 7, aprobar, 9, 'Revisión')
    if aprobar:
        calendario.regenerar_actividades.assert_called_once_with([11])
        cache.assert_called_once()
        assert ('advertencia_calendario' in resultado) == fallo
    else:
        calendario.regenerar_actividades.assert_not_called()
        cache.assert_not_called()

@pytest.mark.parametrize('fallo', [False, True])
def test_contexto_transaccion_confirma_o_revierte(monkeypatch, fallo):
    import db.connection as db
    conexion = Mock()
    @contextmanager
    def prestamo(): yield conexion
    monkeypatch.setattr(db, 'obtener_pool', lambda: SimpleNamespace(connection=prestamo))
    if fallo:
        with pytest.raises(RuntimeError, match='fallo escritura'):
            with db.conexion_ctx(): raise RuntimeError('fallo escritura')
        conexion.rollback.assert_called_once()
        conexion.commit.assert_not_called()
    else:
        with db.conexion_ctx() as recibida: assert recibida is conexion
        conexion.commit.assert_called_once()
        conexion.rollback.assert_not_called()
