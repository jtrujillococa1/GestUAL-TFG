"""
Tests - domain/ordenacion/viabilidad.py
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from domain.ordenacion.viabilidad import (
    calcular_horas_restantes_actividad,
    calcular_horas_restantes_profesor,
    actividad_en_borrador,
    generar_candidatos_horas,
    categorizar_opcion,
    construir_opcion_dict,
    priorizar_opciones,
)


class TestCalcularHorasRestantesActividad:
    def setup_method(self):
        self.actividad = {
            "codigo": "PROG", "codigo_grupo": "A",
            "tipo": "GD", "horas_totales": 6.0,
        }

    def test_sin_asignaciones_devuelve_total(self):
        assert calcular_horas_restantes_actividad(self.actividad, []) == 6.0

    def test_totalmente_asignada(self):
        elecciones = [{"profesor": "García, Ana", "codigo": "PROG", "codigo_grupo": "A",
                       "tipo": "GD", "tipo_actividad": "GD", "horas": 6.0}]
        assert calcular_horas_restantes_actividad(self.actividad, elecciones) == 0.0

    def test_parcialmente_asignada(self):
        elecciones = [{"profesor": "García, Ana", "codigo": "PROG", "codigo_grupo": "A",
                       "tipo": "GD", "tipo_actividad": "GD", "horas": 4.0}]
        assert calcular_horas_restantes_actividad(self.actividad, elecciones) == 2.0

    def test_asignada_entre_varios_profesores(self):
        elecciones = [
            {"profesor": "García, Ana", "codigo": "PROG", "codigo_grupo": "A",
             "tipo": "GD", "tipo_actividad": "GD", "horas": 3.0},
            {"profesor": "López, Pedro", "codigo": "PROG", "codigo_grupo": "A",
             "tipo": "GD", "tipo_actividad": "GD", "horas": 3.0},
        ]
        assert calcular_horas_restantes_actividad(self.actividad, elecciones) == 0.0

    def test_no_confunde_actividades_distintas(self):
        elecciones = [{"profesor": "García, Ana", "codigo": "BBDD", "codigo_grupo": "A",
                       "tipo": "GD", "tipo_actividad": "GD", "horas": 6.0}]
        assert calcular_horas_restantes_actividad(self.actividad, elecciones) == 6.0

    def test_usa_tipo_actividad_como_fallback(self):
        elecciones = [{"profesor": "García, Ana", "codigo": "PROG", "codigo_grupo": "A",
                       "tipo_actividad": "GD", "horas": 3.0}]
        assert calcular_horas_restantes_actividad(self.actividad, elecciones) == 3.0


class TestCalcularHorasRestantesProfesor:
    def setup_method(self):
        self.profesores = [
            {"nombre": "García, Ana", "horas_objetivo": 24.0},
            {"nombre": "López, Pedro", "horas_objetivo": 12.0},
        ]

    def test_sin_asignaciones_devuelve_carga_total(self):
        assert calcular_horas_restantes_profesor("García, Ana", self.profesores, []) == 24.0

    def test_profesor_no_encontrado_devuelve_none(self):
        assert calcular_horas_restantes_profesor("Desconocido, X", self.profesores, []) is None

    def test_con_asignaciones_parciales(self):
        elecciones = [{"profesor": "García, Ana", "horas": 10.0}]
        assert calcular_horas_restantes_profesor("García, Ana", self.profesores, elecciones) == 14.0

    def test_no_confunde_profesores(self):
        elecciones = [{"profesor": "López, Pedro", "horas": 12.0}]
        assert calcular_horas_restantes_profesor("García, Ana", self.profesores, elecciones) == 24.0

    def test_turno_completado(self):
        elecciones = [{"profesor": "García, Ana", "horas": 24.0}]
        assert calcular_horas_restantes_profesor("García, Ana", self.profesores, elecciones) == 0.0


class TestActividadEnBorrador:
    def setup_method(self):
        self.actividad = {"codigo": "PROG", "codigo_grupo": "A", "tipo": "GD"}

    def test_borrador_vacio_devuelve_false(self):
        assert actividad_en_borrador(self.actividad, []) is False

    def test_actividad_presente_devuelve_true(self):
        borrador = [{"codigo": "PROG", "codigo_grupo": "A", "tipo": "GD",
                     "tipo_actividad": "GD", "horas": 6.0, "profesor": "García, Ana"}]
        assert actividad_en_borrador(self.actividad, borrador) is True

    def test_actividad_diferente_devuelve_false(self):
        borrador = [{"codigo": "BBDD", "codigo_grupo": "A", "tipo": "GD",
                     "tipo_actividad": "GD", "horas": 6.0, "profesor": "García, Ana"}]
        assert actividad_en_borrador(self.actividad, borrador) is False

    def test_mismo_codigo_grupo_diferente_devuelve_false(self):
        borrador = [{"codigo": "PROG", "codigo_grupo": "B", "tipo": "GD",
                     "tipo_actividad": "GD", "horas": 6.0, "profesor": "García, Ana"}]
        assert actividad_en_borrador(self.actividad, borrador) is False

    def test_mismo_codigo_tipo_diferente_devuelve_false(self):
        borrador = [{"codigo": "PROG", "codigo_grupo": "A", "tipo": "GT",
                     "tipo_actividad": "GT", "horas": 4.0, "profesor": "García, Ana"}]
        assert actividad_en_borrador(self.actividad, borrador) is False


class TestGenerarCandidatosHoras:
    def test_genera_candidatos_desde_maximo(self):
        candidatos = generar_candidatos_horas(6.0, 24.0)
        assert candidatos[0] == 6.0

    def test_minimo_es_0_5(self):
        candidatos = generar_candidatos_horas(6.0, 24.0)
        assert candidatos[-1] == 0.1

    def test_paso_es_0_5(self):
        candidatos = generar_candidatos_horas(3.0, 24.0)
        assert candidatos == [3.0, 2.9, 2.8, 2.7, 2.6, 2.5, 2.4, 2.3, 2.2, 2.1, 2.0, 1.9, 1.8, 1.7, 1.6, 1.5, 1.4, 1.3, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]

    def test_limite_por_profesor(self):
        candidatos = generar_candidatos_horas(6.0, 2.0)
        assert candidatos[0] == 2.0

    def test_limite_por_actividad(self):
        candidatos = generar_candidatos_horas(3.0, 24.0)
        assert candidatos[0] == 3.0

    def test_por_debajo_del_minimo_devuelve_vacio(self):
        assert generar_candidatos_horas(0.0, 24.0) == []

    def test_exactamente_el_minimo(self):
        assert generar_candidatos_horas(0.1, 24.0) == [0.1]


class TestCategorizarOpcion:
    def test_cero_horas_es_completa_turno(self):
        assert categorizar_opcion(0.0) == "COMPLETA_TURNO"

    def test_casi_cero_es_completa_turno(self):
        assert categorizar_opcion(0.005) == "COMPLETA_TURNO"

    def test_una_hora_es_casi_completa(self):
        assert categorizar_opcion(1.0) == "CASI_COMPLETA"

    def test_media_hora_es_casi_completa(self):
        assert categorizar_opcion(0.5) == "CASI_COMPLETA"

    def test_mas_de_una_hora_es_viable(self):
        assert categorizar_opcion(1.5) == "VIABLE"

    def test_muchas_horas_es_viable(self):
        assert categorizar_opcion(20.0) == "VIABLE"


class TestPriorizarOpciones:
    def _make_opcion(self, categoria, total_repartos, actividades_divididas, horas):
        return {
            "categoria": categoria,
            "total_repartos": total_repartos,
            "actividades_divididas": actividades_divididas,
            "opcion": {"horas": horas, "codigo": "X", "tipo": "GD",
                       "codigo_grupo": "A", "profesor": "García, Ana"},
        }

    def test_completa_turno_primero(self):
        opciones = [
            self._make_opcion("VIABLE", 3, 0, 4.0),
            self._make_opcion("COMPLETA_TURNO", 3, 0, 6.0),
            self._make_opcion("CASI_COMPLETA", 3, 0, 5.0),
        ]
        ordenadas = priorizar_opciones(opciones)
        assert ordenadas[0]["categoria"] == "COMPLETA_TURNO"

    def test_casi_completa_antes_que_viable(self):
        opciones = [
            self._make_opcion("VIABLE", 3, 0, 4.0),
            self._make_opcion("CASI_COMPLETA", 3, 0, 5.0),
        ]
        assert priorizar_opciones(opciones)[0]["categoria"] == "CASI_COMPLETA"

    def test_menos_divididas_primero(self):
        opciones = [
            self._make_opcion("VIABLE", 5, 2, 4.0),
            self._make_opcion("VIABLE", 5, 0, 4.0),
        ]
        assert priorizar_opciones(opciones)[0]["actividades_divididas"] == 0

    def test_menos_repartos_primero(self):
        opciones = [
            self._make_opcion("VIABLE", 5, 0, 4.0),
            self._make_opcion("VIABLE", 3, 0, 4.0),
        ]
        assert priorizar_opciones(opciones)[0]["total_repartos"] == 3

    def test_mas_horas_primero_si_todo_igual(self):
        opciones = [
            self._make_opcion("VIABLE", 3, 0, 2.0),
            self._make_opcion("VIABLE", 3, 0, 4.0),
        ]
        assert priorizar_opciones(opciones)[0]["opcion"]["horas"] == 4.0

    def test_lista_vacia_devuelve_vacia(self):
        assert priorizar_opciones([]) == []

    def test_un_elemento_devuelve_el_mismo(self):
        opcion = self._make_opcion("VIABLE", 3, 0, 4.0)
        assert priorizar_opciones([opcion]) == [opcion]
