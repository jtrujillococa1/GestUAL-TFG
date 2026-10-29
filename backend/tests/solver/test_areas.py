from solver.engine import resolver_reparto, resolver_reparto_en_area


def test_solver_no_cubre_actividades_de_otra_area():
    profesores = [{
        "id": 1, "nombre": "Ana", "apellidos": "Uno", "horas_objetivo": 1,
        "area_id": 10,
    }]
    actividades = [{
        "id": 1, "codigo": "A", "codigo_grupo": "G", "tipo": "GD", "grupo": "G",
        "horas_totales": 1, "area_id": 20, "duracion": "1Q", "turno": "Mañana",
        "dias": "Lunes", "horario": "09:00-10:30",
    }]
    resultado = resolver_reparto([], profesores, actividades, usar_cache=False)
    assert resultado["viable"] is False
    assert resultado["diagnostico"]


def test_solver_descompone_areas_y_conserva_el_reparto_de_cada_una():
    profesores = [
        {"id": 1, "nombre": "Ana", "apellidos": "Uno", "horas_objetivo": 1, "area_id": 10},
        {"id": 2, "nombre": "Beto", "apellidos": "Dos", "horas_objetivo": 1, "area_id": 20},
    ]
    actividades = [
        {"id": 1, "codigo": "A", "codigo_grupo": "G1", "tipo": "GD", "grupo": "G1", "horas_totales": 1, "area_id": 10},
        {"id": 2, "codigo": "B", "codigo_grupo": "G2", "tipo": "GD", "grupo": "G2", "horas_totales": 1, "area_id": 20},
    ]
    resultado = resolver_reparto([], profesores, actividades, usar_cache=False)
    assert resultado["viable"] is True
    assert resultado["total_repartos"] == 2
    assert [fila["profesor"] for fila in resultado["reparto"]] == ["Ana", "Beto"]


def test_transporte_respeta_una_eleccion_forzada_y_cubre_el_resto():
    profesores = [
        {"id": 1, "nombre": "Ana", "apellidos": "Uno", "horas_objetivo": 2, "area_id": 10},
        {"id": 2, "nombre": "Beto", "apellidos": "Dos", "horas_objetivo": 2, "area_id": 10},
    ]
    actividades = [
        {"id": 1, "codigo": "A", "codigo_grupo": "G1", "tipo": "GD", "grupo": "G1", "horas_totales": 2, "area_id": 10},
        {"id": 2, "codigo": "B", "codigo_grupo": "G2", "tipo": "GD", "grupo": "G2", "horas_totales": 2, "area_id": 10},
    ]
    resultado = resolver_reparto([
        {"profesor": "Uno, Ana", "actividad_id": 1, "codigo": "A", "codigo_grupo": "G1", "tipo": "GD", "horas": 1},
    ], profesores, actividades, usar_cache=False)
    assert resultado["viable"] is True
    assert resultado["reparto"][0]["actividades"][0]["horas"] == 1


def test_opcion_de_area_independiente_no_recalcula_un_area_ajena():
    profesores = [
        {
            "id": 1, "nombre": "Ana", "apellidos": "Uno", "horas_objetivo": 1,
            "area_id": 10, "area_ids": [10], "horas_objetivo_por_area": {10: 1},
        },
        # Este perfil comparte otras dos áreas, pero ninguna es el área 10.
        # No debe impedir consultar una opción de Ana en una cola independiente.
        {
            "id": 2, "nombre": "Beto", "apellidos": "Dos", "horas_objetivo": 2,
            "area_id": 20, "area_ids": [20, 30], "horas_objetivo_por_area": {20: 1, 30: 1},
        },
    ]
    actividades = [
        {"id": 1, "codigo": "A", "codigo_grupo": "G1", "tipo": "GD", "grupo": "G1", "horas_totales": 1, "area_id": 10},
        {"id": 2, "codigo": "B", "codigo_grupo": "G2", "tipo": "GD", "grupo": "G2", "horas_totales": 1, "area_id": 20},
    ]
    resultado = resolver_reparto_en_area(
        [{"profesor": "Uno, Ana", "actividad_id": 1, "codigo": "A", "codigo_grupo": "G1", "tipo": "GD", "horas": 1}],
        profesores, actividades, 10, usar_cache=False,
    )
    assert resultado["viable"] is True
