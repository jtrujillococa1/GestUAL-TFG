from solver.cache import SolverCache


def _profesores():
    return [{
        "id": 1,
        "nombre": "Ana",
        "apellidos": "Uno",
        "horas_objetivo": 3,
        "area_id": 10,
    }]


def _actividades():
    return [{
        "id": 1,
        "codigo": "A1",
        "codigo_grupo": "G1",
        "tipo": "GD",
        "horas_totales": 3,
        "area_id": 10,
    }]


def _eleccion(horas):
    return [{
        "profesor": "Uno, Ana",
        "actividad_id": 1,
        "codigo": "A1",
        "codigo_grupo": "G1",
        "tipo": "GD",
        "horas": horas,
    }]


def test_cache_devuelve_el_mismo_resultado_marcado_como_reutilizado():
    cache = SolverCache(max_size=2, max_bytes=10_000)
    profesores = _profesores()
    actividades = _actividades()
    resultado = {"viable": True, "reparto": [{"profesor": "Ana"}]}

    cache.set(_eleccion(1), profesores, actividades, resultado)
    reutilizado = cache.get(_eleccion(1), profesores, actividades)

    assert reutilizado == {**resultado, "cached": True}
    assert cache.get_stats()["hits"] == 1


def test_cache_lru_conserva_el_estado_consultado_mas_recientemente():
    cache = SolverCache(max_size=2, max_bytes=10_000)
    profesores = _profesores()
    actividades = _actividades()
    resultado = {"viable": True}

    cache.set(_eleccion(0.5), profesores, actividades, resultado)
    cache.set(_eleccion(1), profesores, actividades, resultado)
    assert cache.get(_eleccion(0.5), profesores, actividades) is not None
    cache.set(_eleccion(1.5), profesores, actividades, resultado)

    assert cache.get(_eleccion(1), profesores, actividades) is None
    assert cache.get(_eleccion(0.5), profesores, actividades) is not None


def test_cache_no_retiene_un_resultado_mayor_que_su_presupuesto_de_memoria():
    cache = SolverCache(max_size=3, max_bytes=180)
    profesores = _profesores()
    actividades = _actividades()
    resultado_grande = {"viable": True, "reparto": [{"detalle": "x" * 1_000}]}

    cache.set(_eleccion(1), profesores, actividades, resultado_grande)

    assert cache.get(_eleccion(1), profesores, actividades) is None
    assert cache.get_stats()["size"] == 0
