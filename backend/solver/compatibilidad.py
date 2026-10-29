import re
from datetime import date
from typing import Dict, List, Tuple, Optional, Any


MAP_DIAS = {
    "lun": "lun",
    "lunes": "lun",
    "mar": "mar",
    "martes": "mar",
    "mie": "mie",
    "mié": "mie",
    "miercoles": "mie",
    "miércoles": "mie",
    "jue": "jue",
    "jueves": "jue",
    "vie": "vie",
    "viernes": "vie",
    "sab": "sab",
    "sáb": "sab",
    "sabado": "sab",
    "sábado": "sab",
    "dom": "dom",
    "domingo": "dom",
}


def _normalizar_texto(txt: str) -> str:
    return (
        txt.strip()
        .lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
    )


def _normalizar_dia(txt: str) -> Optional[str]:
    if not txt:
        return None

    t = _normalizar_texto(txt)

    if t.startswith("lun"):
        return "lun"
    if t.startswith("mar"):
        return "mar"
    if t.startswith("mie"):
        return "mie"
    if t.startswith("jue"):
        return "jue"
    if t.startswith("vie"):
        return "vie"
    if t.startswith("sab"):
        return "sab"
    if t.startswith("dom"):
        return "dom"

    return MAP_DIAS.get(t)


def _hora_a_minutos(hora: str) -> int:
    h, m = hora.strip().split(":")
    return int(h) * 60 + int(m)


def _franjas_solapan(ini1: int, fin1: int, ini2: int, fin2: int) -> bool:
    return max(ini1, ini2) < min(fin1, fin2)


def _normalizar_duracion(valor: Any) -> Optional[str]:
    """
    Sirve para evitar incompatibilidades entre actividades de duración distinta.

    Acepta valores como:
    - 1, 2
    - '1', '2'
    - 'C1', 'C2'
    - 'Anual'
    - 'Primer cuatrimestre'
    - 'Segundo cuatrimestre'

    Si no se puede interpretar, devuelve texto normalizado.
    """
    if valor is None:
        return None

    txt = _normalizar_texto(str(valor))

    if txt in {"1", "c1", "1q", "cuatrimestre 1", "primer cuatrimestre", "primero"}:
        return "1"

    if txt in {"2", "c2", "2q", "cuatrimestre 2", "segundo cuatrimestre", "segundo"}:
        return "2"

    if txt in {"a", "anual", "todo el curso", "curso completo"}:
        return "anual"

    return txt or None


def _duraciones_compatibles(d1: Optional[str], d2: Optional[str]) -> bool:
    """
    Devuelve True si dos actividades pueden coincidir temporalmente.

    - Si falta una duración, se asume que pueden coincidir.
    - Si una es anual, puede coincidir con cualquiera.
    - Si ambas existen y son distintas, no coinciden.
    """
    if d1 is None or d2 is None:
        return True

    if d1 == "anual" or d2 == "anual":
        return True

    return d1 == d2


def _parse_dias(dias: str) -> List[str]:
    if not dias:
        return []

    resultado = []

    for parte in dias.split(","):
        dia = _normalizar_dia(parte)
        if dia and dia not in resultado:
            resultado.append(dia)

    return resultado


def _parse_bloques_horario(horario: str, dias: str = "") -> List[Tuple[str, int, int]]:
    """
    Devuelve una lista de tramos:
        [(dia, inicio_minutos, fin_minutos), ...]

    Soporta formato recomendado:
        'Lunes 09:00-11:00 | Miércoles 12:00-14:00'

    También soporta:
        'Lunes 09:00 - 11:00'
        '09:00-11:00' + dias='Lunes, Miércoles'
    """
    if not horario:
        return []

    texto = horario.strip()
    bloques: List[Tuple[str, int, int]] = []

    patron_con_dia = re.compile(
        r"([A-Za-zÁÉÍÓÚáéíóúÑñ]+)\s+(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})"
    )

    for m in patron_con_dia.finditer(texto):
        dia = _normalizar_dia(m.group(1))

        if not dia:
            continue

        ini = _hora_a_minutos(m.group(2))
        fin = _hora_a_minutos(m.group(3))

        if fin > ini:
            bloques.append((dia, ini, fin))

    if bloques:
        return bloques

    patron_solo_hora = re.compile(
        r"^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$"
    )

    m = patron_solo_hora.match(texto)

    if not m:
        return []

    ini = _hora_a_minutos(m.group(1))
    fin = _hora_a_minutos(m.group(2))

    if fin <= ini:
        return []

    for dia in _parse_dias(dias):
        bloques.append((dia, ini, fin))

    return bloques


