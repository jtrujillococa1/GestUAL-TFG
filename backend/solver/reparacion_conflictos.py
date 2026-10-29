"""Propuestas de reparación supervisadas para una ordenación bloqueada.

No modifica la base de datos ni confirma cambios: calcula una distribución
alternativa de un área, minimizando las horas que tendrían que cambiar de
profesor. La decisión de aplicarla pertenece siempre a un gestor.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from ortools.linear_solver import pywraplp

from core.config import settings
from domain.ordenacion.disponibilidad import profesor_disponible_para_actividad
from solver.compatibilidad import construir_incompatibilidades


ESCALA = settings.ESCALA_SOLVER
# Una propuesta que implica una cadena larga rara vez es comprensible o
# aceptable en una ordenación real. Tres personas permite una cesión directa
# o una pequeña cadena, sin convertir el apartado de conflictos en una
# reordenación completa del área.
MAX_PROFESORES_PROPUESTA = 3


def _esc(horas: float) -> int:
    return round(float(horas) * ESCALA)


def _desc(unidades: int) -> float:
    return unidades / ESCALA


def _nombre(profesor: Dict[str, Any]) -> str:
    return f"{profesor['apellidos']}, {profesor['nombre']}"


def _areas_profesor(profesor: Dict[str, Any]) -> set[int]:
    return set(profesor.get("area_ids") or ([profesor["area_id"]] if profesor.get("area_id") else []))


def _objetivo_area(profesor: Dict[str, Any], area_id: int) -> float:
    cargas = profesor.get("horas_objetivo_por_area") or {}
    valor = cargas.get(area_id, cargas.get(str(area_id)))
    if valor is not None:
        return float(valor)
    return float(profesor.get("horas_objetivo", 0)) if profesor.get("area_id") == area_id else 0.0


def _puede_cubrir(profesor: Dict[str, Any], actividad: Dict[str, Any]) -> bool:
    return (
        actividad.get("area_id") in _areas_profesor(profesor)
        and profesor_disponible_para_actividad(profesor, actividad)
    )


def _movimientos(
    actuales: Dict[tuple[int, int], int], propuesta: Dict[tuple[int, int], int],
    profesores: List[Dict[str, Any]], actividades: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Convierte las diferencias del modelo en cesiones legibles por grupo."""
    por_profesor = {profesor["id"]: profesor for profesor in profesores}
    resultado: List[Dict[str, Any]] = []
    for actividad in actividades:
        actividad_id = actividad["id"]
        ceden = [
            [profesor["id"], actuales.get((profesor["id"], actividad_id), 0) - propuesta.get((profesor["id"], actividad_id), 0)]
            for profesor in profesores
            if actuales.get((profesor["id"], actividad_id), 0) > propuesta.get((profesor["id"], actividad_id), 0)
        ]
        reciben = [
            [profesor["id"], propuesta.get((profesor["id"], actividad_id), 0) - actuales.get((profesor["id"], actividad_id), 0)]
            for profesor in profesores
            if propuesta.get((profesor["id"], actividad_id), 0) > actuales.get((profesor["id"], actividad_id), 0)
        ]
        indice_cede = indice_recibe = 0
        while indice_cede < len(ceden) and indice_recibe < len(reciben):
            profesor_origen, disponible = ceden[indice_cede]
            profesor_destino, necesario = reciben[indice_recibe]
            unidades = min(disponible, necesario)
            if unidades:
                resultado.append({
                    "actividad_id": actividad_id,
                    "asignatura": actividad.get("nombre_asignatura") or actividad.get("codigo"),
                    "codigo": actividad.get("codigo"),
                    "grupo": actividad.get("grupo") or actividad.get("codigo_grupo"),
                    "desde_profesor_id": profesor_origen,
                    "desde": _nombre(por_profesor[profesor_origen]),
                    "hacia_profesor_id": profesor_destino,
                    "hacia": _nombre(por_profesor[profesor_destino]),
                    "horas": _desc(unidades),
                    "prioridad_destino": (
                        (por_profesor[profesor_destino].get("prioridades_asignaturas") or {})
                        .get(str(actividad.get("codigo")))
                    ),
                })
            ceden[indice_cede][1] -= unidades
            reciben[indice_recibe][1] -= unidades
            if ceden[indice_cede][1] == 0:
                indice_cede += 1
            if reciben[indice_recibe][1] == 0:
                indice_recibe += 1
    return resultado


