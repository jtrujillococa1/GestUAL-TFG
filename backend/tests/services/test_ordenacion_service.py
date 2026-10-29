"""
Tests - Flujo completo del servicio de ordenación con mocks.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))


# ─── Helpers ──────────────────────────────────────────────────

def _p_bd(id_, nombre, apellidos, horas):
    return {"id": id_, "nombre": nombre, "apellidos": apellidos,
            "categoria": "Titular", "carga_docente": horas, "area_id": 1, "es_psi": False}

def _p_solver(nombre_completo, horas):
    """Formato solver: nombre completo en 'nombre' para calcular_horas_restantes_profesor."""
    return {"id": 1, "nombre": nombre_completo, "horas_objetivo": horas, "carga_docente": horas}

def _p_bd_compat(nombre_simple, apellidos, horas):
    """Formato BD compatible con validar_turno_completo."""
    return {"nombre": nombre_simple, "apellidos": apellidos, "horas_objetivo": horas}

def _act(codigo, tipo, grupo, horas):
    return {"id": 1, "codigo": codigo, "tipo": tipo, "tipo_actividad": tipo,
            "codigo_grupo": grupo, "grupo": f"Grupo {grupo}", "turno": "M", "duracion": "C1",
            "horas_actividad": horas, "horas_totales": horas, "area_id": 1}

def _eleccion(profesor, codigo, tipo, grupo, horas):
    return {"profesor": profesor, "codigo": codigo, "tipo": tipo, "tipo_actividad": tipo,
            "codigo_grupo": grupo, "grupo": f"Grupo {grupo}", "horas": horas}

def solver_viable(e, p, a, usar_cache=True):
    return {"viable": True, "total_repartos": 3, "actividades_divididas": 0, "cached": False}

def solver_inviable(e, p, a, usar_cache=True):
    return {"viable": False, "total_repartos": 0, "actividades_divididas": 0, "cached": False}

def solver_con_logica(elecciones, profesores, actividades, usar_cache=True):
    """Mock con lógica básica: verifica que no se excedan las horas de actividades ni profesores."""
    horas_act = {}
    for e in elecciones:
        k = (e["codigo"], e["codigo_grupo"], e.get("tipo") or e.get("tipo_actividad"))
        horas_act[k] = horas_act.get(k, 0.0) + float(e["horas"])
    for a in actividades:
        k = (a["codigo"], a["codigo_grupo"], a["tipo"])
        if horas_act.get(k, 0.0) > float(a["horas_totales"]) + 0.01:
            return {"viable": False, "total_repartos": 0, "actividades_divididas": 0}
    horas_prof = {}
    for e in elecciones:
        horas_prof[e["profesor"]] = horas_prof.get(e["profesor"], 0.0) + float(e["horas"])
    for p in profesores:
        if horas_prof.get(p["nombre"], 0.0) > float(p["horas_objetivo"]) + 0.01:
            return {"viable": False, "total_repartos": 0, "actividades_divididas": 0}
    return {"viable": True, "total_repartos": len(elecciones), "actividades_divididas": 0, "cached": False}


# ═══════════════════════════════════════════════════════════════
# TESTS - Estado de ordenación (solo domain, sin BD)
# ═══════════════════════════════════════════════════════════════

class TestEstadoOrdenacion:
    def setup_method(self):
        self.profs_bd = [
            _p_bd(1, "Ana", "García", 12.0),
            _p_bd(2, "Pedro", "López", 12.0),
        ]

    def test_estado_inicial_sin_confirmaciones(self):
        from domain.ordenacion.turnos import (
            calcular_horas_por_profesor, clasificar_profesores, obtener_profesor_actual
        )
        horas = calcular_horas_por_profesor(self.profs_bd, [])
        completados, pendientes = clasificar_profesores(self.profs_bd, horas)
        actual = obtener_profesor_actual(pendientes)

        assert actual == "García, Ana"
        assert len(pendientes) == 2
        assert len(completados) == 0

    def test_estado_con_ana_completada(self):
        from domain.ordenacion.turnos import (
            calcular_horas_por_profesor, clasificar_profesores, obtener_profesor_actual
        )
        confirmadas = [_eleccion("García, Ana", "PROG", "GD", "A", 12.0)]
        horas = calcular_horas_por_profesor(self.profs_bd, confirmadas)
        completados, pendientes = clasificar_profesores(self.profs_bd, horas)
        actual = obtener_profesor_actual(pendientes)

        assert actual == "López, Pedro"
        assert len(completados) == 1

    def test_ordenacion_terminada_cuando_todos_completados(self):
        from domain.ordenacion.turnos import (
            calcular_horas_por_profesor, clasificar_profesores, obtener_profesor_actual
        )
        confirmadas = [
            _eleccion("García, Ana",  "PROG", "GD", "A", 12.0),
            _eleccion("López, Pedro", "PROG", "GD", "A", 12.0),
        ]
        horas = calcular_horas_por_profesor(self.profs_bd, confirmadas)
        completados, pendientes = clasificar_profesores(self.profs_bd, horas)
        assert obtener_profesor_actual(pendientes) is None
        assert len(completados) == 2


# ═══════════════════════════════════════════════════════════════
# TESTS - Viabilidad con solver mockeado
# ═══════════════════════════════════════════════════════════════

class TestViabilidadConSolver:
    def setup_method(self):
        self.profs = [_p_solver("García, Ana", 24.0)]
        self.acts  = [_act("PROG","GD","A",6.0), _act("BBDD","GD","A",6.0),
                      _act("REDES","GD","A",6.0), _act("SO","GD","A",6.0)]

    def test_solver_viable_genera_candidatos(self):
        from domain.ordenacion.viabilidad import (
            calcular_horas_restantes_actividad, calcular_horas_restantes_profesor,
            generar_candidatos_horas
        )
        for act in self.acts:
            disp = calcular_horas_restantes_actividad(act, [])
            rest = calcular_horas_restantes_profesor("García, Ana", self.profs, [])
            candidatos = generar_candidatos_horas(disp, rest)
            assert len(candidatos) > 0

    def test_opcion_viable_aceptada(self):
        from domain.ordenacion.scheduler import validar_opcion_con_solver
        opcion = _eleccion("García, Ana", "PROG", "GD", "A", 6.0)
        r = validar_opcion_con_solver(opcion, [], [], self.profs, self.acts, solver_viable)
        assert r["viable"] is True

    def test_opcion_inviable_rechazada(self):
        from domain.ordenacion.scheduler import validar_opcion_con_solver
        opcion = _eleccion("García, Ana", "PROG", "GD", "A", 6.0)
        r = validar_opcion_con_solver(opcion, [], [], self.profs, self.acts, solver_inviable)
        assert r["viable"] is False

    def test_solver_rechaza_exceso_actividad(self):
        from domain.ordenacion.scheduler import validar_opcion_con_solver
        opcion = _eleccion("García, Ana", "PROG", "GD", "A", 8.0)  # PROG solo tiene 6h
        r = validar_opcion_con_solver(opcion, [], [], self.profs, self.acts, solver_con_logica)
        assert r["viable"] is False

    def test_prioriza_horas_maximas(self):
        from domain.ordenacion.scheduler import buscar_opciones_viables
        act = _act("PROG", "GD", "A", 6.0)
        r = buscar_opciones_viables("García, Ana", act, [6.0, 5.5, 5.0, 4.5],
                                    [], [], self.profs, self.acts, solver_viable)
        assert r is not None
        assert r["horas"] == 6.0

    def test_solver_inviable_permanece_visible_como_no_viable(self):
        from domain.ordenacion.scheduler import buscar_opciones_viables
        act = _act("PROG", "GD", "A", 6.0)
        r = buscar_opciones_viables("García, Ana", act,
                                    [6.0, 5.9, 5.8, 5.7, 5.6, 5.5, 5.4, 5.3, 5.2, 5.1, 5.0, 4.9, 4.8, 4.7, 4.6, 4.5, 4.4, 4.3, 4.2, 4.1, 4.0, 3.9, 3.8, 3.7, 3.6, 3.5, 3.4, 3.3, 3.2, 3.1, 3.0, 2.9, 2.8, 2.7, 2.6, 2.5, 2.4, 2.3, 2.2, 2.1, 2.0, 1.9, 1.8, 1.7, 1.6, 1.5, 1.4, 1.3, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1],
                                    [], [], self.profs, self.acts, solver_inviable)
        assert r is not None
        assert r["viable"] is False


# ═══════════════════════════════════════════════════════════════
# TESTS - Flujo completo de turno
# ═══════════════════════════════════════════════════════════════

class TestFlujoCompletoTurno:
    def setup_method(self):
        self.profs_solver = [_p_solver("García, Ana", 12.0)]
        self.profs_bd     = [_p_bd_compat("Ana", "García", 12.0)]
        self.acts         = [_act("PROG","GD","A",6.0), _act("BBDD","GD","A",6.0)]

    def test_flujo_completo_anadir_dos_actividades(self):
        from domain.ordenacion.viabilidad import calcular_horas_restantes_profesor
        from domain.ordenacion.turnos import validar_turno_completo
        from domain.ordenacion.scheduler import validar_opcion_con_solver

        # Paso 1: 12h pendientes
        assert calcular_horas_restantes_profesor("García, Ana", self.profs_solver, []) == 12.0

        # Paso 2: Añadir PROG (6h)
        borrador = []
        op1 = _eleccion("García, Ana", "PROG", "GD", "A", 6.0)
        r = validar_opcion_con_solver(op1, [], borrador, self.profs_solver, self.acts, solver_viable)
        assert r["viable"] is True
        borrador.append(op1)

        # Paso 3: Añadir BBDD (6h)
        op2 = _eleccion("García, Ana", "BBDD", "GD", "A", 6.0)
        r = validar_opcion_con_solver(op2, [], borrador, self.profs_solver, self.acts, solver_viable)
        assert r["viable"] is True
        borrador.append(op2)

        # Paso 4: Turno completo
        ok, restantes, error = validar_turno_completo("García, Ana", self.profs_bd, borrador)
        assert ok is True
        assert abs(restantes) < 0.01
        assert error is None

    def test_turno_incompleto_no_puede_confirmarse(self):
        from domain.ordenacion.turnos import validar_turno_completo

        borrador = [_eleccion("García, Ana", "PROG", "GD", "A", 6.0)]
        ok, restantes, error = validar_turno_completo("García, Ana", self.profs_bd, borrador)

        assert ok is False
        assert restantes == 6.0
        assert "Faltan" in error

    def test_turno_excedido_no_valido(self):
        from domain.ordenacion.turnos import validar_turno_completo

        borrador = [_eleccion("García, Ana", "PROG", "GD", "A", 14.0)]
        ok, restantes, error = validar_turno_completo("García, Ana", self.profs_bd, borrador)

        assert ok is False
        assert restantes < 0
        assert "paso" in error

    def test_confirmacion_bloque_viable(self):
        from domain.ordenacion.scheduler import confirmar_bloque_con_solver

        bloque = [_eleccion("García, Ana", "PROG", "GD", "A", 6.0),
                  _eleccion("García, Ana", "BBDD", "GD", "A", 6.0)]
        r = confirmar_bloque_con_solver(bloque, self.profs_solver, self.acts, solver_viable)
        assert r["viable"] is True

    def test_confirmacion_bloque_inviable_rechazada(self):
        from domain.ordenacion.scheduler import confirmar_bloque_con_solver

        bloque = [_eleccion("García, Ana", "PROG", "GD", "A", 6.0)]
        r = confirmar_bloque_con_solver(bloque, self.profs_solver, self.acts, solver_inviable)
        assert r["viable"] is False


# ═══════════════════════════════════════════════════════════════
# TESTS - Excepciones
# ═══════════════════════════════════════════════════════════════

class TestExcepciones:
    def test_not_your_turn_es_permission_denied(self):
        from core.exceptions import NotYourTurn, PermissionDenied
        with pytest.raises(PermissionDenied):
            raise NotYourTurn("no es tu turno")

    def test_viability_lost_es_ordenacion_error(self):
        from core.exceptions import ViabilityLost, OrdenacionError
        with pytest.raises(OrdenacionError):
            raise ViabilityLost("inviable")

    def test_incomplete_turn_es_ordenacion_error(self):
        from core.exceptions import IncompleteTurn, OrdenacionError
        with pytest.raises(OrdenacionError):
            raise IncompleteTurn("incompleto")

    def test_excepciones_tienen_message(self):
        from core.exceptions import NotYourTurn
        exc = NotYourTurn("Mensaje de prueba")
        assert exc.message == "Mensaje de prueba"

    def test_excepciones_tienen_details_vacios_por_defecto(self):
        from core.exceptions import ViabilityLost
        exc = ViabilityLost("error")
        assert exc.details == {}

    def test_excepciones_aceptan_details(self):
        from core.exceptions import OrdenacionError
        exc = OrdenacionError("error", details={"campo": "valor"})
        assert exc.details["campo"] == "valor"
