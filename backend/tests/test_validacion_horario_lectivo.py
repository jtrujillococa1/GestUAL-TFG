import pytest

from core.horario import validar_franjas_horarias


def test_acepta_los_limites_del_horario_lectivo():
    validar_franjas_horarias("Lunes 08:00-10:00 | Miércoles 20:00-22:00")


@pytest.mark.parametrize("horario", ["Lunes 07:59-10:00", "Viernes 20:00-22:01"])
def test_rechaza_franjas_fuera_del_horario_lectivo(horario):
    with pytest.raises(ValueError, match="08:00 y las 22:00"):
        validar_franjas_horarias(horario)


@pytest.mark.parametrize("horario", [
    "Lunes 08:15-10:00", "Viernes 20:00-21:30", "Jueves 20:00-22:00",
])
def test_acepta_franjas_del_intervalo_ampliado(horario):
    validar_franjas_horarias(horario)


@pytest.mark.parametrize("horario", [
    "Lunes 10:00-09:00", "Lunes 10:00-10:00",
    "Lunes 08:60-10:00", "Lunes 20:00-24:00",
])
def test_ampliacion_no_admite_franjas_invalidas(horario):
    with pytest.raises(ValueError):
        validar_franjas_horarias(horario)
