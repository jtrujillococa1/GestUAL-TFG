from datetime import date, timedelta

from domain.ordenacion.planificacion_semanal import (
    generar_sesiones_recurrentes,
    repartir_sesiones_consecutivas,
    replicar_horario_completo_actividad,
)


def test_no_planifica_festivos_y_reparte_por_bloques_consecutivos():
    sesiones = generar_sesiones_recurrentes(
        date(2025, 10, 6), date(2025, 10, 27),
        [{"dia": "Lunes", "inicio": "09:00", "fin": "10:30"}],
        {date(2025, 10, 13)},
    )
    # El lunes 13 es festivo: quedan 3 sesiones de 1,5 h.
    plan = repartir_sesiones_consecutivas(sesiones, [
        {"reparto_id": 10, "profesor_id": 1, "horas": 3},
        {"reparto_id": 11, "profesor_id": 2, "horas": 1.5},
    ])

    planificadas = [item for item in plan if item["estado"] == "PLANIFICADA"]
    assert [item["profesor_id"] for item in planificadas] == [1, 1, 2]
    assert [item["fecha"] for item in planificadas] == [date(2025, 10, 6), date(2025, 10, 20), date(2025, 10, 27)]


def test_parte_la_sesion_y_entrega_el_resto_al_siguiente_profesor():
    plan = repartir_sesiones_consecutivas(
        [{"fecha": date(2025, 10, 6), "inicio": "09:00", "fin": "10:30", "horas": 1.5}],
        [
            {"reparto_id": 10, "profesor_id": 1, "horas": 1},
            {"reparto_id": 11, "profesor_id": 2, "horas": 0.5},
        ],
    )

    assert [(item["profesor_id"], item["inicio"], item["fin"], item["horas"]) for item in plan] == [
        (1, "09:00", "10:00", 1.0),
        (2, "10:00", "10:30", 0.5),
    ]
    assert all(item["estado"] == "PLANIFICADA" for item in plan)


def test_reparto_compartido_de_30_y_25_horas_no_alterna_semanas():
    sesiones = [
        {"fecha": date(2025, 9, 8) + timedelta(days=indice), "inicio": "09:00", "fin": "10:00", "horas": 1}
        for indice in range(55)
    ]
    plan = repartir_sesiones_consecutivas(sesiones, [
        {"reparto_id": 1, "profesor_id": 10, "horas": 30},
        {"reparto_id": 2, "profesor_id": 20, "horas": 25},
    ])

    assert len(plan) == 55
    assert [item["profesor_id"] for item in plan[:30]] == [10] * 30
    assert [item["profesor_id"] for item in plan[30:]] == [20] * 25


def test_no_convierte_horas_docentes_en_mas_tiempo_presencial():
    plan = repartir_sesiones_consecutivas(
        [{
            "fecha": date(2025, 10, 6), "inicio": "09:00", "fin": "11:00",
            "horas": 2,
        }],
        [
            {"reparto_id": 10, "profesor_id": 1, "horas": 3},
        ],
    )

    assert [(item["profesor_id"], item["inicio"], item["fin"], item["horas"]) for item in plan] == [
        (1, "09:00", "11:00", 2.0),
        (1, None, None, 1.0),
    ]
    assert [item["estado"] for item in plan] == ["PLANIFICADA", "AJUSTE_PENDIENTE"]


def test_calendario_muestra_horario_completo_a_cada_docente_compartido():
    sesiones = generar_sesiones_recurrentes(
        date(2026, 9, 7), date(2026, 9, 28),
        [{"dia": "Lunes", "inicio": "09:00", "fin": "10:30"}],
        {date(2026, 9, 14)},
    )
    plan = replicar_horario_completo_actividad(sesiones, [
        {"reparto_id": 10, "profesor_id": 1, "horas": 20},
        {"reparto_id": 11, "profesor_id": 2, "horas": 21},
    ], horas_actividad=41)

    # Ambos ven las tres franjas oficiales no festivas. No se reparte ni se
    # parte una clase: las 20/21 h siguen siendo solo la cuota de ordenación.
    assert [(item["profesor_id"], item["fecha"], item["horas"]) for item in plan if item["estado"] == "PLANIFICADA"] == [
        (1, date(2026, 9, 7), 1.5),
        (1, date(2026, 9, 21), 1.5),
        (1, date(2026, 9, 28), 1.5),
        (2, date(2026, 9, 7), 1.5),
        (2, date(2026, 9, 21), 1.5),
        (2, date(2026, 9, 28), 1.5),
    ]
    assert {item["horas_adjudicadas"] for item in plan if item["profesor_id"] == 1} == {20.0}
    assert {item["horas_adjudicadas"] for item in plan if item["profesor_id"] == 2} == {21.0}
    assert all(item["es_horario_referencia"] is True for item in plan)


def test_calendario_avisa_si_faltan_franjas_para_las_horas_globales_actividad():
    plan = replicar_horario_completo_actividad(
        [{"fecha": date(2026, 9, 7), "inicio": "09:00", "fin": "11:00", "horas": 2}],
        [{"reparto_id": 10, "profesor_id": 1, "horas": 1}],
        horas_actividad=3,
    )

    assert [(item["estado"], item["horas"], item["horas_adjudicadas"]) for item in plan] == [
        ("PLANIFICADA", 2.0, 1.0),
        ("AJUSTE_PENDIENTE", 1.0, 1.0),
    ]


def test_dos_profesores_con_20_horas_ven_las_40_horas_del_grupo():
    sesiones = [
        {"fecha": date(2026, 9, 7) + timedelta(weeks=i), "inicio": "09:00", "fin": "11:00", "horas": 2}
        for i in range(20)
    ]
    plan = replicar_horario_completo_actividad(sesiones, [
        {"profesor_id": 1, "horas": 20}, {"profesor_id": 2, "horas": 20},
    ], horas_actividad=40)
    for profesor_id in (1, 2):
        propias = [item for item in plan if item['profesor_id'] == profesor_id]
        assert len(propias) == 20
        assert sum(item['horas'] for item in propias) == 40
        assert all(item['horas_adjudicadas'] == 20 for item in propias)
        assert all(item['estado'] == 'PLANIFICADA' for item in propias)
