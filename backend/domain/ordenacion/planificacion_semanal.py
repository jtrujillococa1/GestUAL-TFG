"""Reglas puras para construir el calendario semanal de docencia.

La ordenación decide *cuántas* horas de una actividad asume cada persona.
El calendario, en cambio, es una referencia de disponibilidad: muestra el
horario oficial completo de la actividad a cada docente que participa en ella.
El reparto de semanas entre docentes se realiza posteriormente y no debe
inventarse ni inferirse a partir del orden de adjudicación.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Sequence
import re
import unicodedata


DIAS_SEMANA = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
}


def normalizar_dia(valor: object) -> int | None:
    """Convierte el nombre de un día lectivo a ``date.weekday()``."""
    texto = unicodedata.normalize("NFD", str(valor or "").strip().lower())
    texto = "".join(char for char in texto if unicodedata.category(char) != "Mn")
    return DIAS_SEMANA.get(texto)


def horas_entre(inicio: str, fin: str) -> float:
    """Devuelve la duración de una sesión HH:MM-HH:MM en horas."""
    inicio_dt = datetime.strptime(str(inicio)[:5], "%H:%M")
    fin_dt = datetime.strptime(str(fin)[:5], "%H:%M")
    return round((fin_dt - inicio_dt).total_seconds() / 3600, 2)


def generar_sesiones_recurrentes(
    fecha_inicio: date,
    fecha_fin: date,
    franjas: Iterable[Dict[str, Any]],
    fechas_no_lectivas: Iterable[date] = (),
) -> List[Dict[str, Any]]:
    """Expande franjas semanales únicamente en fechas lectivas válidas."""
    no_lectivas = set(fechas_no_lectivas)
    sesiones: List[Dict[str, Any]] = []
    actual = fecha_inicio
    franjas_validas = []
    for franja in franjas:
        dia = normalizar_dia(franja.get("dia"))
        inicio, fin = franja.get("inicio"), franja.get("fin")
        if dia is None or not inicio or not fin:
            continue
        try:
            horas = horas_entre(str(inicio), str(fin))
        except ValueError:
            continue
        if horas > 0:
            franjas_validas.append({"dia_semana": dia, "inicio": str(inicio)[:5], "fin": str(fin)[:5], "horas": horas})

    while actual <= fecha_fin:
        if actual.weekday() < 5 and actual not in no_lectivas:
            for franja in franjas_validas:
                if actual.weekday() == franja["dia_semana"]:
                    sesiones.append({"fecha": actual, **franja})
        actual += timedelta(days=1)
    return sorted(sesiones, key=lambda sesion: (sesion["fecha"], sesion["inicio"], sesion["fin"]))


def extraer_franjas(horario: object, dias: object) -> List[Dict[str, str]]:
    """Extrae las franjas de los formatos manuales admitidos por el formulario."""
    texto = str(horario or "")
    completas = re.findall(
        r"([A-Za-zÁÉÍÓÚáéíóúÑñ]+)\s+(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})",
        texto,
    )
    if completas:
        return [{"dia": dia, "inicio": inicio.zfill(5), "fin": fin.zfill(5)} for dia, inicio, fin in completas]

    solo_horas = re.findall(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", texto)
    dias_lista = [dia.strip() for dia in re.split(r"[,/;·|]", str(dias or "")) if dia.strip()]
    if len(solo_horas) == 1:
        inicio, fin = solo_horas[0]
        return [{"dia": dia, "inicio": inicio.zfill(5), "fin": fin.zfill(5)} for dia in dias_lista]
    return []


def sumar_horas(hora: str, horas: float) -> str:
    """Avanza una hora HH:MM el número de horas indicado, con precisión de minuto."""
    base = datetime.strptime(str(hora)[:5], "%H:%M")
    return (base + timedelta(minutes=round(float(horas) * 60))).strftime("%H:%M")


def repartir_sesiones_consecutivas(
    sesiones: Sequence[Dict[str, Any]], adjudicaciones: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Modelo de compatibilidad para el solver, no para el calendario visible.

    El motor conserva esta simulación para poder valorar solapes exactos con
    las horas que cada docente ha adjudicado. La interfaz semanal usa
    :func:`replicar_horario_completo_actividad` y no comunica este reparto
    provisional como si fuese una planificación real de semanas.
    """
    disponibles = sorted(sesiones, key=lambda sesion: (sesion["fecha"], sesion["inicio"], sesion["fin"]))
    resultado: List[Dict[str, Any]] = []
    indice_sesion = 0

    for orden_adjudicacion, adjudicacion in enumerate(adjudicaciones, start=1):
        restante = round(float(adjudicacion["horas"]), 2)
        orden_sesion = 0
        while restante > 0.01 and indice_sesion < len(disponibles):
            sesion = disponibles[indice_sesion]
            horas = round(float(sesion["horas"]), 2)
            horas_asignadas = min(restante, horas)
            inicio = sesion["inicio"]
            fin = sesion["fin"] if horas_asignadas + 0.01 >= horas else sumar_horas(inicio, horas_asignadas)
            orden_sesion += 1
            resultado.append({
                "reparto_id": adjudicacion.get("reparto_id"),
                "profesor_id": adjudicacion["profesor_id"],
                "fecha": sesion["fecha"],
                "inicio": inicio,
                "fin": fin,
                "horas": horas_asignadas,
                "orden_adjudicacion": orden_adjudicacion,
                "orden_sesion": orden_sesion,
                "estado": "PLANIFICADA",
                "observacion": None,
            })
            restante = round(restante - horas_asignadas, 2)
            if horas_asignadas + 0.01 >= horas:
                indice_sesion += 1
            else:
                disponibles[indice_sesion] = {
                    **sesion,
                    "inicio": fin,
                    "horas": round(horas - horas_asignadas, 2),
                }

        if restante > 0.01:
            resultado.append({
                "reparto_id": adjudicacion.get("reparto_id"),
                "profesor_id": adjudicacion["profesor_id"],
                "fecha": None,
                "inicio": None,
                "fin": None,
                "horas": restante,
                "orden_adjudicacion": orden_adjudicacion,
                "orden_sesion": orden_sesion + 1,
                "estado": "AJUSTE_PENDIENTE",
                "observacion": "No hay suficientes franjas oficiales para simular el reparto.",
            })
    return resultado