def _parse_bloques_detallados(actividad: Dict) -> List[Tuple[str, int, int, Optional[date]]]:
    """Lee sesiones oficiales sin perder la fecha que determina el solape.

    ``horario_detallado`` es opcional para conservar la compatibilidad con los
    registros creados antes de que se importaran los horarios oficiales.
    """
    bloques: List[Tuple[str, int, int, Optional[date]]] = []
    for sesion in actividad.get("horario_detallado") or []:
        if not isinstance(sesion, dict):
            continue
        dia = _normalizar_dia(str(sesion.get("dia") or ""))
        try:
            inicio = _hora_a_minutos(str(sesion.get("inicio") or ""))
            fin = _hora_a_minutos(str(sesion.get("fin") or ""))
        except (TypeError, ValueError):
            continue
        if not dia or fin <= inicio:
            continue
        fecha = None
        if sesion.get("fecha"):
            try:
                fecha = date.fromisoformat(str(sesion["fecha"])[:10])
            except ValueError:
                continue
        bloques.append((dia, inicio, fin, fecha))
    return bloques


def _bloques_actividad(actividad: Dict) -> List[Tuple[str, int, int, Optional[date]]]:
    """Reserva el horario completo; la cuota no determina qué semanas imparte."""
    detallados = _parse_bloques_detallados(actividad)
    if detallados:
        return detallados
    return [
        (dia, inicio, fin, None)
        for dia, inicio, fin in _parse_bloques_horario(
            actividad.get("horario") or "", actividad.get("dias") or ""
        )
    ]


def actividades_incompatibles(
    a1: Dict, a2: Dict, considerar_horarios_sinteticos: bool = False,
) -> bool:
    # Los objetos de pruebas y algunas importaciones heredadas pueden no tener
    # id aún. Solo son la misma actividad cuando ambos identificadores existen.
    if a1.get("id") is not None and a1.get("id") == a2.get("id"):
        return False

    # Actividades como prácticas externas tienen carga docente, pero no una
    # ocupación semanal presencial. Aunque procedan de un dato heredado con
    # una franja residual, nunca deben bloquear una selección por horario.
    if not a1.get("requiere_horario", True) or not a2.get("requiere_horario", True):
        return False

    # El solver global puede ignorar franjas sintéticas provisionales para no
    # concluir que un catálogo de prueba es inviable por horarios inventados.
    # En cambio, al componer el borrador sí se consideran: el docente nunca
    # puede elegir dos grupos que visualmente coinciden en su semana.
    if not considerar_horarios_sinteticos and (
        (a1.get("origen_horario") == "SINTETICO" and not a1.get("horario_confirmado"))
        or (a2.get("origen_horario") == "SINTETICO" and not a2.get("horario_confirmado"))
    ):
        return False

    d1 = _normalizar_duracion(a1.get("duracion") or a1.get("cuatrimestre"))
    d2 = _normalizar_duracion(a2.get("duracion") or a2.get("cuatrimestre"))

    if not _duraciones_compatibles(d1, d2):
        return False

    bloques1 = _bloques_actividad(a1)
    bloques2 = _bloques_actividad(a2)

    if not bloques1 or not bloques2:
        return False

    for dia1, ini1, fin1, fecha1 in bloques1:
        for dia2, ini2, fin2, fecha2 in bloques2:
            if dia1 != dia2:
                continue

            # Dos sesiones con fecha exacta solo se bloquean cuando ocurren el
            # mismo día natural. Una franja sin fecha se interpreta como
            # semanal recurrente y por tanto puede coincidir con cualquier día.
            if fecha1 is not None and fecha2 is not None and fecha1 != fecha2:
                continue

            if _franjas_solapan(ini1, fin1, ini2, fin2):
                return True

    return False


def construir_incompatibilidades(
    actividades: List[Dict], considerar_horarios_sinteticos: bool = False,
) -> List[Tuple[int, int]]:
    """Construye las parejas que un mismo profesor no puede impartir.

    El motor ordinario conserva por defecto el comportamiento histórico: no
    bloquea toda una ordenación por horarios sintéticos aún no confirmados.
    Los flujos que van a proponer o confirmar una reparación sí deben pedir
    explícitamente esa comprobación, para que nunca entreguen al gestor un
    plan que la validación final vaya a rechazar por solape visual.
    """
    incompatibles: List[Tuple[int, int]] = []

    n = len(actividades)

    for i in range(n):
        for j in range(i + 1, n):
            if actividades_incompatibles(
                actividades[i], actividades[j],
                considerar_horarios_sinteticos=considerar_horarios_sinteticos,
            ):
                incompatibles.append((actividades[i]["id"], actividades[j]["id"]))

    return incompatibles


# Alias temporal por compatibilidad con código antiguo.
grupos_incompatibles = actividades_incompatibles
