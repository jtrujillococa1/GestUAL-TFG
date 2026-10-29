"""Reglas de disponibilidad docente por cuatrimestre.

La disponibilidad limita las actividades que un docente puede asumir, no su
posición en la cola. Así un perfil que solo está presente un cuatrimestre
mantiene su carga, pero debe cubrirla completamente con grupos compatibles.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Set
import unicodedata


DISPONIBILIDADES = {"PRIMERO", "SEGUNDO", "AMBOS"}


def normalizar_disponibilidad(valor: object) -> str:
    texto = str(valor or "AMBOS").strip().upper()
    aliases = {
        "C1": "PRIMERO", "1": "PRIMERO", "1Q": "PRIMERO", "PRIMER": "PRIMERO",
        "C2": "SEGUNDO", "2": "SEGUNDO", "2Q": "SEGUNDO", "SEGUNDO": "SEGUNDO",
        "ANUAL": "AMBOS", "TODOS": "AMBOS", "TODO": "AMBOS",
    }
    texto = aliases.get(texto, texto)
    return texto if texto in DISPONIBILIDADES else "AMBOS"


def etiqueta_disponibilidad(valor: object) -> str:
    return {
        "PRIMERO": "Solo 1.º cuatrimestre",
        "SEGUNDO": "Solo 2.º cuatrimestre",
        "AMBOS": "Ambos cuatrimestres",
    }[normalizar_disponibilidad(valor)]


def _normalizar_texto(valor: object) -> str:
    texto = unicodedata.normalize("NFD", str(valor or "").strip().lower())
    return "".join(caracter for caracter in texto if unicodedata.category(caracter) != "Mn")


def _cuatrimestre_fecha(fecha: object) -> str | None:
    try:
        fecha_real = date.fromisoformat(str(fecha)[:10])
    except (TypeError, ValueError):
        return None
    # El curso UAL comienza en septiembre: septiembre-diciembre pertenecen al
    # primer cuatrimestre y enero-agosto al segundo.
    return "C1" if fecha_real.month >= 9 else "C2"


def cuatrimestres_actividad(actividad: Dict[str, Any]) -> Set[str]:
    """Obtiene los cuatrimestres reales de la actividad.

    Las sesiones con fecha oficial tienen prioridad. Para catálogos manuales o
    sin fechas se usa ``duracion``. Lo desconocido se trata como anual para no
    permitir que una disponibilidad restringida acepte docencia incierta.
    """
    desde_sesiones = {
        cuatrimestre
        for sesion in (actividad.get("horario_detallado") or [])
        if isinstance(sesion, dict)
        for cuatrimestre in [_cuatrimestre_fecha(sesion.get("fecha"))]
        if cuatrimestre
    }
    if desde_sesiones:
        return desde_sesiones

    duracion = _normalizar_texto(actividad.get("duracion") or actividad.get("cuatrimestre"))
    if duracion in {"1", "c1", "1c", "1q", "primer cuatrimestre", "primero"}:
        return {"C1"}
    if duracion in {"2", "c2", "2c", "2q", "segundo cuatrimestre", "segundo"}:
        return {"C2"}
    # "A" es el código habitual de anual en la exportación UAL.
    if duracion in {"a", "anual", "curso completo", "todo el curso"}:
        return {"C1", "C2"}
    return {"C1", "C2"}


def profesor_disponible_para_actividad(profesor: Dict[str, Any], actividad: Dict[str, Any]) -> bool:
    disponibilidad = normalizar_disponibilidad(profesor.get("disponibilidad_cuatrimestre"))
    if disponibilidad == "AMBOS":
        return True
    permitidos = {"C1"} if disponibilidad == "PRIMERO" else {"C2"}
    return cuatrimestres_actividad(actividad).issubset(permitidos)


def motivo_no_disponibilidad(profesor: Dict[str, Any], actividad: Dict[str, Any]) -> str | None:
    if profesor_disponible_para_actividad(profesor, actividad):
        return None
    disponibilidad = normalizar_disponibilidad(profesor.get("disponibilidad_cuatrimestre"))
    cuatrimestres = cuatrimestres_actividad(actividad)
    periodo = (
        "ambos cuatrimestres" if cuatrimestres == {"C1", "C2"}
        else "el primer cuatrimestre" if "C1" in cuatrimestres
        else "el segundo cuatrimestre"
    )
    limite = "el primer cuatrimestre" if disponibilidad == "PRIMERO" else "el segundo cuatrimestre"
    return f"Disponibilidad restringida: este profesor solo puede impartir en {limite} y la actividad se desarrolla en {periodo}."
