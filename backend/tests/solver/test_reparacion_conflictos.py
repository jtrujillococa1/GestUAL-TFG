from solver.reparacion_conflictos import proponer_reparacion_area
import pytest


def test_enumera_planes_distintos_con_prioridades_y_detecta_agotamiento():
    profesores = [_profesor(1, 'Uno, Ana', 0.1), _profesor(2, 'Dos, Bruno', 0.1)]
    profesores[0]['prioridades_asignaturas'] = {'B': 1, 'A': 2}
    actividades = [_actividad(11, 'A', 0.1, 'Lunes 09:00-10:00'), _actividad(12, 'B', 0.1, 'Martes 09:00-10:00')]
    primera = proponer_reparacion_area(10, 1, profesores, actividades, [], max_profesores=None)
    assert primera['viable']
    assert next(f for f in primera['plan'] if f['profesor_id'] == 1)['actividad_id'] == 12
    segunda = proponer_reparacion_area(10, 1, profesores, actividades, [], planes_excluidos=[primera['plan']], max_profesores=None)
    assert segunda['viable']
    assert segunda['plan'] != primera['plan']
    agotadas = proponer_reparacion_area(10, 1, profesores, actividades, [], planes_excluidos=[primera['plan'], segunda['plan']], max_profesores=None)
    assert not agotadas['viable']
    assert 'No quedan' in agotadas['motivo']


def _profesor(profesor_id, nombre, objetivo):
    apellidos, pila = nombre.split(", ")
    return {
        "id": profesor_id,
        "nombre": pila,
        "apellidos": apellidos,
        "area_id": 10,
        "area_ids": [10],
        "horas_objetivo": objetivo,
        "horas_objetivo_por_area": {10: objetivo},
        "disponibilidad_cuatrimestre": "AMBOS",
    }


def _actividad(actividad_id, codigo, horas, horario):
    return {
        "id": actividad_id,
        "codigo": codigo,
        "nombre_asignatura": codigo,
        "tipo": "GD",
        "codigo_grupo": "A",
        "grupo": "GRUPO A",
        "area_id": 10,
        "horas_totales": horas,
        "duracion": "C1",
        "requiere_horario": True,
        "horario_confirmado": True,
        "origen_horario": "OFICIAL",
        "horario": horario,
        "dias": "Lunes",
    }


def test_propone_una_cadena_minima_que_desbloquea_al_profesor():
    profesores = [
        _profesor(1, "García, Ana", 4),
        _profesor(2, "López, Bruno", 4),
    ]
    # Ana ya imparte C (2 h); B se solapa con C y no puede completar su
    # carga con la actividad aún libre. El solver mueve parte de A a Ana y
    # permite que Bruno absorba B, manteniendo todas las cuotas exactas.
    actividades = [
        _actividad(11, "A", 4, "Martes 09:00-11:00"),
        _actividad(12, "B", 2, "Lunes 09:00-11:00"),
        _actividad(13, "C", 2, "Lunes 09:00-11:00"),
    ]
    confirmadas = [
        {"profesor_id": 1, "profesor": "García, Ana", "actividad_id": 13, "horas": 2},
        {"profesor_id": 2, "profesor": "López, Bruno", "actividad_id": 11, "horas": 4},
    ]

    resultado = proponer_reparacion_area(10, 1, profesores, actividades, confirmadas)

    assert resultado["viable"] is True
    assert resultado["movimientos"]
    plan_ana = [linea for linea in resultado["plan"] if linea["profesor_id"] == 1]
    assert sum(linea["horas"] for linea in plan_ana) == 4
    assert any(linea["actividad_id"] == 11 for linea in plan_ana)


def test_no_propone_cambios_si_la_carga_del_area_no_cuadra():
    resultado = proponer_reparacion_area(
        10,
        1,
        [_profesor(1, "García, Ana", 4)],
        [_actividad(11, "A", 2, "Martes 09:00-11:00")],
        [],
    )
    assert resultado["viable"] is False
    assert "equilibrada" in resultado["motivo"]


def test_respeta_una_prohibicion_horaria_concreta_para_un_profesor():
    profesores = [
        _profesor(1, "García, Ana", 4),
        _profesor(2, "López, Bruno", 4),
    ]
    actividades = [
        _actividad(11, "A", 2, "Lunes 09:00-11:00"),
        _actividad(12, "B", 2, "Martes 09:00-11:00"),
        _actividad(13, "C", 2, "Miércoles 09:00-11:00"),
        _actividad(14, "D", 2, "Jueves 09:00-11:00"),
    ]

    resultado = proponer_reparacion_area(
        10, 1, profesores, actividades, [],
        prohibiciones_horarias={(1, 11, 12)},
    )

    assert resultado["viable"] is True
    actividades_ana = {
        linea["actividad_id"]
        for linea in resultado["plan"]
        if linea["profesor_id"] == 1
    }
    assert not {11, 12}.issubset(actividades_ana)


@pytest.mark.parametrize('preferencias', [{'B':1,'A':2},{'B':20}])
def test_prefiere_asignatura_prioritaria_y_minimo_numero_de_docentes(preferencias):
    profesores = [
        _profesor(1, "García, Ana", 2),
        _profesor(2, "López, Bruno", 2),
        _profesor(3, "Martín, Carla", 2),
    ]
    # Ana necesita recuperar 2 h. Bruno puede ceder A o B con el mismo
    # movimiento y Carla no necesita participar. Ana declara B como primera
    # preferencia: el modelo debe escoger ese intercambio de dos personas.
    profesores[0]["prioridades_asignaturas"] = preferencias
    actividades = [
        _actividad(11, "A", 2, "Lunes 09:00-11:00"),
        _actividad(12, "B", 2, "Martes 09:00-11:00"),
        _actividad(13, "C", 2, "Miércoles 09:00-11:00"),
    ]
    confirmadas = [
        {"profesor_id": 2, "profesor": "López, Bruno", "actividad_id": 11, "horas": 2},
        {"profesor_id": 2, "profesor": "López, Bruno", "actividad_id": 12, "horas": 2},
        {"profesor_id": 3, "profesor": "Martín, Carla", "actividad_id": 13, "horas": 2},
    ]

    resultado = proponer_reparacion_area(10, 1, profesores, actividades, confirmadas)

    assert resultado["viable"] is True
    assert {item["profesor_id"] for item in resultado["afectados"]} == {1, 2}
    plan_ana = [linea for linea in resultado["plan"] if linea["profesor_id"] == 1]
    assert [(linea["actividad_id"], linea["horas"]) for linea in plan_ana] == [(12, 2.0)]
    movimiento = next(item for item in resultado["movimientos"] if item["hacia_profesor_id"] == 1)
    assert movimiento["prioridad_destino"] == preferencias['B']
