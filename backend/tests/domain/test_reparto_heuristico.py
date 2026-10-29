from domain.ordenacion.reparto_heuristico import construir_reparto_heuristico


def _profesor(identificador, horas):
    return {
        "id": identificador, "nombre": f"P{identificador}", "apellidos": "Prueba",
        "horas_objetivo": horas, "area_id": 1, "area_ids": [1],
        "disponibilidad_cuatrimestre": "AMBOS",
    }


def _actividad(identificador, horas):
    return {
        "id": identificador, "codigo": f"A{identificador}", "codigo_grupo": "G1",
        "tipo": "GD", "grupo": "Grupo 1", "area_id": 1,
        "horas_totales": horas, "duracion": "Anual",
    }


def test_heuristica_cubre_cargas_y_evitar_solapes():
    resultado = construir_reparto_heuristico(
        [], [_profesor(1, 3), _profesor(2, 3)],
        [_actividad(1, 3), _actividad(2, 3)], [(1, 2)],
    )

    assert resultado["viable"] is True
    assert [fila["horas_totales"] for fila in resultado["reparto"]] == [3.0, 3.0]
    actividades = [
        {actividad["actividad_id"] for actividad in fila["actividades"]}
        for fila in resultado["reparto"]
    ]
    assert all(not ({1, 2} <= asignadas) for asignadas in actividades)
