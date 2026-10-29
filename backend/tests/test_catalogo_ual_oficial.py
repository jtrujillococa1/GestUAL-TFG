from cargar_catalogo_ual_oficial import vincular_horarios_oficiales


def _ficha(codigo: str, tipo: str = "GD", grupo: str = "A", plan: str = "4015"):
    return {
        "codigo": codigo,
        "tipo": tipo,
        "codigo_grupo": grupo,
        "codigo_grupo_oficial": grupo,
        "grupo": grupo,
        "codigo_plan": plan,
        "nombre_asignatura": "Materia de prueba",
        "nombre_actividad": "Teoría",
        "caracter": "Obligatoria",
        "idioma": "es",
    }


def test_plan_historico_419_usa_identificador_publico(monkeypatch):
    ficha = _ficha("4192202", plan="419")
    detalle = {
        "asignatura": [{"actividades": [{"abrv_tipo_grupo": "GD", "grupos": [{
            "grupo": "A", "hor": [{
                "per_datini": "2026-09-13T22:00:00Z",
                "franjas": [{"id_dia_semana": "LUN", "horini": 9, "minini": "00", "horfin": 11, "minfin": "00"}],
            }],
        }]}]}],
    }
    monkeypatch.setattr(
        "cargar_catalogo_ual_oficial._cargar_detalles",
        lambda fichas, cache: {("0419", "4192202"): detalle},
    )

    fichas, incidencias = vincular_horarios_oficiales([ficha], None)

    assert incidencias == []
    assert fichas[0]["origen_horario"] == "UAL_OFICIAL"
    assert fichas[0]["horario_detallado"][0]["fecha"] == "2026-09-14"


def test_horario_oficial_que_empieza_a_las_0830_se_conserva(monkeypatch):
    ficha = _ficha("40150001")
    detalle = {
        "asignatura": [{"actividades": [{"abrv_tipo_grupo": "GD", "grupos": [{
            "grupo": "A", "hor": [{
                "per_datini": "2026-09-13T22:00:00Z",
                "franjas": [{"id_dia_semana": "LUN", "horini": 8, "minini": "30", "horfin": 10, "minfin": "00"}],
            }],
        }]}]}],
    }
    monkeypatch.setattr(
        "cargar_catalogo_ual_oficial._cargar_detalles",
        lambda fichas, cache: {("4015", "40150001"): detalle},
    )

    fichas, incidencias = vincular_horarios_oficiales([ficha], None)

    assert incidencias == []
    assert fichas[0]["horario_detallado"][0]["inicio"] == "08:30"


def test_referencia_ual_anterior_se_marca_como_pendiente(monkeypatch):
    ficha = _ficha("71461202")
    monkeypatch.setattr("cargar_catalogo_ual_oficial._cargar_detalles", lambda fichas, cache: {})

    fichas, incidencias = vincular_horarios_oficiales([ficha], None)

    assert incidencias == []
    assert fichas[0]["origen_horario"] == "UAL_REFERENCIA_2025_26"
    assert fichas[0]["horario_confirmado"] is False
    assert fichas[0]["horario_detallado"][0]["fecha"] == "2027-01-06"


def test_actividad_dual_sin_franja_no_inventa_solapes(monkeypatch):
    ficha = _ficha("71461607")
    monkeypatch.setattr("cargar_catalogo_ual_oficial._cargar_detalles", lambda fichas, cache: {})

    fichas, incidencias = vincular_horarios_oficiales([ficha], None)

    assert incidencias == []
    assert fichas[0]["requiere_horario"] is False
    assert fichas[0]["origen_horario"] == "UAL_DUAL_SIN_FRANJA"
