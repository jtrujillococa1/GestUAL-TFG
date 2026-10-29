"""Rutas de permisos reales mediante HTTP; identidad y repositorios controlados."""
from types import SimpleNamespace
from unittest.mock import Mock
from contextlib import contextmanager
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.routes import ordenacion as rutas
from core.auth import get_current_user

@pytest.mark.parametrize('rol,propio,turno,esperado', [
    ('profesor', True, True, 200), ('profesor', False, True, 403),
    ('profesor', True, False, 403), ('psi', True, True, 403),
    ('responsable_area', True, True, 200), ('responsable_area', False, True, 403),
    ('responsable_departamento', True, True, 200), ('responsable_departamento', False, True, 403),
])
def test_confirmacion_http_respeta_identidad_ambito_y_turno(monkeypatch, rol, propio, turno, esperado):
    perfil = dict(id=1, usuario_id=9 if propio else 10, area_id=7, area_ids=[7],
                  departamento_id=3, horas_objetivo_por_area={7: 6}, es_psi=False)
    repo = Mock()
    repo.find_by_nombre_completo.return_value = perfil
    repo.find_by_usuario_id.return_value = {'id': 1 if propio else 2}
    monkeypatch.setattr(rutas, 'ProfesorRepository', lambda: repo)
    monkeypatch.setattr(rutas, 'obtener_ambito_gestor', lambda *_: {'areas': {7} if propio else {8}, 'departamentos': {3} if propio else {4}})
    servicio = Mock()
    # Primera consulta: turno a confirmar; segunda: validación dentro del permiso.
    servicio.get_profesor_actual.side_effect = ['García, Ana', 'García, Ana' if turno else 'Otro, Docente']
    servicio.confirmar_turno.return_value = dict(ok=True, profesor_confirmado='García, Ana', siguiente_profesor=None, ordenacion_terminada=True, version=4)
    monkeypatch.setattr(rutas, 'OrdenacionService', lambda: servicio)
    @contextmanager
    def edicion_controlada(_nombre):
        yield
    monkeypatch.setattr(rutas, '_edicion_docente', edicion_controlada)
    app = FastAPI()
    app.include_router(rutas.router)
    app.dependency_overrides[get_current_user] = lambda: {'rol': rol, 'user_id': 9}
    respuesta = TestClient(app).post('/api/v1/confirmar-turno?area_id=7&version_ordenacion=3')
    assert respuesta.status_code == esperado, respuesta.text
    if esperado == 200:
        servicio.confirmar_turno.assert_called_once_with(7, 3, 9)
        assert respuesta.json()['version'] == 4
    else:
        servicio.confirmar_turno.assert_not_called()

