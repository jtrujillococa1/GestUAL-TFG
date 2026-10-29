"""Reglas comunes para las franjas lectivas de las actividades."""
import re

HORA_INICIO_ADMITIDA = "08:00"
HORA_FIN_ADMITIDA = "22:00"


def validar_sesion_horaria(inicio: str, fin: str) -> None:
    """Valida una sesión dentro del intervalo admitido por GestUAL."""
    def a_minutos(valor: str) -> int:
        if not re.fullmatch(r"\d{1,2}:\d{2}", valor):
            raise ValueError("Utiliza horas con formato HH:MM.")
        hora, minuto = (int(parte) for parte in valor.split(":"))
        if hora > 23 or minuto > 59:
            raise ValueError("Las horas deben estar entre 00:00 y 23:59.")
        return hora * 60 + minuto

    inicio_minutos = a_minutos(inicio)
    fin_minutos = a_minutos(fin)
    if inicio_minutos >= fin_minutos:
        raise ValueError("La hora de fin debe ser posterior a la de inicio.")
    if (inicio_minutos < a_minutos(HORA_INICIO_ADMITIDA)
            or fin_minutos > a_minutos(HORA_FIN_ADMITIDA)):
        raise ValueError(
            f"Las sesiones deben estar entre las {HORA_INICIO_ADMITIDA} "
            f"y las {HORA_FIN_ADMITIDA}."
        )


def validar_franjas_horarias(horario: str) -> None:
    """Exige franjas ordenadas dentro del intervalo admitido 08:00–22:00."""
    franjas = re.findall(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", horario)
    if not franjas:
        raise ValueError("El horario debe contener franjas como 09:00-10:30.")

    for inicio, fin in franjas:
        validar_sesion_horaria(inicio, fin)
