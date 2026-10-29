"""
Tests - core/permissions.py y core/config.py
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import types
from enum import Enum

def _ensure_schemas():
    """Garantiza que RolUsuario esté disponible antes de importar permissions."""
    mod = sys.modules.get("models.schemas")
    if mod is None or not hasattr(mod, "RolUsuario"):
        class _RolUsuario(str, Enum):
            ADMIN = "admin"; PROFESOR = "profesor"
            RESPONSABLE_AREA = "responsable_area"
            RESPONSABLE_DEPARTAMENTO = "responsable_departamento"
        class _Schema:
            def __init__(self, **kwargs):
                for k, v in kwargs.items(): setattr(self, k, v)
        if mod is None:
            mod = types.ModuleType("models.schemas")
            sys.modules["models.schemas"] = mod
            m = types.ModuleType("models")
            m.schemas = mod
            sys.modules["models"] = m
        mod.RolUsuario = _RolUsuario
        mod.ProfesorEstadoSchema = type("ProfesorEstadoSchema", (_Schema,), {})
        if "core.permissions" in sys.modules:
            del sys.modules["core.permissions"]
_ensure_schemas()

from core.permissions import (
    require_admin,
    can_modify_draft,
    can_confirm_turn,
    can_create_profesor,
    can_reset_ordenacion,
)
from core.exceptions import PermissionDenied, NotYourTurn


class TestRequireAdmin:
    def test_admin_pasa(self):
        require_admin("admin")


    def test_responsable_area_lanza_excepcion(self):
        with pytest.raises(PermissionDenied):
            require_admin("responsable_area")

    def test_responsable_depto_lanza_excepcion(self):
        with pytest.raises(PermissionDenied):
            require_admin("responsable_departamento")

    def test_rol_vacio_lanza_excepcion(self):
        with pytest.raises(PermissionDenied):
            require_admin("")

    def test_mensaje_claro(self):
        with pytest.raises(PermissionDenied) as error:
            require_admin("profesor")
        assert error.value.message.strip()


class TestCanModifyDraft:
    def test_admin_siempre_puede(self):
        assert can_modify_draft("admin", 1, 5, "García, Ana", "López, Pedro") is True

    def test_profesor_puede_su_propio_turno(self):
        assert can_modify_draft("profesor", 5, 5, "García, Ana", "García, Ana") is True

    def test_profesor_no_puede_borrador_ajeno(self):
        with pytest.raises(PermissionDenied):
            can_modify_draft("profesor", 5, 9, "López, Pedro", "López, Pedro")

    def test_profesor_no_puede_fuera_de_su_turno(self):
        with pytest.raises(NotYourTurn):
            can_modify_draft("profesor", 5, 5, "García, Ana", "López, Pedro")

    def test_responsable_departamento_puede_en_su_ambito_y_turno(self):
        assert can_modify_draft(
            "responsable_departamento", 2, 5, "García, Ana", "García, Ana",
            pertenece_al_ambito=True,
        ) is True

    def test_responsable_area_no_puede_fuera_de_su_ambito(self):
        with pytest.raises(PermissionDenied):
            can_modify_draft(
                "responsable_area", 2, 5, "García, Ana", "García, Ana",
                pertenece_al_ambito=False,
            )

    def test_responsable_debe_respetar_el_turno(self):
        with pytest.raises(NotYourTurn):
            can_modify_draft(
                "responsable_area", 2, 5, "García, Ana", "López, Pedro",
                pertenece_al_ambito=True,
            )

    def test_rol_desconocido_lanza_excepcion(self):
        with pytest.raises(PermissionDenied):
            can_modify_draft("hacker", 1, 1, "García, Ana", "García, Ana")


class TestCanConfirmTurn:
    def test_admin_puede_confirmar(self):
        assert can_confirm_turn("admin", 1, 5, "García, Ana", "García, Ana") is True

    def test_profesor_puede_confirmar_su_turno(self):
        assert can_confirm_turn("profesor", 5, 5, "García, Ana", "García, Ana") is True

    def test_responsable_puede_confirmar_turno_en_su_ambito(self):
        assert can_confirm_turn(
            "responsable_area", 2, 5, "García, Ana", "García, Ana",
            pertenece_al_ambito=True,
        ) is True

    def test_fuera_de_turno_lanza_excepcion(self):
        with pytest.raises((PermissionDenied, NotYourTurn)):
            can_confirm_turn("profesor", 5, 5, "García, Ana", "López, Pedro")


class TestPermisosAdmin:
    def test_admin_puede_crear_profesor(self):
        assert can_create_profesor("admin") is True

    def test_no_admin_no_puede_crear_profesor(self):
        with pytest.raises(PermissionDenied):
            can_create_profesor("profesor")

    def test_admin_puede_reset(self):
        assert can_reset_ordenacion("admin") is True

    def test_no_admin_no_puede_reset(self):
        with pytest.raises(PermissionDenied):
            can_reset_ordenacion("profesor")


class TestConfig:

    def test_horas_minimas_positivo(self):
        from core.config import settings
        assert settings.HORAS_MINIMAS > 0

    def test_paso_horas_positivo(self):
        from core.config import settings
        assert settings.PASO_HORAS > 0

    def test_project_name_no_vacio(self):
        from core.config import settings
        assert len(settings.PROJECT_NAME) > 0

    def test_cors_origins_es_lista(self):
        from core.config import settings
        assert isinstance(settings.CORS_ORIGINS, list)

    def test_api_prefix_correcto(self):
        from core.config import settings
        assert settings.API_V1_PREFIX.startswith("/")


class TestJerarquiaExcepciones:
    def test_domain_exception_es_base(self):
        from core.exceptions import DomainException
        exc = DomainException("test")
        assert isinstance(exc, Exception)
        assert exc.message == "test"
        assert exc.details == {}

    def test_profesor_not_found_hereda_correctamente(self):
        from core.exceptions import ProfesorNotFound, ResourceNotFound, DomainException
        exc = ProfesorNotFound("no encontrado")
        assert isinstance(exc, ResourceNotFound)
        assert isinstance(exc, DomainException)




    def test_details_se_pasan_correctamente(self):
        from core.exceptions import DomainException
        exc = DomainException("test", details={"campo": "valor"})
        assert exc.details == {"campo": "valor"}

    def test_str_representation(self):
        from core.exceptions import ProfesorNotFound
        exc = ProfesorNotFound("Profesor 5 no encontrado.")
        assert "Profesor 5" in str(exc)
