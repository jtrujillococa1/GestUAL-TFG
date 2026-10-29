"""
Tests de integración - Escenarios realistas sin BD ni OR-Tools.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from domain.ordenacion.turnos import (
    calcular_nombre_completo, calcular_horas_por_profesor,
    clasificar_profesores, obtener_profesor_actual, validar_turno_completo,
)
from domain.ordenacion.viabilidad import (
    calcular_horas_restantes_actividad, calcular_horas_restantes_profesor,
    actividad_en_borrador, generar_candidatos_horas,
    categorizar_opcion, priorizar_opciones,
)
from domain.ordenacion.conflictos import calcular_equilibrio_horas, calcular_riesgo_global
from domain.ordenacion.scheduler import (
    validar_opcion_con_solver, buscar_opciones_viables, confirmar_bloque_con_solver,
)


# ─── Helpers ──────────────────────────────────────────────────

def _p_bd(id_, nombre, apellidos, horas):
    return {"id": id_, "nombre": nombre, "apellidos": apellidos,
            "categoria": "Titular", "carga_docente": horas, "area_id": 1, "es_psi": False}

def _p_solver(nc, horas):
    partes = nc.split(", ", 1)
    return {"id": 1, "nombre": nc, "apellidos": partes[0],
            "horas_objetivo": horas, "carga_docente": horas}

def _p_turno(nombre_simple, apellidos, horas):
    return {"nombre": nombre_simple, "apellidos": apellidos, "horas_objetivo": horas}

def _act(codigo, tipo, grupo, horas):
    return {"id": 1, "codigo": codigo, "tipo": tipo, "tipo_actividad": tipo,
            "codigo_grupo": grupo, "grupo": f"Grupo {grupo}", "turno": "M", "duracion": "C1",
            "horas_actividad": horas, "horas_totales": horas, "area_id": 1}

def _e(profesor, codigo, tipo, grupo, horas):
    return {"profesor": profesor, "codigo": codigo, "tipo": tipo, "tipo_actividad": tipo,
            "codigo_grupo": grupo, "grupo": f"Grupo {grupo}", "horas": horas}

def solver_viable(e, p, a, usar_cache=True):
    return {"viable": True, "total_repartos": len(e), "actividades_divididas": 0, "cached": False}

def solver_inviable(e, p, a, usar_cache=True):
    return {"viable": False, "total_repartos": 0, "actividades_divididas": 0, "cached": False}

def solver_logico(elecciones, profesores, actividades, usar_cache=True):
    """Mock con lógica real: verifica horas de actividades y profesores."""
    horas_act = {}
    for e in elecciones:
        k = (e["codigo"], e["codigo_grupo"], e.get("tipo") or e.get("tipo_actividad"))
        horas_act[k] = horas_act.get(k, 0.0) + float(e["horas"])
    for a in actividades:
        if horas_act.get((a["codigo"], a["codigo_grupo"], a["tipo"]), 0.0) > float(a["horas_totales"]) + 0.01:
            return {"viable": False, "total_repartos": 0, "actividades_divididas": 0, "cached": False}
    horas_prof = {}
    for e in elecciones:
        horas_prof[e["profesor"]] = horas_prof.get(e["profesor"], 0.0) + float(e["horas"])
    for p in profesores:
        if horas_prof.get(p["nombre"], 0.0) > float(p["horas_objetivo"]) + 0.01:
            return {"viable": False, "total_repartos": 0, "actividades_divididas": 0, "cached": False}
    return {"viable": True, "total_repartos": len(elecciones), "actividades_divididas": 0, "cached": False}


# ═══════════════════════════════════════════════════════════════
# ESCENARIO 1: 2 profesores, 2 actividades
# ═══════════════════════════════════════════════════════════════

class TestEscenario2Prof2Act:
    def setup_method(self):
        self.profs_bd     = [_p_bd(1,"Ana","García",12.0), _p_bd(2,"Pedro","López",12.0)]
        self.profs_solver = [_p_solver("García, Ana",12.0), _p_solver("López, Pedro",12.0)]
        self.profs_turno  = [_p_turno("Ana","García",12.0), _p_turno("Pedro","López",12.0)]
        self.acts         = [_act("PROG","GD","A",12.0), _act("BBDD","GD","A",12.0)]

    def test_sistema_equilibrado(self):
        r = calcular_equilibrio_horas(self.profs_solver, self.acts)
        assert r["equilibrado"] is True

    def test_orden_inicial_correcto(self):
        _, pendientes = clasificar_profesores(self.profs_bd, {})
        assert obtener_profesor_actual(pendientes) == "García, Ana"

    def test_turno_ana_completo(self):
        borrador = [_e("García, Ana", "PROG", "GD", "A", 12.0)]
        ok, _, _ = validar_turno_completo("García, Ana", self.profs_turno, borrador)
        assert ok is True

    def test_turno_pedro_completo(self):
        conf  = [_e("García, Ana",  "PROG", "GD", "A", 12.0)]
        borr  = [_e("López, Pedro", "BBDD", "GD", "A", 12.0)]
        ok, _, _ = validar_turno_completo("López, Pedro", self.profs_turno, conf + borr)
        assert ok is True

    def test_solver_valida_asignacion(self):
        op = _e("García, Ana", "PROG", "GD", "A", 12.0)
        r = validar_opcion_con_solver(op, [], [], self.profs_solver, self.acts, solver_logico)
        assert r["viable"] is True


    def test_solver_rechaza_exceso(self):
        op = _e("García, Ana", "PROG", "GD", "A", 15.0)  # PROG solo tiene 12h
        r = validar_opcion_con_solver(op, [], [], self.profs_solver, self.acts, solver_logico)
        assert r["viable"] is False

    def test_flujo_completo_dos_turnos(self):
        confirmadas = []

        borr_ana = [_e("García, Ana", "PROG", "GD", "A", 12.0)]
        ok_ana, _, _ = validar_turno_completo("García, Ana", self.profs_turno, borr_ana)
        assert ok_ana is True
        r = confirmar_bloque_con_solver(borr_ana, self.profs_solver, self.acts, solver_viable)
        assert r["viable"] is True
        confirmadas.extend(borr_ana)

        borr_pedro = [_e("López, Pedro", "BBDD", "GD", "A", 12.0)]
        ok_pedro, _, _ = validar_turno_completo("López, Pedro", self.profs_turno, confirmadas + borr_pedro)
        assert ok_pedro is True
        r = confirmar_bloque_con_solver(confirmadas + borr_pedro, self.profs_solver, self.acts, solver_viable)
        assert r["viable"] is True
        confirmadas.extend(borr_pedro)

        horas = calcular_horas_por_profesor(self.profs_bd, confirmadas)
        completados, pendientes = clasificar_profesores(self.profs_bd, horas)
        assert len(completados) == 2
        assert len(pendientes) == 0


# ═══════════════════════════════════════════════════════════════
# ESCENARIO 2: Actividad dividida entre 3 profesores
# ═══════════════════════════════════════════════════════════════

class TestActividadDividida:
    def setup_method(self):
        self.profs  = [_p_solver("García, Ana",6.0), _p_solver("López, Pedro",6.0),
                       _p_solver("Martínez, Carmen",6.0)]
        self.act    = _act("PROG", "GD", "A", 18.0)
        self.acts   = [self.act]

    def test_equilibrio(self):
        assert calcular_equilibrio_horas(self.profs, self.acts)["equilibrado"] is True

    def test_horas_decrecen_con_cada_asignacion(self):
        elecciones = []
        assert calcular_horas_restantes_actividad(self.act, elecciones) == 18.0
        elecciones.append(_e("García, Ana", "PROG", "GD", "A", 6.0))
        assert calcular_horas_restantes_actividad(self.act, elecciones) == 12.0
        elecciones.append(_e("López, Pedro", "PROG", "GD", "A", 6.0))
        assert calcular_horas_restantes_actividad(self.act, elecciones) == 6.0
        elecciones.append(_e("Martínez, Carmen", "PROG", "GD", "A", 6.0))
        assert calcular_horas_restantes_actividad(self.act, elecciones) == 0.0

    def test_candidatos_limitados_por_disponibilidad(self):
        previas = [_e("García, Ana","PROG","GD","A",6.0), _e("López, Pedro","PROG","GD","A",6.0)]
        disp = calcular_horas_restantes_actividad(self.act, previas)
        candidatos = generar_candidatos_horas(disp, 6.0)
        assert candidatos[0] == 6.0


# ═══════════════════════════════════════════════════════════════
# ESCENARIO 3: Horas fraccionadas
# ═══════════════════════════════════════════════════════════════

class TestHorasFraccionadas:
    def setup_method(self):
        self.prof  = [_p_solver("García, Ana", 3.5)]
        self.pturno= [_p_turno("Ana","García", 3.5)]
        self.act   = _act("PROG", "GD", "A", 3.5)

    def test_candidatos_incluyen_fraccion(self):
        candidatos = generar_candidatos_horas(3.5, 3.5)
        assert 3.5 in candidatos
        assert 0.1 in candidatos

    def test_turno_completo_con_fraccion(self):
        borrador = [_e("García, Ana", "PROG", "GD", "A", 3.5)]
        ok, rest, _ = validar_turno_completo("García, Ana", self.pturno, borrador)
        assert ok is True

    def test_solver_acepta_fraccion(self):
        op = _e("García, Ana", "PROG", "GD", "A", 3.5)
        r = validar_opcion_con_solver(op, [], [], self.prof, [self.act], solver_viable)
        assert r["viable"] is True


# ═══════════════════════════════════════════════════════════════
# ESCENARIO 4: Riesgo y categorización
# ═══════════════════════════════════════════════════════════════

class TestRiesgoYCategorizacion:
    def test_sistema_completamente_asignado_riesgo_cero(self):
        profs = [_p_solver("García, Ana", 12.0)]
        acts  = [_act("PROG", "GD", "A", 12.0)]
        conf  = [_e("García, Ana", "PROG", "GD", "A", 12.0)]
        r = calcular_riesgo_global(profs, acts, conf)
        assert r["riesgo"] == 0
        assert r["nivel"] == "BAJO"

    def test_opciones_ordenadas_correctamente(self):
        def _op(cat, rep, div, h):
            return {"categoria": cat, "total_repartos": rep, "actividades_divididas": div,
                    "opcion": {"horas": h, "codigo": "X", "tipo": "GD", "codigo_grupo": "A", "profesor": "P"}}
        opciones = [_op("VIABLE",3,0,4.0), _op("COMPLETA_TURNO",3,0,6.0), _op("CASI_COMPLETA",3,0,5.0)]
        ordenadas = priorizar_opciones(opciones)
        assert ordenadas[0]["categoria"] == "COMPLETA_TURNO"
        assert ordenadas[1]["categoria"] == "CASI_COMPLETA"
        assert ordenadas[2]["categoria"] == "VIABLE"

    def test_categorizacion_correcta(self):
        assert categorizar_opcion(0.0)   == "COMPLETA_TURNO"
        assert categorizar_opcion(0.009) == "COMPLETA_TURNO"
        assert categorizar_opcion(0.5)   == "CASI_COMPLETA"
        assert categorizar_opcion(1.0)   == "CASI_COMPLETA"
        assert categorizar_opcion(1.5)   == "VIABLE"
        assert categorizar_opcion(20.0)  == "VIABLE"


# ═══════════════════════════════════════════════════════════════
# ESCENARIO 5: Borrador
# ═══════════════════════════════════════════════════════════════

class TestBorrador:
    def test_actividad_detectada_en_borrador(self):
        act  = _act("PROG", "GD", "A", 6.0)
        borr = [_e("García, Ana", "PROG", "GD", "A", 6.0)]
        assert actividad_en_borrador(act, borr) is True

    def test_actividad_diferente_no_detectada(self):
        act  = _act("BBDD", "GD", "A", 6.0)
        borr = [_e("García, Ana", "PROG", "GD", "A", 6.0)]
        assert actividad_en_borrador(act, borr) is False

    def test_horas_borrador_cuentan_para_actividad(self):
        act  = _act("PROG", "GD", "A", 12.0)
        borr = [_e("García, Ana", "PROG", "GD", "A", 6.0)]
        assert calcular_horas_restantes_actividad(act, borr) == 6.0

    def test_confirmadas_mas_borrador_acumulan(self):
        act   = _act("PROG", "GD", "A", 12.0)
        conf  = [_e("García, Ana", "PROG", "GD", "A", 4.0)]
        borr  = [_e("García, Ana", "PROG", "GD", "A", 4.0)]
        assert calcular_horas_restantes_actividad(act, conf + borr) == 4.0


# ═══════════════════════════════════════════════════════════════
# ESCENARIO 6: Casos borde
# ═══════════════════════════════════════════════════════════════

class TestCasosBorde:
    def test_sistema_sin_profesores_ni_actividades(self):
        r = calcular_equilibrio_horas([], [])
        assert r["equilibrado"] is True

    def test_sistema_sin_actividades_desequilibrado(self):
        r = calcular_equilibrio_horas([_p_solver("X", 12.0)], [])
        assert r["equilibrado"] is False

    def test_carga_cero_sin_candidatos(self):
        assert generar_candidatos_horas(6.0, 0.0) == []

    def test_actividad_cubierta_sin_candidatos(self):
        act  = _act("PROG", "GD", "A", 6.0)
        conf = [_e("García, Ana", "PROG", "GD", "A", 6.0)]
        disp = calcular_horas_restantes_actividad(act, conf)
        assert generar_candidatos_horas(disp, 12.0) == []

    def test_riesgo_nunca_supera_100(self):
        profs = [_p_solver(f"P{i}", 24.0) for i in range(10)]
        r = calcular_riesgo_global(profs, [], [])
        assert r["riesgo"] <= 100

    def test_nombre_completo_formato_correcto(self):
        nc = calcular_nombre_completo("Ana María", "García López")
        assert nc == "García López, Ana María"
        assert len(nc.split(", ")) == 2
