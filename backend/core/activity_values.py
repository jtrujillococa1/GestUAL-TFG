"""Normalización de valores históricos de actividades.

La base de datos contiene tanto los códigos históricos de una letra como los
valores canónicos expuestos por la API. El dominio trabaja exclusivamente con
los valores canónicos para que las claves del solver y los schemas coincidan.
"""

from typing import Optional


_TIPOS_LEGACY = {
    "T": "GD",
    "P": "GT",
    "L": "GL",
    "S": "GA",
}

_TURNOS_LEGACY = {
    "M": "Mañana",
    "T": "Tarde",
    "N": "Noche",
}

_TURNOS_REALES = {
    "manana": "Mañana",
    "mañana": "Mañana",
    "tarde": "Tarde",
    "noche": "Noche",
    "mañana/tarde": "Mañana/Tarde",
    "manana/tarde": "Mañana/Tarde",
    "tarde semipresencial y virtual": "Tarde semipresencial y virtual",
}


def normalizar_tipo_actividad(valor: Optional[str]) -> Optional[str]:
    """Convierte un código histórico de tipo al contrato actual de la API."""
    return _TIPOS_LEGACY.get(valor, valor)


def normalizar_turno(valor: Optional[str]) -> Optional[str]:
    """Convierte códigos históricos y variantes reales al contrato de la API."""
    if valor is None:
        return None
    if valor in _TURNOS_LEGACY:
        return _TURNOS_LEGACY[valor]
    normalizado = " ".join(valor.strip().split()).lower()
    return _TURNOS_REALES.get(normalizado, valor)