def _resolver_minimo(solver: Any, coeficientes: Dict[Any, int]) -> tuple[int, int]:
    """Resuelve una fase lexicográfica y devuelve su mínimo entero.

    No se mezclan los criterios en un único peso enorme: así se garantiza que
    primero se minimizan las personas afectadas, después las horas movidas y
    finalmente se respetan las preferencias docentes como desempate.
    """
    objetivo = solver.Objective()
    objetivo.Clear()
    for variable, coeficiente in coeficientes.items():
        objetivo.SetCoefficient(variable, coeficiente)
    objetivo.SetMinimization()
    estado = solver.Solve()
    if estado not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return estado, 0
    return estado, int(round(objetivo.Value()))


def proponer_reparacion_area(
    area_id: int,
    profesor_bloqueado_id: int,
    profesores: List[Dict[str, Any]],
    actividades: List[Dict[str, Any]],
    confirmadas: List[Dict[str, Any]],
    prohibiciones_horarias: Optional[Set[Tuple[int, int, int]]] = None,
    planes_excluidos: Optional[List[List[Dict[str, Any]]]] = None,
    max_profesores: Optional[int] = MAX_PROFESORES_PROPUESTA,
) -> Dict[str, Any]:
    """Busca el menor intercambio que permite completar el área.

    El modelo conserva todas las cuotas de profesores y actividades, comprueba
    disponibilidad por cuatrimestre y los solapes conocidos. La función se
    limita al área indicada, incluso cuando existen perfiles multiarea.
    """
    profesores_area = [
        profesor for profesor in profesores
        if area_id in _areas_profesor(profesor) and _objetivo_area(profesor, area_id) > 0.01
    ]
    actividades_area = [actividad for actividad in actividades if actividad.get("area_id") == area_id]
    profesor_bloqueado = next((profesor for profesor in profesores_area if profesor["id"] == profesor_bloqueado_id), None)
    if profesor_bloqueado is None:
        return {"viable": False, "motivo": "El profesor no tiene carga docente en el área seleccionada."}
    if not actividades_area:
        return {"viable": False, "motivo": "El área no tiene actividades que se puedan reorganizar."}

    ids_actividades = {actividad["id"] for actividad in actividades_area}
    por_nombre = {_nombre(profesor): profesor["id"] for profesor in profesores_area}
    actuales: Dict[tuple[int, int], int] = {}
    for eleccion in confirmadas:
        actividad_id = eleccion.get("actividad_id")
        profesor_id = eleccion.get("profesor_id") or por_nombre.get(eleccion.get("profesor"))
        if actividad_id not in ids_actividades or profesor_id not in {profesor["id"] for profesor in profesores_area}:
            continue
        clave = (int(profesor_id), int(actividad_id))
        actuales[clave] = actuales.get(clave, 0) + _esc(float(eleccion.get("horas", 0)))

    carga_bloqueado = sum(actuales.get((profesor_bloqueado_id, actividad["id"]), 0) for actividad in actividades_area)
    objetivo_bloqueado = _esc(_objetivo_area(profesor_bloqueado, area_id))
    if carga_bloqueado >= objetivo_bloqueado:
        return {"viable": False, "motivo": "El profesor indicado ya tiene cubierta su carga del área."}

    demanda = sum(_esc(float(actividad["horas_totales"])) for actividad in actividades_area)
    capacidad = sum(_esc(_objetivo_area(profesor, area_id)) for profesor in profesores_area)
    if demanda != capacidad:
        return {
            "viable": False,
            "motivo": "No se puede generar un intercambio porque la carga del profesorado y las actividades del área no está equilibrada.",
        }

    solver = pywraplp.Solver.CreateSolver("SCIP")
    if not solver:
        return {"viable": False, "motivo": "No se pudo iniciar el solver de conflictos."}
    solver.SetTimeLimit(min(settings.SOLVER_MAX_TIME_MS, 3000))

    x: Dict[tuple[int, int], Any] = {}
    y: Dict[tuple[int, int], Any] = {}
    delta: Dict[tuple[int, int], Any] = {}
    ganancia: Dict[tuple[int, int], Any] = {}
    cambio_profesor: Dict[int, Any] = {}
    for profesor in profesores_area:
        cambio_profesor[profesor["id"]] = solver.IntVar(0, 1, f"conf_cambio_{profesor['id']}")
        for actividad in actividades_area:
            clave = (profesor["id"], actividad["id"])
            maximo = _esc(float(actividad["horas_totales"])) if _puede_cubrir(profesor, actividad) else 0
            x[clave] = solver.IntVar(0, maximo, f"conf_x_{profesor['id']}_{actividad['id']}")
            y[clave] = solver.IntVar(0, 1 if maximo else 0, f"conf_y_{profesor['id']}_{actividad['id']}")
            delta[clave] = solver.IntVar(0, _esc(float(actividad["horas_totales"])), f"conf_d_{profesor['id']}_{actividad['id']}")
            actual = actuales.get(clave, 0)
            solver.Add(delta[clave] >= x[clave] - actual)
            solver.Add(delta[clave] >= actual - x[clave])
            solver.Add(x[clave] <= maximo * y[clave])
            solver.Add(x[clave] >= y[clave])
            # Solo cuenta como preferencia aquello que el profesor recibe por
            # encima de su reparto actual. De este modo no penaliza conservar
            # una adjudicación ya aprobada.
            ganancia[clave] = solver.IntVar(0, maximo, f"conf_g_{profesor['id']}_{actividad['id']}")
            solver.Add(ganancia[clave] >= x[clave] - actual)

    for profesor in profesores_area:
        solver.Add(sum(x[(profesor["id"], actividad["id"])] for actividad in actividades_area) == _esc(_objetivo_area(profesor, area_id)))
    for actividad in actividades_area:
        solver.Add(sum(x[(profesor["id"], actividad["id"])] for profesor in profesores_area) == _esc(float(actividad["horas_totales"])))

    # La propuesta se valida después con los mismos horarios que se muestran
    # al docente, incluidos los provisionales. Incorporarlos ya en el modelo
    # evita calcular una reparación que sería imposible de aprobar.
    for primera, segunda in construir_incompatibilidades(
        actividades_area, considerar_horarios_sinteticos=True,
    ):
        for profesor in profesores_area:
            solver.Add(y[(profesor["id"], primera)] + y[(profesor["id"], segunda)] <= 1)

    # Las sesiones oficiales repartidas parcialmente pueden revelar un
    # solape que no es deducible solo de la franja semanal de cada actividad.
    # El servicio reintenta el modelo con estas prohibiciones concretas hasta
    # obtener un calendario aplicable, sin restringir a los demás docentes.
    for profesor_id, primera, segunda in prohibiciones_horarias or set():
        if primera == segunda:
            continue
        clave_primera = (profesor_id, primera)
        clave_segunda = (profesor_id, segunda)
        if clave_primera in y and clave_segunda in y:
            solver.Add(y[clave_primera] + y[clave_segunda] <= 1)

    # Evita que una propuesta aparentemente válida no haga nada para quien
    # está bloqueado. Al menos una décima de hora debe cambiar en su reparto.
    solver.Add(sum(delta[(profesor_bloqueado_id, actividad["id"])] for actividad in actividades_area) >= 1)
    # Un docente queda afectado si cualquiera de sus cantidades cambia. Se
    # limita explícitamente el tamaño de la propuesta antes de optimizarla.
    for profesor in profesores_area:
        profesor_id = profesor["id"]
        solver.Add(
            sum(delta[(profesor_id, actividad["id"])] for actividad in actividades_area)
            <= 2 * demanda * cambio_profesor[profesor_id]
        )
    limite_profesores = max_profesores if max_profesores is not None else len(profesores_area)
    solver.Add(sum(cambio_profesor.values()) <= limite_profesores)

    # No-good cuts sobre cantidades enteras: cada plan nuevo debe diferir
    # al menos una décima de todos los mostrados, incluidos los rechazados.
    for indice, plan_anterior in enumerate(planes_excluidos or []):
        anterior = {(int(f['profesor_id']), int(f['actividad_id'])): _esc(float(f['horas'])) for f in plan_anterior}
        diferencias = []
        for clave, variable in x.items():
            if variable.ub() == 0:
                continue
            valor = anterior.get(clave, 0)
            margen = max(int(variable.ub()), valor) + 1
            menos = solver.BoolVar(f'excluir_{indice}_{clave[0]}_{clave[1]}_menos')
            mas = solver.BoolVar(f'excluir_{indice}_{clave[0]}_{clave[1]}_mas')
            solver.Add(variable <= valor - 1 + margen * (1 - menos))
            solver.Add(variable >= valor + 1 - margen * (1 - mas))
            diferencias.extend([menos, mas])
        solver.Add(solver.Sum(diferencias) >= 1)

    # Optimización lexicográfica: el número de profesores es el criterio
    # principal; nunca se sacrifica por ahorrar unas décimas de hora.
    estado, minimo_afectados = _resolver_minimo(solver, {variable: 1 for variable in cambio_profesor.values()})
    if estado not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return {
            "viable": False,
            "motivo": (
                f"No quedan reparaciones distintas de las ya mostradas con un máximo de {limite_profesores} profesores "
                "que cumpla simultáneamente cargas, disponibilidad y horarios."
            ) if estado == pywraplp.Solver.INFEASIBLE else 'No se ha encontrado una reparación dentro del límite de cálculo. No se ha demostrado que sea imposible.',
        }
    minimo_demostrado = estado == pywraplp.Solver.OPTIMAL
    solver.Add(sum(cambio_profesor.values()) == minimo_afectados)

    estado, minimo_delta = _resolver_minimo(solver, {variable: 1 for variable in delta.values()})
    if estado not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return {"viable": False, "motivo": "No se pudo concretar el intercambio mínimo del área."}
    solver.Add(sum(delta.values()) == minimo_delta)

    # Entre reparaciones equivalentes, se prefieren las asignaturas declaradas
    # por cada docente. Las no incluidas quedan después de toda su lista.
    coste_preferencias: Dict[Any, int] = {}
    prioridad_no_declarada = len({actividad.get("codigo") for actividad in actividades_area}) + 1
    for profesor in profesores_area:
        prioridades = profesor.get("prioridades_asignaturas") or {}
        prioridad_no_declarada = max([prioridad_no_declarada] + [int(v)+1 for v in prioridades.values()])
        for actividad in actividades_area:
            clave = (profesor["id"], actividad["id"])
            try:
                prioridad = int(prioridades.get(str(actividad.get("codigo")), prioridad_no_declarada))
            except (TypeError, ValueError):
                prioridad = prioridad_no_declarada
            coste_preferencias[ganancia[clave]] = max(1, prioridad)
    estado, _ = _resolver_minimo(solver, coste_preferencias)
    if estado not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return {"viable": False, "motivo": "No se pudo aplicar las prioridades docentes a la propuesta."}

    propuesta: Dict[tuple[int, int], int] = {
        clave: int(variable.solution_value()) for clave, variable in x.items()
    }
    movimientos = _movimientos(actuales, propuesta, profesores_area, actividades_area)
    afectados_ids = sorted({
        profesor_id
        for movimiento in movimientos
        for profesor_id in (movimiento["desde_profesor_id"], movimiento["hacia_profesor_id"])
    })
    por_id = {profesor["id"]: profesor for profesor in profesores_area}
    plan = [
        {
            "profesor_id": profesor["id"],
            "actividad_id": actividad["id"],
            "horas": _desc(propuesta[(profesor["id"], actividad["id"])]),
        }
        for profesor in profesores_area
        for actividad in actividades_area
        if propuesta[(profesor["id"], actividad["id"])] > 0
    ]
    return {
        "viable": True,
        "plan": plan,
        "movimientos": movimientos,
        "afectados": [
            {"profesor_id": profesor_id, "profesor": _nombre(por_id[profesor_id])}
            for profesor_id in afectados_ids
        ],
        "impacto": {
            "profesores_afectados": len(afectados_ids),
            "movimientos": len(movimientos),
            "horas_reasignadas": round(sum(movimiento["horas"] for movimiento in movimientos), 1),
            "limite_profesores": limite_profesores,
            "minimo_profesores_demostrado": minimo_demostrado,
            "criterio": "Mínimo número de profesores, mínimo movimiento y prioridades docentes." if minimo_demostrado else "Mejor propuesta encontrada dentro del tiempo disponible; mínimo de profesores no demostrado.",
        },
    }
