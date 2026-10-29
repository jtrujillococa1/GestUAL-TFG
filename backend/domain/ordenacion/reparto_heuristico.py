"""Construcción rápida de repartos válidos para áreas docentes grandes.

No sustituye al modelo exacto: se utiliza cuando el optimizador agota el
tiempo intentando mejorar una solución. La heurística solo devuelve una
propuesta si cubre exactamente todas las cuotas, todas las cargas y respeta
las incompatibilidades de horario.
"""
from __future__ import annotations

from random import Random
from typing import Any, Dict, List, Tuple

from domain.ordenacion.disponibilidad import profesor_disponible_para_actividad


def _areas_profesor(profesor: Dict[str, Any]) -> set[int]:
    return set(profesor.get("area_ids") or ([profesor["area_id"]] if profesor.get("area_id") else []))


def _puede_cubrir(profesor: Dict[str, Any], actividad: Dict[str, Any]) -> bool:
    area = actividad.get("area_id")
    return (
        (area is None or area in _areas_profesor(profesor))
        and profesor_disponible_para_actividad(profesor, actividad)
    )


def _clave_actividad(eleccion: Dict[str, Any]) -> Tuple[Any, ...]:
    if eleccion.get("actividad_id") is not None:
        return ("id", eleccion["actividad_id"])
    return (eleccion["codigo"], eleccion["codigo_grupo"], eleccion.get("tipo") or eleccion.get("tipo_actividad"))


def construir_reparto_heuristico(
    elecciones_forzadas: List[Dict[str, Any]],
    profesores: List[Dict[str, Any]],
    actividades: List[Dict[str, Any]],
    incompatibilidades: List[Tuple[int, int]],
    escala: int = 10,
    intentos: int = 160,
) -> Dict[str, Any]:
    """Busca, con reinicios deterministas, un reparto completo y compatible."""
    profesores_por_nombre = {f"{p['apellidos']}, {p['nombre']}": p for p in profesores}
    actividad_por_id = {actividad["id"]: actividad for actividad in actividades}
    actividad_por_texto = {
        (actividad["codigo"], actividad["codigo_grupo"], actividad["tipo"]): actividad
        for actividad in actividades
    }
    conflictos = {actividad["id"]: set() for actividad in actividades}
    for primera, segunda in incompatibilidades:
        conflictos.setdefault(primera, set()).add(segunda)
        conflictos.setdefault(segunda, set()).add(primera)

    def actividad_de(eleccion: Dict[str, Any]) -> Dict[str, Any] | None:
        if eleccion.get("actividad_id") is not None:
            return actividad_por_id.get(eleccion["actividad_id"])
        return actividad_por_texto.get(_clave_actividad(eleccion))

    for semilla in range(intentos):
        azar = Random(semilla)
        capacidad = {profesor["id"]: round(float(profesor["horas_objetivo"]) * escala) for profesor in profesores}
        pendiente = {actividad["id"]: round(float(actividad["horas_totales"]) * escala) for actividad in actividades}
        asignadas: Dict[Tuple[int, int], int] = {}
        actividades_profesor: Dict[int, set[int]] = {profesor["id"]: set() for profesor in profesores}
        valido = True

        for eleccion in elecciones_forzadas:
            profesor = profesores_por_nombre.get(eleccion.get("profesor"))
            actividad = actividad_de(eleccion)
            unidades = round(float(eleccion.get("horas", 0)) * escala)
            if not profesor or not actividad or unidades <= 0 or not _puede_cubrir(profesor, actividad):
                valido = False
                break
            if conflictos.get(actividad["id"], set()).intersection(actividades_profesor[profesor["id"]]):
                valido = False
                break
            clave = (profesor["id"], actividad["id"])
            if clave in asignadas or capacidad[profesor["id"]] < unidades or pendiente[actividad["id"]] < unidades:
                valido = False
                break
            asignadas[clave] = unidades
            capacidad[profesor["id"]] -= unidades
            pendiente[actividad["id"]] -= unidades
            actividades_profesor[profesor["id"]].add(actividad["id"])
        if not valido:
            continue

        # Las más grandes y con más conflictos se sitúan antes para dejar el
        # máximo de alternativas a los grupos sencillos del final.
        orden = sorted(
            actividades,
            key=lambda actividad: (-len(conflictos.get(actividad["id"], set())), -pendiente[actividad["id"]], actividad["id"]),
        )
        for actividad in orden:
            actividad_id = actividad["id"]
            while pendiente[actividad_id] > 0:
                candidatas = [
                    profesor for profesor in profesores
                    if capacidad[profesor["id"]] > 0
                    and _puede_cubrir(profesor, actividad)
                    and not conflictos.get(actividad_id, set()).intersection(actividades_profesor[profesor["id"]])
                ]
                if not candidatas:
                    valido = False
                    break
                azar.shuffle(candidatas)
                # Se intenta cerrar una carga con el menor corte posible. Si
                # ninguna carga alcanza toda la cuota restante se consume la
                # mayor capacidad compatible.
                candidatas.sort(key=lambda profesor: (
                    0 if capacidad[profesor["id"]] >= pendiente[actividad_id] else 1,
                    abs(capacidad[profesor["id"]] - pendiente[actividad_id])
                    if capacidad[profesor["id"]] >= pendiente[actividad_id]
                    else -capacidad[profesor["id"]],
                ))
                profesor = candidatas[0]
                unidades = min(capacidad[profesor["id"]], pendiente[actividad_id])
                clave = (profesor["id"], actividad_id)
                asignadas[clave] = asignadas.get(clave, 0) + unidades
                capacidad[profesor["id"]] -= unidades
                pendiente[actividad_id] -= unidades
                actividades_profesor[profesor["id"]].add(actividad_id)
            if not valido:
                break
        if not valido or any(valor != 0 for valor in pendiente.values()) or any(valor != 0 for valor in capacidad.values()):
            continue

        reparto = []
        total_repartos = 0
        actividades_divididas = 0
        for actividad in actividades:
            if sum((profesor["id"], actividad["id"]) in asignadas for profesor in profesores) > 1:
                actividades_divididas += 1
        for profesor in profesores:
            actividades_prof = []
            for actividad in actividades:
                unidades = asignadas.get((profesor["id"], actividad["id"]), 0)
                if unidades <= 0:
                    continue
                total_repartos += 1
                actividades_prof.append({
                    "actividad_id": actividad["id"], "codigo": actividad["codigo"],
                    "tipo": actividad["tipo"], "tipo_actividad": actividad["tipo"],
                    "codigo_grupo": actividad["codigo_grupo"], "grupo": actividad["grupo"],
                    "idioma": actividad.get("idioma"), "duracion": actividad.get("duracion"),
                    "turno": actividad.get("turno"), "horas": unidades / escala,
                })
            reparto.append({
                "profesor": profesor["nombre"], "profesor_id": profesor["id"],
                "horas_totales": round(sum(item["horas"] for item in actividades_prof), 1),
                "actividades": actividades_prof,
            })
        return {
            "viable": True, "reparto": reparto, "total_repartos": total_repartos,
            "actividades_divididas": actividades_divididas, "cached": False, "heuristico": True,
        }

    return {"viable": False, "cached": False, "heuristico": True}
