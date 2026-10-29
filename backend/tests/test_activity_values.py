from core.activity_values import normalizar_tipo_actividad, normalizar_turno


def test_normaliza_codigos_legacy_de_actividad():
    assert normalizar_tipo_actividad("T") == "GD"
    assert normalizar_tipo_actividad("P") == "GT"
    assert normalizar_tipo_actividad("L") == "GL"
    assert normalizar_tipo_actividad("S") == "GA"


def test_conserva_valores_canonicos_de_actividad():
    assert normalizar_tipo_actividad("GD") == "GD"
    assert normalizar_tipo_actividad("GA") == "GA"


def test_normaliza_turnos_legacy():
    assert normalizar_turno("M") == "Mañana"
    assert normalizar_turno("T") == "Tarde"
    assert normalizar_turno("N") == "Noche"


def test_conserva_turnos_canonicos():
    assert normalizar_turno("Mañana") == "Mañana"
    assert normalizar_turno("Noche") == "Noche"


def test_normaliza_turnos_reales_de_la_exportacion_docente():
    assert normalizar_turno("tarde SEMIPRESENCIAL y VIRTUAL") == "Tarde semipresencial y virtual"
    assert normalizar_turno("Mañana/Tarde") == "Mañana/Tarde"