def replicar_horario_completo_actividad(
    sesiones: Sequence[Dict[str, Any]],
    adjudicaciones: Sequence[Dict[str, Any]],
    horas_actividad: float,
) -> List[Dict[str, Any]]:
    """Copia el horario oficial completo para cada docente adjudicado.

    Una adjudicación de 20 h dentro de una actividad de 41 h no significa que
    el docente imparta necesariamente las primeras 20 h del cuatrimestre. La
    distribución real se acuerda después. Por tanto, los dos docentes ven las
    mismas franjas oficiales completas, mientras ``horas_adjudicadas`` conserva
    su carga individual y ``horas`` sigue siendo la duración real de clase.
    """
    oficiales = sorted(sesiones, key=lambda sesion: (sesion["fecha"], sesion["inicio"], sesion["fin"]))
    total_oficial = round(sum(float(sesion["horas"]) for sesion in oficiales), 2)
    total_actividad = round(float(horas_actividad), 2)
    faltan_horas = round(max(0.0, total_actividad - total_oficial), 2)
    resultado: List[Dict[str, Any]] = []

    for orden_adjudicacion, adjudicacion in enumerate(adjudicaciones, start=1):
        horas_adjudicadas = round(float(adjudicacion["horas"]), 2)
        for orden_sesion, sesion in enumerate(oficiales, start=1):
            resultado.append({
                "reparto_id": adjudicacion.get("reparto_id"),
                "profesor_id": adjudicacion["profesor_id"],
                "fecha": sesion["fecha"],
                "inicio": sesion["inicio"],
                "fin": sesion["fin"],
                "horas": round(float(sesion["horas"]), 2),
                "horas_adjudicadas": horas_adjudicadas,
                "es_horario_referencia": True,
                "orden_adjudicacion": orden_adjudicacion,
                "orden_sesion": orden_sesion,
                "estado": "PLANIFICADA",
                "observacion": None,
            })

        if faltan_horas > 0.01:
            resultado.append({
                "reparto_id": adjudicacion.get("reparto_id"),
                "profesor_id": adjudicacion["profesor_id"],
                "fecha": None,
                "inicio": None,
                "fin": None,
                "horas": faltan_horas,
                "horas_adjudicadas": horas_adjudicadas,
                "es_horario_referencia": True,
                "orden_adjudicacion": orden_adjudicacion,
                "orden_sesion": len(oficiales) + 1,
                "estado": "AJUSTE_PENDIENTE",
                "observacion": (
                    f"Las sesiones registradas suman {total_oficial:.1f} h y la carga de la actividad "
                    f"es {total_actividad:.1f} h. La diferencia de {faltan_horas:.1f} h requiere "
                    "contrastar la modalidad docente y la planificación oficial; no demuestra por sí sola "
                    "que falten clases presenciales."
                ),
            })
    return resultado
