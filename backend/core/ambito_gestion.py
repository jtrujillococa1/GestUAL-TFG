"""Ámbitos de las cuentas de gestión, independientes de perfiles docentes."""
from __future__ import annotations

from typing import Any

from db.connection import cursor_ctx


def obtener_ambito_gestor(usuario_id: int, rol: str) -> dict[str, set[int]]:
    """Devuelve las áreas y departamentos asignados a una cuenta responsable.

    Las cuentas responsables no se enlazan a ``profesores``: su autoridad se
    obtiene exclusivamente de la responsabilidad configurada en el área o el
    departamento. Así un docente puede conservar su cuenta y su turno aunque
    la misma persona asuma además una responsabilidad institucional.
    """
    departamentos: set[int] = set()
    areas: set[int] = set()
    with cursor_ctx() as cur:
        if rol == "responsable_departamento":
            cur.execute(
                "SELECT id FROM departamentos WHERE responsable_departamento_id=%s",
                (usuario_id,),
            )
            departamentos = {fila["id"] for fila in cur.fetchall()}
            if departamentos:
                cur.execute(
                    "SELECT id FROM areas WHERE departamento_id = ANY(%s)",
                    (list(departamentos),),
                )
                areas = {fila["id"] for fila in cur.fetchall()}
        elif rol == "responsable_area":
            cur.execute(
                "SELECT id, departamento_id FROM areas WHERE responsable_area_id=%s",
                (usuario_id,),
            )
            filas = cur.fetchall()
            areas = {fila["id"] for fila in filas}
            departamentos = {fila["departamento_id"] for fila in filas}
    return {"areas": areas, "departamentos": departamentos}


def es_gestor(rol: str) -> bool:
    return rol in {"responsable_departamento", "responsable_area"}
