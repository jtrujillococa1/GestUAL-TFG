from solver.compatibilidad import actividades_incompatibles


def _actividad(actividad_id, *, origen="MANUAL", confirmado=True):
    return {
        "id": actividad_id, "duracion": "A", "dias": "Lunes",
        "horario": "09:00-10:30", "origen_horario": origen,
        "horario_confirmado": confirmado,
    }


def test_horarios_sinteticos_no_bloquean_la_viabilidad_hasta_confirmarlos():
    assert not actividades_incompatibles(
        _actividad(1, origen="SINTETICO", confirmado=False),
        _actividad(2),
    )


def test_horarios_sinteticos_confirmados_si_detectan_solapes():
    assert actividades_incompatibles(
        _actividad(1, origen="SINTETICO", confirmado=True),
        _actividad(2),
    )


def test_borrador_si_detecta_solape_de_horario_sintetico_provisional():
    assert actividades_incompatibles(
        _actividad(1, origen="SINTETICO", confirmado=False),
        _actividad(2),
        considerar_horarios_sinteticos=True,
    )


def test_actividad_sin_horario_fijo_no_bloquea_aunque_arrastre_una_franja_heredada():
    externa = _actividad(1, origen="SINTETICO", confirmado=False)
    externa["requiere_horario"] = False
    assert not actividades_incompatibles(
        externa,
        _actividad(2),
        considerar_horarios_sinteticos=True,
    )


def test_sesiones_oficiales_en_semanas_distintas_no_se_solapan():
    primera = {
        "id": 1, "duracion": "Primer cuatrimestre", "requiere_horario": True,
        "horario_detallado": [{"fecha": "2026-10-05", "dia": "Lunes", "inicio": "09:00", "fin": "11:00"}],
    }
    segunda = {
        "id": 2, "duracion": "Primer cuatrimestre", "requiere_horario": True,
        "horario_detallado": [{"fecha": "2026-10-12", "dia": "Lunes", "inicio": "09:30", "fin": "11:30"}],
    }
    assert not actividades_incompatibles(primera, segunda)


def test_sesiones_oficiales_en_la_misma_fecha_si_se_solapan():
    primera = {
        "id": 1, "duracion": "Primer cuatrimestre", "requiere_horario": True,
        "horario_detallado": [{"fecha": "2026-10-05", "dia": "Lunes", "inicio": "09:00", "fin": "11:00"}],
    }
    segunda = {
        "id": 2, "duracion": "Primer cuatrimestre", "requiere_horario": True,
        "horario_detallado": [{"fecha": "2026-10-05", "dia": "Lunes", "inicio": "10:30", "fin": "12:00"}],
    }
    assert actividades_incompatibles(primera, segunda)


def test_la_cuota_del_area_no_recorta_el_horario_reservado():
    primera = {
        "id": 1, "duracion": "Primer cuatrimestre", "requiere_horario": True,
        "horas_totales": 2,
        "horario_detallado": [
            {"fecha": "2026-10-05", "dia": "Lunes", "inicio": "09:00", "fin": "11:00"},
            {"fecha": "2026-10-12", "dia": "Lunes", "inicio": "09:00", "fin": "11:00"},
        ],
    }
    segunda = {
        "id": 2, "duracion": "Primer cuatrimestre", "requiere_horario": True,
        "horas_totales": 2,
        "horario_detallado": [
            {"fecha": "2026-10-12", "dia": "Lunes", "inicio": "10:00", "fin": "12:00"},
        ],
    }
    # El reparto de semanas se decide después: ambos reservan el grupo completo.
    assert actividades_incompatibles(primera, segunda)
