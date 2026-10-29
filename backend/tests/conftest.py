"""
conftest.py raíz - instala mocks VIA pytest_configure (primer hook que se ejecuta).
"""
import pytest
import sys
import types
import os
from enum import Enum

# Las pruebas unitarias no abren conexiones reales, pero varios módulos
# cargan la configuración al importarse. Mantener valores inertes permite
# probar su lógica sin depender del fichero privado .env de cada máquina.
os.environ.setdefault("DB_PASSWORD", "prueba-sin-conexion")
os.environ.setdefault("JWT_SECRET_KEY", "clave-de-prueba-para-conflictos-de-32-caracteres")

class _Schema:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

class _RolUsuario(str, Enum):
    ADMIN                    = "admin"
    PROFESOR                 = "profesor"
    RESPONSABLE_AREA         = "responsable_area"
    RESPONSABLE_DEPARTAMENTO = "responsable_departamento"

def _install():
    mock = types.ModuleType("models.schemas")
    mock.ProfesorEstadoSchema        = type("ProfesorEstadoSchema", (_Schema,), {})
    mock.EleccionSchema              = type("EleccionSchema", (_Schema,), {})
    mock.OpcionSchema                = type("OpcionSchema", (_Schema,), {})
    mock.BorradorSchema              = type("BorradorSchema", (_Schema,), {})
    mock.EstadoOrdenacionSchema      = type("EstadoOrdenacionSchema", (_Schema,), {})
    mock.ConfirmacionResultadoSchema = type("ConfirmacionResultadoSchema", (_Schema,), {})
    # El paquete api.routes carga también las rutas de control e historial de
    # ordenación durante la colección; mantener su contrato mínimo en el mock.
    mock.ControlOrdenacionSchema      = type("ControlOrdenacionSchema", (_Schema,), {})
    mock.EventoOrdenacionSchema       = type("EventoOrdenacionSchema", (_Schema,), {})
    mock.RolUsuario                  = _RolUsuario
    mock.TipoActividad               = type("TipoActividad", (), {"GD":"GD","GT":"GT","GL":"GL","GA":"GA"})
    mock.CategoriaDocente            = type("CategoriaDocente", (), {})
    models_mod = types.ModuleType("models")
    models_mod.schemas = mock
    sys.modules["models"]         = models_mod
    sys.modules["models.schemas"] = mock

def pytest_configure(config):
    """Hook más temprano de pytest - se ejecuta antes de cualquier import de tests."""
    _install()

# ✅ FIXTURE FALTANTE - Agregarlo aquí
@pytest.fixture
def profesores_base():
    """Fixture con 3 profesores base para tests de clasificación."""
    return [
        {
            "id": 1,
            "nombre": "Ana",
            "apellidos": "García",
            "categoria": "Titular",
            "carga_docente": 24.0,
            "area_id": 1,
            "es_psi": False,
        },
        {
            "id": 2,
            "nombre": "Pedro",
            "apellidos": "López",
            "categoria": "Titular",
            "carga_docente": 12.0,
            "area_id": 1,
            "es_psi": False,
        },
        {
            "id": 3,
            "nombre": "Carmen",
            "apellidos": "Martínez",
            "categoria": "Titular",
            "carga_docente": 18.0,
            "area_id": 1,
            "es_psi": False,
        },
    ]
