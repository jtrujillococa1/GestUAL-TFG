"""Regresiones para profesores con carga distribuida entre áreas."""

import sys
from pathlib import Path

# Evita que el directorio tests/solver oculte el paquete de producción.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from solver.engine import resolver_reparto
from services.ordenacion_service import _puede_validar_por_transporte


def _profesor(identificador, nombre, carga, cargas_area):
    return {
        "id": identificador,
        "nombre": nombre,
        "apellidos": "Prueba",
        "horas_objetivo": carga,
        "area_id": next(iter(cargas_area)),
        "area_ids": list(cargas_area),
        "horas_objetivo_por_area": cargas_area,
    }


def _actividad(identificador, codigo, area_id):
    return {
        "id": identificador,
        "codigo": codigo,
        "tipo": "GD",
        "codigo_grupo": "T1",
        "grupo": "Teoría 1",
        "horas_totales": 6,
        "area_id": area_id,
    }


def test_solver_respeta_carga_de_un_docente_en_cada_area():
    profesores = [
        _profesor(1, "Multi", 6, {10: 3, 20: 3}),
        _profesor(2, "Bases", 3, {10: 3}),
        _profesor(3, "Software", 3, {20: 3}),
    ]
    actividades = [_actividad(101, "BD101", 10), _actividad(201, "IS201", 20)]

    resultado = resolver_reparto([], profesores, actividades, usar_cache=False)

    assert resultado["viable"] is True
    reparto_multi = next(fila for fila in resultado["reparto"] if fila["profesor"] == "Multi")
    horas_por_actividad = {actividad["actividad_id"]: actividad["horas"] for actividad in reparto_multi["actividades"]}
    assert horas_por_actividad == {101: 3.0, 201: 3.0}


def test_validacion_rapida_ignora_perfiles_multiarea_ajenos_al_area():
    profesores = [
        _profesor(1, "Local", 6, {10: 6}),
        _profesor(2, "Ajeno", 6, {20: 3, 30: 3}),
    ]
    actividades = [_actividad(101, "BD101", 10)]

    assert _puede_validar_por_transporte(profesores, actividades, 10, {"viable": True}) is True


def test_validacion_rapida_se_desactiva_ante_solapes_confirmados():
    profesores = [_profesor(1, "Local", 12, {10: 12})]
    actividades = [
        {
            **_actividad(101, "BD101", 10),
            "horario_confirmado": True, "dias": "Lunes", "horario": "09:00-10:30",
        },
        {
            **_actividad(102, "BD102", 10),
            "horario_confirmado": True, "dias": "Lunes", "horario": "09:00-10:30",
        },
    ]

    assert _puede_validar_por_transporte(profesores, actividades, 10, {"viable": True}) is False
