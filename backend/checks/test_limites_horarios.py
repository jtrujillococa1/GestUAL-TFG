"""Comprueba el intervalo admitido en la API y la lectura del catálogo UAL."""
import pytest

from api.routes.actividades import HorarioDetalladoRequest
from cargar_catalogo_ual_oficial import _sesiones_ual


@pytest.mark.parametrize("inicio,fin,admitida", [
    ("08:00", "10:00", True),
    ("08:15", "10:00", True),
    ("20:00", "21:30", True),
    ("20:00", "22:00", True),
    ("07:59", "10:00", False),
    ("20:00", "22:01", False),
    ("10:00", "09:00", False),
])
@pytest.mark.parametrize("via", ["api", "catalogo"])
def test_limites_coherentes(inicio, fin, admitida, via):
    def validar():
        if via == "api":
            return HorarioDetalladoRequest(dia="Lunes", inicio=inicio, fin=fin)
        hi, mi = inicio.split(":")
        hf, mf = fin.split(":")
        return _sesiones_ual({"grupo": "A", "hor": [{
            "per_datini": "2026-09-13T22:00:00Z",
            "franjas": [{"id_dia_semana": "LUN", "horini": int(hi),
                         "minini": mi, "horfin": int(hf), "minfin": mf}],
        }]})

    if admitida:
        resultado = validar()
        if via == "api":
            assert (resultado.inicio, resultado.fin) == (inicio, fin)
        else:
            assert len(resultado) == 1
            assert (resultado[0]["inicio"], resultado[0]["fin"]) == (inicio, fin)
    else:
        from cargar_catalogo_ual_oficial import ErrorImportacionDocente
        error = ValueError if via == "api" else ErrorImportacionDocente
        with pytest.raises(error):
            validar()
