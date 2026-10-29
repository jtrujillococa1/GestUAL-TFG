"""
Tests - domain/ordenacion/conflictos.py + scheduler.py
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from domain.ordenacion.conflictos import (
    calcular_equilibrio_horas,
    calcular_riesgo_global,
    calcular_riesgo_estado,
    evaluar_riesgo_opcion,
    preparar_contexto_riesgo,
)
from domain.ordenacion.scheduler import (
    detectar_conflicto_en_elecciones,
    detectar_solape_en_elecciones,
    validar_opcion_con_solver,
    buscar_opciones_viables,
    confirmar_bloque_con_solver,
)


def _p(nombre, horas):
    return {"nombre": nombre, "horas_objetivo": horas}

def _a(codigo, tipo, grupo, horas):
    return {"codigo": codigo, "tipo": tipo, "codigo_grupo": grupo,
            "grupo": f"Grupo {grupo}", "turno": "M", "duracion": "C1",
            "horas_actividad": horas, "horas_totales": horas}

def _e(profesor, codigo, tipo, grupo, horas):
    return {"profesor": profesor, "codigo": codigo, "tipo": tipo,
            "tipo_actividad": tipo, "codigo_grupo": grupo,
            "grupo": f"Grupo {grupo}", "horas": horas}


def test_solape_reserva_el_horario_completo_para_cada_profesor():
    actividades = [
        {
            "id": 1, "codigo": "A", "tipo": "GT", "codigo_grupo": "A1", "grupo": "A1",
            "nombre_asignatura": "Primera", "duracion": "C1", "horas_totales": 4,
            "horario_detallado": [
                {"fecha": "2026-10-05", "dia": "Lunes", "inicio": "09:00", "fin": "11:00"},
                {"fecha": "2026-10-12", "dia": "Lunes", "inicio": "09:00", "fin": "11:00"},
            ],
        },
        {
            "id": 2, "codigo": "B", "tipo": "GT", "codigo_grupo": "B1", "grupo": "B1",
            "nombre_asignatura": "Segunda", "duracion": "C1", "horas_totales": 2,
            "horario_detallado": [
                {"fecha": "2026-10-05", "dia": "Lunes", "inicio": "10:00", "fin": "12:00"},
            ],
        },
    ]
    elecciones = [
        {"profesor": "Otra, Persona", "actividad_id": 1, "horas": 2},
        {"profesor": "García, Ana", "actividad_id": 1, "horas": 2},
        {"profesor": "García, Ana", "actividad_id": 2, "horas": 2},
    ]
    # Las semanas se acuerdan después: Ana debe reservar también el día 5.
    assert detectar_solape_en_elecciones(elecciones, actividades) is not None


def test_solape_real_bloquea_dos_tramos_que_ocupan_la_misma_hora():
    actividades = [
        {
            "id": 1, "codigo": "A", "tipo": "GT", "codigo_grupo": "A1", "grupo": "A1",
            "nombre_asignatura": "Primera", "duracion": "C1", "horas_totales": 2,
            "horario_detallado": [{"fecha": "2026-10-05", "dia": "Lunes", "inicio": "09:00", "fin": "11:00"}],
        },
        {
            "id": 2, "codigo": "B", "tipo": "GT", "codigo_grupo": "B1", "grupo": "B1",
            "nombre_asignatura": "Segunda", "duracion": "C1", "horas_totales": 2,
            "horario_detallado": [{"fecha": "2026-10-05", "dia": "Lunes", "inicio": "10:00", "fin": "12:00"}],
        },
    ]
    elecciones = [
        {"profesor": "García, Ana", "actividad_id": 1, "horas": 2},
        {"profesor": "García, Ana", "actividad_id": 2, "horas": 2},
    ]
    assert detectar_solape_en_elecciones(elecciones, actividades) == "Se solapa con Segunda · B1."
    conflicto = detectar_conflicto_en_elecciones(elecciones, actividades)
    assert conflicto == {
        "motivo": "Se solapa con Segunda · B1.",
        "profesor": "García, Ana",
        "actividad_id": 1,
        "otra_actividad_id": 2,
    }

def solver_viable(e, p, a, usar_cache=True):
    return {"viable": True, "total_repartos": 3, "actividades_divididas": 0, "cached": False}

def solver_inviable(e, p, a, usar_cache=True):
    return {"viable": False, "total_repartos": 0, "actividades_divididas": 0, "cached": False}


class TestCalcularEquilibrioHoras:
    def test_sistema_equilibrado(self):
        profs = [_p("García, Ana", 12.0), _p("López, Pedro", 12.0)]
        acts  = [_a("PROG", "GD", "A", 12.0), _a("BBDD", "GD", "A", 12.0)]
        r = calcular_equilibrio_horas(profs, acts)
        assert r["equilibrado"] is True
        assert r["diferencia"] == 0.0

    def test_mas_horas_profesores(self):
        r = calcular_equilibrio_horas([_p("X", 24.0)], [_a("P", "GD", "A", 20.0)])
        assert r["equilibrado"] is False
        assert r["diferencia"] == 4.0

    def test_mas_horas_actividades(self):
        r = calcular_equilibrio_horas([_p("X", 18.0)], [_a("P", "GD", "A", 24.0)])
        assert r["equilibrado"] is False
        assert r["diferencia"] == -6.0

    def test_sistema_vacio_equilibrado(self):
        r = calcular_equilibrio_horas([], [])
        assert r["equilibrado"] is True

    def test_tolerancia_pequenas_diferencias(self):
        r = calcular_equilibrio_horas([_p("X", 12.005)], [_a("P", "GD", "A", 12.0)])
        assert r["equilibrado"] is True


class TestCalcularRiesgoGlobal:
    def setup_method(self):
        self.profs = [_p("García, Ana", 12.0), _p("López, Pedro", 12.0)]
        self.acts  = [_a("PROG", "GD", "A", 12.0), _a("BBDD", "GD", "A", 12.0)]

    def test_sin_confirmaciones_riesgo_no_es_cero(self):
        r = calcular_riesgo_global(self.profs, self.acts, [])
        assert r["riesgo"] > 0

    def test_todo_confirmado_riesgo_bajo(self):
        confirmadas = [
            _e("García, Ana", "PROG", "GD", "A", 12.0),
            _e("López, Pedro", "BBDD", "GD", "A", 12.0),
        ]
        r = calcular_riesgo_global(self.profs, self.acts, confirmadas)
        assert r["riesgo"] == 0
        assert r["nivel"] == "BAJO"

    def test_niveles_en_rango_valido(self):
        r = calcular_riesgo_global([], [], [])
        assert r["nivel"] in ["BAJO", "MODERADO", "ALTO", "CRITICO"]
        assert 0 <= r["riesgo"] <= 100

    def test_sistema_equilibrado_reduce_riesgo(self):
        r_eq   = calcular_riesgo_global([_p("X", 12.0)], [_a("P", "GD", "A", 12.0)], [])
        r_deseq= calcular_riesgo_global([_p("X", 24.0)], [_a("P", "GD", "A", 12.0)], [])
        assert r_eq["riesgo"] <= r_deseq["riesgo"]

    def test_campos_requeridos_presentes(self):
        r = calcular_riesgo_global(self.profs, self.acts, [])
        for campo in ["riesgo", "nivel", "equilibrado", "actividades_incompletas", "profesores_pendientes"]:
            assert campo in r


class TestRiesgoPorOpcion:
    def _profesor(self, nombre, horas, area_id=10):
        return {
            "id": len(nombre), "nombre": nombre, "horas_objetivo": horas,
            "area_id": area_id, "area_ids": [area_id],
        }

    def _actividad(self, actividad_id, codigo, horas, area_id=10):
        hora_inicio = "09:00" if actividad_id % 2 else "11:00"
        hora_fin = "10:30" if actividad_id % 2 else "12:30"
        return {
            "id": actividad_id, "codigo": codigo, "tipo": "GD", "codigo_grupo": "A",
            "grupo": f"Grupo {codigo}", "horas_totales": horas, "area_id": area_id,
            "duracion": "C1", "dias": "Lunes", "horario": f"Lunes {hora_inicio}-{hora_fin}",
            "horario_confirmado": True,
        }

    def _eleccion(self, profesor, actividad, horas):
        return {
            "profesor": profesor, "actividad_id": actividad["id"],
            "codigo": actividad["codigo"], "tipo": actividad["tipo"],
            "codigo_grupo": actividad["codigo_grupo"], "horas": horas,
        }

    def test_el_borrador_se_incluye_en_el_estado_de_riesgo(self):
        actividad = self._actividad(1, "BBDD", 6.0)
        contexto = preparar_contexto_riesgo([self._profesor("Ana", 6.0)], [actividad], 10)
        estado = calcular_riesgo_estado([self._eleccion("Ana", actividad, 2.0)], contexto)
        assert estado["horas_pendientes"] == 4.0

    def test_elegir_toda_la_capacidad_deja_una_cobertura_mas_fragil(self):
        profesores = [self._profesor("Ana", 6.0), self._profesor("Beto", 6.0)]
        actividades = [self._actividad(1, "BBDD", 6.0), self._actividad(2, "RED", 6.0)]
        contexto = preparar_contexto_riesgo(profesores, actividades, 10)

        riesgo_parcial = calcular_riesgo_estado(
            [self._eleccion("Ana", actividades[0], 2.0)], contexto,
        )
        riesgo_completo = calcular_riesgo_estado(
            [self._eleccion("Ana", actividades[0], 6.0)], contexto,
        )

        assert riesgo_completo["riesgo"] > riesgo_parcial["riesgo"]
        assert riesgo_completo["actividades_criticas"] == 1

    def test_el_riesgo_se_limita_al_area_evaluada(self):
        actividad_area = self._actividad(1, "BBDD", 6.0, 10)
        actividad_ajena = self._actividad(2, "FIS", 100.0, 20)
        contexto = preparar_contexto_riesgo(
            [self._profesor("Ana", 6.0, 10)], [actividad_area, actividad_ajena], 10,
        )
        estado = calcular_riesgo_estado([], contexto)
        assert estado["horas_pendientes"] == 6.0

    def test_el_solver_aporta_el_coste_de_fragmentacion_de_una_opcion(self):
        actividad = self._actividad(1, "BBDD", 6.0)
        contexto = preparar_contexto_riesgo([self._profesor("Ana", 6.0)], [actividad], 10)
        base = calcular_riesgo_estado([], contexto)
        riesgo = evaluar_riesgo_opcion(
            [self._eleccion("Ana", actividad, 6.0)],
            {"viable": True, "total_repartos": 3, "actividades_divididas": 1},
            contexto,
            base,
            {"total_repartos": 1, "actividades_divididas": 0},
        )
        assert riesgo["desglose"]["fragmentacion"] == 12
        assert riesgo["desglose"]["repartos"] == 6
        assert riesgo["impacto"] != 0


class TestValidarOpcionConSolver:
    def setup_method(self):
        self.profs = [_p("García, Ana", 24.0)]
        self.acts  = [_a("PROG", "GD", "A", 6.0)]
        self.nueva = _e("García, Ana", "PROG", "GD", "A", 6.0)

    def test_solver_viable_devuelve_viable(self):
        r = validar_opcion_con_solver(self.nueva, [], [], self.profs, self.acts, solver_viable)
        assert r["viable"] is True

    def test_solver_inviable_devuelve_inviable(self):
        r = validar_opcion_con_solver(self.nueva, [], [], self.profs, self.acts, solver_inviable)
        assert r["viable"] is False

    def test_combina_confirmadas_borrador_nueva(self):
        capturado = []
        def capturar(e, p, a, usar_cache=True):
            capturado.extend(e)
            return {"viable": True, "total_repartos": 1, "actividades_divididas": 0}

        conf = [_e("García, Ana", "BBDD", "GD", "B", 4.0)]
        borr = [_e("García, Ana", "REDES", "GD", "A", 6.0)]
        validar_opcion_con_solver(self.nueva, conf, borr, self.profs, self.acts, capturar)
        assert len(capturado) == 3


class TestBuscarOpcionesViables:
    def setup_method(self):
        self.profs = [_p("García, Ana", 24.0)]
        self.acts  = [_a("PROG", "GD", "A", 6.0)]
        self.act   = _a("PROG", "GD", "A", 6.0)

    def test_encuentra_primera_opcion_viable(self):
        r = buscar_opciones_viables("García, Ana", self.act, [6.0, 5.5, 5.0],
                                    [], [], self.profs, self.acts, solver_viable)
        assert r is not None
        assert r["horas"] == 6.0

    def test_solver_inviable_permanece_visible_como_no_viable(self):
        r = buscar_opciones_viables("García, Ana", self.act, [6.0, 5.5],
                                    [], [], self.profs, self.acts, solver_inviable)
        assert r is not None
        assert r["viable"] is False
        assert r["motivo_no_viable"]

    def test_candidatos_vacios_no_crean_opcion(self):
        r = buscar_opciones_viables("García, Ana", self.act, [],
                                    [], [], self.profs, self.acts, solver_viable)
        assert r is None

    def test_solape_se_muestra_como_no_viable(self):
        nueva = {
            **self.act,
            "id": 1,
            "duracion": "Anual",
            "dias": "Lunes",
            "horario": "Lunes 09:00-10:30",
        }
        existente = {
            **self.act,
            "id": 2,
            "codigo": "BBDD",
            "dias": "Lunes",
            "horario": "Lunes 10:00-11:30",
        }
        borrador = [{"profesor": "García, Ana", "actividad_id": 2, "horas": 3.0}]
        r = buscar_opciones_viables(
            "García, Ana", nueva, [3.0], [], borrador,
            self.profs, [nueva, existente], solver_inviable,
        )
        assert r is not None
        assert r["viable"] is False
        assert r["bloqueada_por_solape"] is True
        assert "solapa" in r["motivo_no_viable"].lower()

    def test_solape_sintetico_provisional_tambien_se_muestra_en_el_borrador(self):
        nueva = {
            **self.act,
            "id": 1,
            "duracion": "Anual",
            "dias": "Lunes",
            "horario": "Lunes 09:00-10:30",
            "origen_horario": "SINTETICO",
            "horario_confirmado": False,
        }
        existente = {
            **self.act,
            "id": 2,
            "codigo": "BBDD",
            "dias": "Lunes",
            "horario": "Lunes 10:00-11:30",
            "origen_horario": "SINTETICO",
            "horario_confirmado": False,
        }
        r = buscar_opciones_viables(
            "García, Ana", nueva, [3.0], [],
            [{"profesor": "García, Ana", "actividad_id": 2, "horas": 3.0}],
            self.profs, [nueva, existente], solver_viable,
        )
        assert r is not None
        assert r["viable"] is False
        assert r["bloqueada_por_solape"] is True

    def test_busca_hasta_encontrar_viable(self):
        contador = {"n": 0}
        def tercera_viable(e, p, a, usar_cache=True):
            contador["n"] += 1
            return {"viable": contador["n"] >= 3, "total_repartos": 3, "actividades_divididas": 0}

        r = buscar_opciones_viables("García, Ana", self.act, [6.0, 5.5, 5.0, 4.5],
                                    [], [], self.profs, self.acts, tercera_viable)
        assert r is not None
        assert r["horas"] == 5.0
        assert contador["n"] == 3


class TestConfirmarBloqueConSolver:
    def test_bloque_viable(self):
        bloque = [_e("García, Ana", "PROG", "GD", "A", 6.0)]
        r = confirmar_bloque_con_solver(bloque, [_p("García, Ana", 6.0)],
                                        [_a("PROG", "GD", "A", 6.0)], solver_viable)
        assert r["viable"] is True

    def test_bloque_inviable(self):
        bloque = [_e("García, Ana", "PROG", "GD", "A", 6.0)]
        r = confirmar_bloque_con_solver(bloque, [_p("García, Ana", 6.0)],
                                        [_a("PROG", "GD", "A", 6.0)], solver_inviable)
        assert r["viable"] is False
