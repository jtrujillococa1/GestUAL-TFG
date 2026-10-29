"""Cobertura de las restricciones docentes por cuatrimestre."""

from domain.ordenacion.conflictos import calcular_riesgo_estado, preparar_contexto_riesgo
from domain.ordenacion.disponibilidad import cuatrimestres_actividad
from domain.ordenacion.scheduler import buscar_opciones_viables
from solver.engine import resolver_reparto


def _profesor(profesor_id, nombre, disponibilidad):
    return {
        "id": profesor_id,
        "nombre": nombre,
        "apellidos": "Prueba",
        "horas_objetivo": 3,
        "carga_docente": 3,
        "area_id": 10,
        "area_ids": [10],
        "horas_objetivo_por_area": {10: 3},
        "disponibilidad_cuatrimestre": disponibilidad,
    }


def _actividad(actividad_id, codigo, duracion, fecha=None):
    actividad = {
        "id": actividad_id,
        "codigo": codigo,
        "codigo_grupo": "A",
        "tipo": "GD",
        "grupo": "A",
        "horas_totales": 3,
        "area_id": 10,
        "duracion": duracion,
        "turno": "Mañana",
        "dias": "Lunes",
        "horario": "Lunes 09:00-10:30",
    }
    if fecha:
        actividad["horario_detallado"] = [{"fecha": fecha, "inicio": "09:00", "fin": "10:30"}]
    return actividad


def test_las_sesiones_oficiales_tienen_prioridad_sobre_la_duracion():
    actividad = _actividad(1, "BD", "A", "2026-10-05")
    assert cuatrimestres_actividad(actividad) == {"C1"}


def test_solver_rechaza_eleccion_en_cuatrimestre_no_disponible():
    primero = _profesor(1, "Ana", "PRIMERO")
    ambos = _profesor(2, "Beto", "AMBOS")
    c1 = _actividad(1, "C1", "1Q")
    c2 = _actividad(2, "C2", "2Q")

    resultado = resolver_reparto(
        [{
            "profesor": "Prueba, Ana", "actividad_id": c2["id"],
            "codigo": c2["codigo"], "codigo_grupo": c2["codigo_grupo"],
            "tipo": c2["tipo"], "horas": 3,
        }],
        [primero, ambos], [c1, c2], usar_cache=False,
    )

    assert resultado["viable"] is False
    assert any("Disponibilidad restringida" in motivo for motivo in resultado["diagnostico"])


def test_opcion_restringida_permanece_visible_y_marca_motivo():
    profesor = _profesor(1, "Ana", "PRIMERO")
    actividad = _actividad(1, "C2", "2Q")

    resultado = buscar_opciones_viables(
        "Prueba, Ana", actividad, [3], [], [], [profesor], [actividad], resolver_reparto,
    )

    assert resultado is not None
    assert resultado["viable"] is False
    assert "Disponibilidad restringida" in resultado["motivo_no_viable"]
    assert resultado["resultado_solver"]["motivo_restriccion"]


def test_riesgo_refleja_cobertura_limitada_por_cuatrimestre():
    primero = _profesor(1, "Ana", "PRIMERO")
    segundo = _profesor(2, "Beto", "SEGUNDO")
    actividad = _actividad(1, "C1", "1Q")

    riesgo = calcular_riesgo_estado(
        [], preparar_contexto_riesgo([primero, segundo], [actividad], 10),
    )

    assert riesgo["desglose"]["cuatrimestre"] > 0
    assert any("cuatrimestre" in motivo.lower() for motivo in riesgo["motivos"])


def test_riesgo_inicial_reserva_carga_aun_con_varias_alternativas():
    profesores = [
        _profesor(1, "Ana", "AMBOS"),
        _profesor(2, "Beto", "AMBOS"),
        _profesor(3, "Celia", "AMBOS"),
        _profesor(4, "Dani", "SEGUNDO"),
    ]
    actividad = _actividad(1, "C2", "2Q")
    actividad["horas_totales"] = 12

    riesgo = calcular_riesgo_estado(
        [], preparar_contexto_riesgo(profesores, [actividad], 10),
    )

    assert riesgo["desglose"]["cuatrimestre"] > 0
    assert any("Reserva de" in motivo for motivo in riesgo["motivos"])


def test_riesgo_es_critico_si_la_reserva_supera_la_docencia_del_periodo():
    profesores = [
        _profesor(1, "Ana", "SEGUNDO"),
        _profesor(2, "Beto", "SEGUNDO"),
    ]
    actividad = _actividad(1, "C2", "2Q")
    actividad["horas_totales"] = 3

    riesgo = calcular_riesgo_estado(
        [], preparar_contexto_riesgo(profesores, [actividad], 10),
    )

    assert riesgo["riesgo"] == 100
    assert riesgo["nivel"] == "CRITICO"
    assert any("Inviable desde el inicio" in motivo for motivo in riesgo["motivos"])


def test_solver_descarta_pronto_una_reserva_temporal_imposible():
    profesores = [
        _profesor(1, "Ana", "SEGUNDO"),
        _profesor(2, "Beto", "SEGUNDO"),
    ]
    actividad = _actividad(1, "C2", "2Q")
    actividad["horas_totales"] = 3

    resultado = resolver_reparto([], profesores, [actividad], usar_cache=False)

    assert resultado["viable"] is False
    assert "carga reservada" in resultado["diagnostico"][0].lower()


def test_eleccion_temprana_no_puede_consumir_la_reserva_de_los_ultimos_turnos():
    profesores = [
        _profesor(1, "Flex 1", "AMBOS"),
        _profesor(2, "Flex 2", "AMBOS"),
        _profesor(3, "Flex 3", "AMBOS"),
        _profesor(4, "C2 1", "SEGUNDO"),
        _profesor(5, "C2 2", "SEGUNDO"),
        _profesor(6, "C2 3", "SEGUNDO"),
    ]
    c1 = _actividad(1, "C1", "1Q")
    c2 = _actividad(2, "C2", "2Q")
    for actividad in (c1, c2):
        actividad["horas_totales"] = 9
        actividad["dias"] = None
        actividad["horario"] = None

    riesgo_inicial = calcular_riesgo_estado(
        [], preparar_contexto_riesgo(profesores, [c1, c2], 10),
    )
    solucion_inicial = resolver_reparto([], profesores, [c1, c2], usar_cache=False)
    eleccion_temprana = {
        "profesor": "Prueba, Flex 1", "actividad_id": c2["id"],
        "codigo": c2["codigo"], "codigo_grupo": c2["codigo_grupo"],
        "tipo": c2["tipo"], "horas": 3,
    }
    solucion_tras_elegir_c2 = resolver_reparto(
        [eleccion_temprana], profesores, [c1, c2], usar_cache=False,
    )

    assert solucion_inicial["viable"] is True
    assert riesgo_inicial["riesgo"] > 20
    assert solucion_tras_elegir_c2["viable"] is False
    assert "carga reservada" in solucion_tras_elegir_c2["diagnostico"][0].lower()
