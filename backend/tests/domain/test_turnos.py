"""
Tests - domain/ordenacion/turnos.py

Cubre:
- calcular_nombre_completo
- calcular_horas_por_profesor
- clasificar_profesores
- obtener_profesor_actual
- detectar_incidencias
- validar_turno_completo
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from domain.ordenacion.turnos import (
    calcular_nombre_completo,
    calcular_horas_por_profesor,
    clasificar_profesores,
    obtener_profesor_actual,
    detectar_incidencias,
    validar_turno_completo,
)

_ProfesorEstadoSchema = sys.modules["models.schemas"].ProfesorEstadoSchema

def _make_estado(**kwargs):
    return _ProfesorEstadoSchema(**kwargs)


# ═══════════════════════════════════════════════════════════════
# calcular_nombre_completo
# ═══════════════════════════════════════════════════════════════

class TestCalcularNombreCompleto:
    def test_formato_correcto(self):
        assert calcular_nombre_completo("Ana", "García") == "García, Ana"

    def test_nombre_compuesto(self):
        assert calcular_nombre_completo("María José", "López Martínez") == "López Martínez, María José"

    def test_espacios_respetados(self):
        assert calcular_nombre_completo("Pedro", "De la Torre") == "De la Torre, Pedro"

    def test_formato_con_coma(self):
        nombre = calcular_nombre_completo("Juan", "Pérez")
        assert "," in nombre
        assert nombre.startswith("Pérez")


# ═══════════════════════════════════════════════════════════════
# calcular_horas_por_profesor
# ═══════════════════════════════════════════════════════════════

class TestCalcularHorasPorProfesor:
    def test_sin_confirmadas_devuelve_vacio(self):
        assert calcular_horas_por_profesor([], []) == {}

    def test_una_eleccion_simple(self):
        confirmadas = [{"profesor": "García, Ana", "horas": 6.0}]
        resultado = calcular_horas_por_profesor([], confirmadas)
        assert resultado["García, Ana"] == 6.0

    def test_acumula_horas_mismo_profesor(self):
        confirmadas = [
            {"profesor": "García, Ana", "horas": 6.0},
            {"profesor": "García, Ana", "horas": 4.0},
        ]
        resultado = calcular_horas_por_profesor([], confirmadas)
        assert resultado["García, Ana"] == 10.0

    def test_multiples_profesores(self):
        confirmadas = [
            {"profesor": "García, Ana", "horas": 6.0},
            {"profesor": "López, Pedro", "horas": 4.0},
            {"profesor": "García, Ana", "horas": 6.0},
        ]
        resultado = calcular_horas_por_profesor([], confirmadas)
        assert resultado["García, Ana"] == 12.0
        assert resultado["López, Pedro"] == 4.0

    def test_horas_como_string(self):
        confirmadas = [{"profesor": "García, Ana", "horas": "6.0"}]
        resultado = calcular_horas_por_profesor([], confirmadas)
        assert resultado["García, Ana"] == 6.0


# ═══════════════════════════════════════════════════════════════
# clasificar_profesores
# ═══════════════════════════════════════════════════════════════

class TestClasificarProfesores:
    def test_sin_confirmadas_todos_pendientes(self, profesores_base):
        completados, pendientes = clasificar_profesores(profesores_base, {})
        assert len(completados) == 0
        assert len(pendientes) == 3

    def test_uno_completado(self, profesores_base):
        horas = {"García, Ana": 24.0}
        completados, pendientes = clasificar_profesores(profesores_base, horas)
        assert len(completados) == 1
        assert completados[0].nombre == "Ana"
        assert len(pendientes) == 2

    def test_todos_completados(self, profesores_base):
        horas = {
            "García, Ana": 24.0,
            "López, Pedro": 12.0,
            "Martínez, Carmen": 18.0,
        }
        completados, pendientes = clasificar_profesores(profesores_base, horas)
        assert len(completados) == 3
        assert len(pendientes) == 0

    def test_psi_incluido_gestionado_por_responsable(self):
        profesores = [
            {"id": 1, "nombre": "Ana", "apellidos": "García", "categoria": "Titular",
             "carga_docente": 24.0, "area_id": 1, "es_psi": False},
            {"id": 2, "nombre": "Bot", "apellidos": "PSI", "categoria": "PSI",
             "carga_docente": 0.0, "area_id": 1, "es_psi": True},
        ]
        completados, pendientes = clasificar_profesores(profesores, {})
        assert len(completados) + len(pendientes) == 2

    def test_horas_restantes_calculadas_correctamente(self, profesores_base):
        horas = {"García, Ana": 10.0}
        _, pendientes = clasificar_profesores(profesores_base, horas)
        ana = next(p for p in pendientes if p.nombre == "Ana")
        assert ana.horas_restantes == 14.0

    def test_tolerancia_en_completado(self):
        profesores = [
            {"id": 1, "nombre": "Ana", "apellidos": "García", "categoria": "Titular",
             "carga_docente": 24.0, "area_id": 1, "es_psi": False},
        ]
        horas = {"García, Ana": 23.995}
        completados, pendientes = clasificar_profesores(profesores, horas)
        assert len(completados) == 1

    def test_orden_preservado(self, profesores_base):
        _, pendientes = clasificar_profesores(profesores_base, {})
        nombres = [p.nombre for p in pendientes]
        assert nombres == ["Ana", "Pedro", "Carmen"]


# ═══════════════════════════════════════════════════════════════
# obtener_profesor_actual
# ═══════════════════════════════════════════════════════════════

class TestObtenerProfesorActual:
    def test_sin_pendientes_devuelve_none(self):
        assert obtener_profesor_actual([]) is None

    def test_primer_pendiente_es_el_actual(self):
        pendientes = [
            _make_estado(nombre="Ana",   apellidos="García",  horas_restantes=24.0, carga_docente=24.0),
            _make_estado(nombre="Pedro", apellidos="López",   horas_restantes=12.0, carga_docente=12.0),
        ]
        assert obtener_profesor_actual(pendientes) == "García, Ana"

    def test_devuelve_formato_apellidos_nombre(self):
        pendientes = [
            _make_estado(nombre="María", apellidos="De la Vega", horas_restantes=6.0, carga_docente=6.0),
        ]
        assert obtener_profesor_actual(pendientes) == "De la Vega, María"


# ═══════════════════════════════════════════════════════════════
# detectar_incidencias
# ═══════════════════════════════════════════════════════════════

class TestDetectarIncidencias:
    def test_sin_pendientes_no_hay_incidencia(self):
        assert detectar_incidencias([]) is None

    def test_horas_negativas_es_incidencia(self):
        pendientes = [_make_estado(nombre="Ana", apellidos="García",
                                   horas_restantes=-2.0, carga_docente=24.0)]
        incidencia = detectar_incidencias(pendientes)
        assert incidencia is not None
        assert "INCIDENCIA" in incidencia

    def test_horas_mayores_que_carga_es_incidencia(self):
        pendientes = [_make_estado(nombre="Ana", apellidos="García",
                                   horas_restantes=30.0, carga_docente=24.0)]
        assert detectar_incidencias(pendientes) is not None

    def test_horas_normales_no_hay_incidencia(self):
        pendientes = [_make_estado(nombre="Ana", apellidos="García",
                                   horas_restantes=12.0, carga_docente=24.0)]
        assert detectar_incidencias(pendientes) is None


# ═══════════════════════════════════════════════════════════════
# validar_turno_completo
# ═══════════════════════════════════════════════════════════════

class TestValidarTurnoCompleto:
    def setup_method(self):
        self.profesores = [
            {"nombre": "Ana", "apellidos": "García", "horas_objetivo": 24.0},
        ]

    def test_turno_completo_exacto(self):
        elecciones = [{"profesor": "García, Ana", "horas": 24.0}]
        ok, restantes, error = validar_turno_completo("García, Ana", self.profesores, elecciones)
        assert ok is True
        assert error is None

    def test_turno_completo_con_multiples_elecciones(self):
        elecciones = [{"profesor": "García, Ana", "horas": h} for h in [6.0, 6.0, 6.0, 6.0]]
        ok, _, _ = validar_turno_completo("García, Ana", self.profesores, elecciones)
        assert ok is True

    def test_turno_incompleto(self):
        elecciones = [{"profesor": "García, Ana", "horas": 10.0}]
        ok, restantes, error = validar_turno_completo("García, Ana", self.profesores, elecciones)
        assert ok is False
        assert restantes == 14.0
        assert "Faltan" in error

    def test_turno_excedido(self):
        elecciones = [{"profesor": "García, Ana", "horas": 26.0}]
        ok, restantes, error = validar_turno_completo("García, Ana", self.profesores, elecciones)
        assert ok is False
        assert restantes < 0
        assert "paso" in error

    def test_profesor_no_encontrado(self):
        ok, _, error = validar_turno_completo("Desconocido, X", self.profesores, [])
        assert ok is False
        assert "no encontrado" in error

    def test_tolerancia_aceptada(self):
        elecciones = [{"profesor": "García, Ana", "horas": 23.995}]
        ok, _, _ = validar_turno_completo("García, Ana", self.profesores, elecciones)
        assert ok is True

    def test_ignora_elecciones_de_otros_profesores(self):
        elecciones = [
            {"profesor": "García, Ana", "horas": 12.0},
            {"profesor": "López, Pedro", "horas": 12.0},
        ]
        ok, restantes, _ = validar_turno_completo("García, Ana", self.profesores, elecciones)
        assert ok is False
        assert restantes == 12.0
