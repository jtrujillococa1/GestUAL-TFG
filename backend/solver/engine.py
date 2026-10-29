from ortools.linear_solver import pywraplp
from solver.cache import solver_cache
from solver.compatibilidad import construir_incompatibilidades
from typing import List, Dict, Optional
from core.config import settings
from domain.ordenacion.disponibilidad import (
    cuatrimestres_actividad,
    motivo_no_disponibilidad,
    normalizar_disponibilidad,
    profesor_disponible_para_actividad,
)
from domain.ordenacion.reparto_heuristico import construir_reparto_heuristico


ESCALA = settings.ESCALA_SOLVER  # 0.1h = 1 unidad interna


def _esc(horas: float) -> int:
    return round(float(horas) * ESCALA)


def _desc(entero: int) -> float:
    return entero / ESCALA


def _clave_actividad(item: Dict):
    if item.get("actividad_id") is not None:
        return ("id", item["actividad_id"])
    return (
        item["codigo"],
        item["codigo_grupo"],
        item.get("tipo") or item.get("tipo_actividad"),
    )


def _areas_profesor(profesor: Dict) -> set[int]:
    """Áreas en las que el profesor puede cubrir una cuota docente."""
    areas = profesor.get("area_ids")
    if areas is not None:
        return set(areas)
    return {profesor["area_id"]} if profesor.get("area_id") is not None else set()


def _profesor_puede_cubrir(profesor: Dict, actividad: Dict) -> bool:
    area_actividad = actividad.get("area_id")
    areas_profesor = _areas_profesor(profesor)
    area_compatible = (
        area_actividad is None
        or not areas_profesor
        or area_actividad in areas_profesor
    )
    return area_compatible and profesor_disponible_para_actividad(profesor, actividad)


def _resultado_actividad_no_encontrada(eleccion: Dict) -> Dict:
    return {
        "viable": False,
        "error": (
            f"Actividad no encontrada: "
            f"{eleccion.get('codigo')} {eleccion.get('codigo_grupo')} "
            f"({eleccion.get('tipo') or eleccion.get('tipo_actividad')})"
        ),
        "cached": False,
    }


def _prevalidar_reservas_por_cuatrimestre(
    elecciones: List[Dict], profesores: List[Dict], actividades: List[Dict],
) -> Dict | None:
    """Descarta antes del MILP una reserva temporal imposible.

    Una persona disponible únicamente en un cuatrimestre no puede compensar
    su carga con actividades anuales ni del otro periodo. Si la carga restante
    de ese colectivo supera las horas pendientes del propio cuatrimestre, no
    hace falta iniciar una búsqueda combinatoria para saber que no hay salida.
    """
    actividades_por_id = {actividad.get("id"): actividad for actividad in actividades}
    actividades_por_clave = {
        (actividad["codigo"], actividad["codigo_grupo"], actividad["tipo"]): actividad
        for actividad in actividades
    }
    profesores_por_nombre = {
        f"{profesor['apellidos']}, {profesor['nombre']}": profesor
        for profesor in profesores
    }
    demanda = {"C1": 0.0, "C2": 0.0}
    for actividad in actividades:
        periodos = cuatrimestres_actividad(actividad)
        if len(periodos) == 1:
            demanda[next(iter(periodos))] += float(actividad["horas_totales"])

    capacidad_restante = {
        profesor["id"]: float(profesor["horas_objetivo"])
        for profesor in profesores
    }
    for eleccion in elecciones:
        profesor = profesores_por_nombre.get(eleccion.get("profesor"))
        actividad = actividades_por_id.get(eleccion.get("actividad_id"))
        if actividad is None:
            actividad = actividades_por_clave.get(_clave_actividad(eleccion))
        if profesor is None or actividad is None:
            continue
        horas = float(eleccion.get("horas", 0))
        capacidad_restante[profesor["id"]] = capacidad_restante.get(profesor["id"], 0.0) - horas
        periodos = cuatrimestres_actividad(actividad)
        if len(periodos) == 1:
            periodo = next(iter(periodos))
            demanda[periodo] -= horas

    diagnostico = []
    for periodo, disponibilidad in (("C1", "PRIMERO"), ("C2", "SEGUNDO")):
        reserva = sum(
            max(0.0, capacidad_restante.get(profesor["id"], 0.0))
            for profesor in profesores
            if normalizar_disponibilidad(profesor.get("disponibilidad_cuatrimestre")) == disponibilidad
        )
        pendiente = max(0.0, demanda[periodo])
        if reserva > pendiente + 0.01:
            etiqueta = "primer" if periodo == "C1" else "segundo"
            diagnostico.append(
                f"La carga reservada para el {etiqueta} cuatrimestre ({reserva:g} h) "
                f"supera las actividades pendientes de ese periodo ({pendiente:g} h)."
            )
    if not diagnostico:
        return None
    return {
        "viable": False,
        "cached": False,
        "error": "Las restricciones de disponibilidad por cuatrimestre no admiten una ordenación completa.",
        "diagnostico": diagnostico,
    }


def _diagnosticar_inviabilidad(
    elecciones: List[Dict], profesores: List[Dict], actividades: List[Dict],
) -> List[str]:
    """Ofrece causas accionables cuando el modelo no encuentra solución.

    No intenta explicar todos los certificados internos de SCIP; identifica las
    restricciones de negocio que más habitualmente bloquean una ordenación:
    cuota, área, carga y horario confirmado.
    """
    profesores_por_nombre = {
        f"{profesor['apellidos']}, {profesor['nombre']}": profesor
        for profesor in profesores
    }
    actividades_por_id = {actividad.get("id"): actividad for actividad in actividades}
    actividades_por_clave: Dict[tuple, Dict | None] = {}
    for actividad in actividades:
        clave = (actividad["codigo"], actividad["codigo_grupo"], actividad["tipo"])
        actividades_por_clave[clave] = None if clave in actividades_por_clave else actividad

    diagnostico: List[str] = []
    horas_profesor: Dict[str, float] = {}
    horas_actividad: Dict[int, float] = {}
    actividades_profesor: Dict[str, List[Dict]] = {}
    for eleccion in elecciones:
        profesor = profesores_por_nombre.get(eleccion.get("profesor"))
        actividad = actividades_por_id.get(eleccion.get("actividad_id"))
        if actividad is None:
            actividad = actividades_por_clave.get(_clave_actividad(eleccion))
        if profesor is None or actividad is None:
            continue
        nombre = eleccion["profesor"]
        horas = float(eleccion.get("horas", 0))
        horas_profesor[nombre] = horas_profesor.get(nombre, 0.0) + horas
        horas_actividad[actividad["id"]] = horas_actividad.get(actividad["id"], 0.0) + horas
        actividades_profesor.setdefault(nombre, []).append(actividad)
        if not _profesor_puede_cubrir(profesor, actividad):
            area_actividad = actividad.get("area_id")
            if area_actividad is not None and _areas_profesor(profesor) and area_actividad not in _areas_profesor(profesor):
                diagnostico.append(
                    f"{nombre} no pertenece al área que cubre {actividad.get('nombre_asignatura') or actividad['codigo']}."
                )
            else:
                diagnostico.append(motivo_no_disponibilidad(profesor, actividad))

    for profesor in profesores:
        nombre = f"{profesor['apellidos']}, {profesor['nombre']}"
        if horas_profesor.get(nombre, 0.0) > float(profesor["horas_objetivo"]) + 0.01:
            diagnostico.append(f"{nombre} supera su carga docente disponible.")

    for actividad in actividades:
        asignadas = horas_actividad.get(actividad["id"], 0.0)
        if asignadas > float(actividad["horas_totales"]) + 0.01:
            diagnostico.append(
                f"La cuota de {actividad.get('nombre_asignatura') or actividad['codigo']} excede sus horas disponibles."
            )

    incompatibles = construir_incompatibilidades(actividades)
    incompatibles_set = {frozenset(par) for par in incompatibles}
    for nombre, actividades_asignadas in actividades_profesor.items():
        for indice, primera in enumerate(actividades_asignadas):
            for segunda in actividades_asignadas[indice + 1:]:
                if frozenset((primera["id"], segunda["id"])) in incompatibles_set:
                    diagnostico.append(
                        f"{nombre} tiene un solape horario confirmado entre "
                        f"{primera.get('nombre_asignatura') or primera['codigo']} y "
                        f"{segunda.get('nombre_asignatura') or segunda['codigo']}."
                    )

    for area_id in {actividad.get("area_id") for actividad in actividades if actividad.get("area_id") is not None}:
        demanda = sum(float(actividad["horas_totales"]) for actividad in actividades if actividad.get("area_id") == area_id)
        capacidad = sum(
            float((profesor.get("horas_objetivo_por_area") or {}).get(
                area_id,
                (profesor.get("horas_objetivo_por_area") or {}).get(str(area_id), 0),
            ))
            for profesor in profesores
        )
        if capacidad and capacidad + 0.01 < demanda:
            diagnostico.append(f"El área {area_id} tiene menos carga docente ({capacidad:g} h) que cuota de actividades ({demanda:g} h).")

    if not diagnostico:
        diagnostico.append("Las cuotas, áreas y horarios confirmados no admiten una continuación completa con las elecciones actuales.")
    return list(dict.fromkeys(diagnostico))[:5]


def _con_diagnostico(resultado: Dict, elecciones: List[Dict], profesores: List[Dict], actividades: List[Dict]) -> Dict:
    if resultado.get("viable", False):
        return resultado
    resultado.setdefault("diagnostico", _diagnosticar_inviabilidad(elecciones, profesores, actividades))
    return resultado


def _resolver_transporte_sin_solapes(
    elecciones_forzadas: List[Dict], profesores: List[Dict], actividades: List[Dict],
) -> Dict:
    """Resuelve por flujo el caso sin incompatibilidades horarias confirmadas.

    Sin solapes, el reparto es un problema de transporte: las cuotas de las
    actividades son demanda y las cargas de profesores, capacidad. Evitamos
    introducir miles de binarias que no aportan ninguna restricción en ese
    caso, habitual mientras los horarios sean sintéticos y provisionales.
    """
    prof_por_nombre = {
        f"{profesor['apellidos']}, {profesor['nombre']}": profesor
        for profesor in profesores
    }
    actividad_por_clave = {("id", actividad["id"]): actividad for actividad in actividades}
    for actividad in actividades:
        clave_legacy = (actividad["codigo"], actividad["codigo_grupo"], actividad["tipo"])
        actividad_por_clave[clave_legacy] = (
            None if clave_legacy in actividad_por_clave else actividad
        )

    capacidad = {profesor["id"]: _esc(profesor["horas_objetivo"]) for profesor in profesores}
    demanda = {actividad["id"]: _esc(actividad["horas_totales"]) for actividad in actividades}
    asignaciones: Dict[tuple[int, int], int] = {}

    for eleccion in elecciones_forzadas:
        profesor = prof_por_nombre.get(eleccion.get("profesor"))
        if profesor is None:
            return {
                "viable": False,
                "error": f"Profesor no encontrado: {eleccion.get('profesor')}",
                "cached": False,
            }
        actividad = actividad_por_clave.get(_clave_actividad(eleccion))
        if actividad is None:
            return _resultado_actividad_no_encontrada(eleccion)
        if not _profesor_puede_cubrir(profesor, actividad):
            return {"viable": False, "cached": False}
        horas = _esc(float(eleccion["horas"]))
        clave = (profesor["id"], actividad["id"])
        if horas < 0 or clave in asignaciones:
            return {"viable": False, "cached": False}
        asignaciones[clave] = horas

    for (profesor_id, actividad_id), horas in asignaciones.items():
        capacidad[profesor_id] -= horas
        demanda[actividad_id] -= horas
        if capacidad[profesor_id] < 0 or demanda[actividad_id] < 0:
            return {"viable": False, "cached": False}

    # La asignación codiciosa es completa porque dentro de cada área todos los
    # profesores compatibles forman un grafo bipartito completo. Primero llena
    # las actividades grandes para producir también un reparto legible.
    for actividad in sorted(actividades, key=lambda item: (-demanda[item["id"]], item["id"])):
        actividad_id = actividad["id"]
        pendiente = demanda[actividad_id]
        if not pendiente:
            continue
        for profesor in profesores:
            if not _profesor_puede_cubrir(profesor, actividad):
                continue
            disponible = capacidad[profesor["id"]]
            if disponible <= 0:
                continue
            horas = min(disponible, pendiente)
            asignaciones[(profesor["id"], actividad_id)] = horas
            capacidad[profesor["id"]] -= horas
            pendiente -= horas
            if not pendiente:
                break
        demanda[actividad_id] = pendiente
        if pendiente:
            return {"viable": False, "cached": False}

    reparto = []
    total_repartos = 0
    actividades_divididas = 0
    for actividad in actividades:
        asignada_a = [
            (profesor, asignaciones.get((profesor["id"], actividad["id"]), 0))
            for profesor in profesores
        ]
        if sum(horas > 0 for _, horas in asignada_a) > 1:
            actividades_divididas += 1

    for profesor in profesores:
        actividades_prof = []
        for actividad in actividades:
            unidades = asignaciones.get((profesor["id"], actividad["id"]), 0)
            if unidades <= 0:
                continue
            actividades_prof.append({
                "actividad_id": actividad["id"],
                "codigo": actividad["codigo"],
                "tipo": actividad["tipo"],
                "tipo_actividad": actividad["tipo"],
                "codigo_grupo": actividad["codigo_grupo"],
                "grupo": actividad["grupo"],
                "idioma": actividad.get("idioma"),
                "duracion": actividad.get("duracion"),
                "turno": actividad.get("turno"),
                "horas": _desc(unidades),
            })
            total_repartos += 1
        reparto.append({
            "profesor": profesor["nombre"],
            "horas_totales": round(sum(item["horas"] for item in actividades_prof), 1),
            "actividades": actividades_prof,
        })

    return {
        "viable": True,
        "reparto": reparto,
        "total_repartos": total_repartos,
        "actividades_divididas": actividades_divididas,
        "cached": False,
    }


def _resolver_por_areas(
    elecciones_forzadas: List[Dict], profesores: List[Dict], actividades: List[Dict],
) -> Dict:
    """Resuelve cada área por separado cuando todos los datos están acotados.

    Un profesor no puede cubrir actividades de otra área, por lo que los
    modelos no comparten variables ni restricciones. Dividirlos conserva la
    solución exacta y evita que un escenario real convierta cada consulta de
    opciones en un problema monolítico de decenas de miles de variables.
    """
    prof_por_nombre = {f"{p['apellidos']}, {p['nombre']}": p for p in profesores}
    area_por_id = {actividad["id"]: actividad["area_id"] for actividad in actividades}
    area_por_clave_legacy: Dict[tuple, int | None] = {}
    for actividad in actividades:
        clave = (actividad["codigo"], actividad["codigo_grupo"], actividad["tipo"])
        area_por_clave_legacy[clave] = (
            None if clave in area_por_clave_legacy else actividad["area_id"]
        )

    elecciones_por_area: Dict[int, List[Dict]] = {}
    for eleccion in elecciones_forzadas:
        if eleccion.get("profesor") not in prof_por_nombre:
            return {
                "viable": False,
                "error": f"Profesor no encontrado: {eleccion['profesor']}",
                "cached": False,
            }
        if eleccion.get("actividad_id") is not None:
            area_id = area_por_id.get(eleccion["actividad_id"])
        else:
            area_id = area_por_clave_legacy.get(_clave_actividad(eleccion))
        if area_id is None:
            return _resultado_actividad_no_encontrada(eleccion)
        elecciones_por_area.setdefault(area_id, []).append(eleccion)

    reparto_por_profesor_id: Dict[int, Dict] = {}
    total_repartos = 0
    actividades_divididas = 0
    areas = sorted({actividad["area_id"] for actividad in actividades})
    for area_id in areas:
        profesores_area = [profesor for profesor in profesores if area_id in _areas_profesor(profesor)]
        actividades_area = [actividad for actividad in actividades if actividad["area_id"] == area_id]
        resultado_area = resolver_reparto(
            elecciones_por_area.get(area_id, []), profesores_area, actividades_area, usar_cache=False,
        )
        if not resultado_area["viable"]:
            return {"viable": False, "cached": False, **({"error": resultado_area["error"]} if resultado_area.get("error") else {})}
        total_repartos += resultado_area["total_repartos"]
        actividades_divididas += resultado_area.get("actividades_divididas", 0)
        reparto_por_profesor_id.update({
            profesor["id"]: fila
            for profesor, fila in zip(profesores_area, resultado_area["reparto"])
        })

    return {
        "viable": True,
        "reparto": [
            reparto_por_profesor_id.get(
                profesor["id"],
                {"profesor": profesor["nombre"], "horas_totales": 0.0, "actividades": []},
            )
            for profesor in profesores
        ],
        "total_repartos": total_repartos,
        "actividades_divididas": actividades_divididas,
        "cached": False,
    }


def _puede_aislar_area(profesores_area: List[Dict], area_id: int) -> bool:
    """Indica si la cola de un área no comparte carga con otra.

    Solo importan los perfiles que participan en el área solicitada. Un perfil
    multárea de otro departamento no debe forzar que esta cola use el modelo
    global ni hacer que la pantalla de opciones escale con todo el catálogo.
    """
    return all(_areas_profesor(profesor) == {area_id} for profesor in profesores_area)


def resolver_reparto_en_area(
    elecciones_forzadas: List[Dict], profesores: List[Dict], actividades: List[Dict],
    area_id: int, usar_cache: bool = True, preferir_heuristico: bool = False,
    solo_factibilidad: bool = False, tiempo_limite_ms: Optional[int] = None,
) -> Dict:
    """Resuelve una alternativa local sin recalcular áreas independientes.

    Es una optimización segura de la pantalla de opciones. Si se detecta una
    dependencia multiarea, delega inmediatamente en el solver global.
    """
    actividades_area = [actividad for actividad in actividades if actividad["area_id"] == area_id]
    profesores_area = [profesor for profesor in profesores if area_id in _areas_profesor(profesor)]
    if not _puede_aislar_area(profesores_area, area_id):
        # Los perfiles que comparten carga entre áreas requieren conservar las
        # restricciones cruzadas del modelo completo. La heurística rápida se
        # reserva para las colas realmente independientes.
        return resolver_reparto(
            elecciones_forzadas, profesores, actividades, usar_cache=usar_cache,
            solo_factibilidad=solo_factibilidad, tiempo_limite_ms=tiempo_limite_ms,
        )

    actividades_por_id = {actividad["id"]: actividad for actividad in actividades}
    actividades_por_clave = {
        (actividad["codigo"], actividad["codigo_grupo"], actividad["tipo"]): actividad
        for actividad in actividades
    }
    elecciones_area = []
    for eleccion in elecciones_forzadas:
        actividad = actividades_por_id.get(eleccion.get("actividad_id"))
        if actividad is None:
            actividad = actividades_por_clave.get(_clave_actividad(eleccion))
        if actividad and actividad.get("area_id") == area_id:
            elecciones_area.append(eleccion)

    return resolver_reparto(
        elecciones_area,
        profesores_area,
        actividades_area,
        usar_cache=usar_cache,
        preferir_heuristico=preferir_heuristico,
        solo_factibilidad=solo_factibilidad,
        tiempo_limite_ms=tiempo_limite_ms,
    )


def resolver_reparto(
    elecciones_forzadas: List[Dict],
    profesores: List[Dict],
    actividades: List[Dict],
    usar_cache: bool = True,
    preferir_heuristico: bool = False,
    solo_factibilidad: bool = False,
    tiempo_limite_ms: Optional[int] = None,
) -> Dict:
    # Una consulta de factibilidad no optimiza el reparto; no debe reutilizar
    # ni sobrescribir las soluciones optimizadas de otros flujos.
    cachear = usar_cache and not solo_factibilidad
    if cachear:
        cached = solver_cache.get(elecciones_forzadas, profesores, actividades)
        if cached is not None:
            return cached

    prevalidacion = _prevalidar_reservas_por_cuatrimestre(
        elecciones_forzadas, profesores, actividades,
    )
    if prevalidacion is not None:
        if cachear:
            solver_cache.set(elecciones_forzadas, profesores, actividades, prevalidacion)
        return prevalidacion

    incompatibles = construir_incompatibilidades(actividades)

    # La pantalla de opciones necesita comprobar decenas o cientos de
    # alternativas. En una cola aislada, una distribución construida por la
    # heurística es ya una prueba completa de viabilidad: respeta exactamente
    # cuotas, cargas, disponibilidad y todos los solapes. Probarla antes del
    # optimizador evita crear un MILP enorme por cada tarjeta visible. Si no
    # encuentra reparto, se conserva el camino exacto de SCIP; nunca se marca
    # una opción como inviable solo porque el atajo no haya dado resultado.
    es_escenario_aislado = (
        bool(actividades)
        and all(len(_areas_profesor(profesor)) <= 1 for profesor in profesores)
        and all(actividad.get("area_id") is not None for actividad in actividades)
    )
    if preferir_heuristico and es_escenario_aislado:
        heuristico = construir_reparto_heuristico(
            elecciones_forzadas, profesores, actividades, incompatibles, ESCALA,
        )
        if heuristico.get("viable"):
            # No se almacena como respuesta del caché global: otros flujos
            # pueden pedir después el reparto optimizado para informes, pero
            # la decisión de viabilidad ya es exacta y segura.
            return heuristico

    if not incompatibles and all(len(_areas_profesor(profesor)) <= 1 for profesor in profesores):
        resultado = _resolver_transporte_sin_solapes(elecciones_forzadas, profesores, actividades)
        resultado = _con_diagnostico(resultado, elecciones_forzadas, profesores, actividades)
        if cachear:
            solver_cache.set(elecciones_forzadas, profesores, actividades, resultado)
        return resultado

    # El modelo se puede descomponer únicamente si no existe ningún profesor
    # ni actividad sin área. Los datos heredados sin este campo siguen usando
    # el modelo único para mantener compatibilidad.
    areas_actividades = {actividad.get("area_id") for actividad in actividades}
    if (
        all(len(_areas_profesor(profesor)) == 1 for profesor in profesores)
        and None not in areas_actividades
        and len(areas_actividades) > 1
    ):
        resultado = _resolver_por_areas(elecciones_forzadas, profesores, actividades)
        resultado = _con_diagnostico(resultado, elecciones_forzadas, profesores, actividades)
        if cachear:
            solver_cache.set(elecciones_forzadas, profesores, actividades, resultado)
        return resultado

    solver = pywraplp.Solver.CreateSolver("SCIP")

    if not solver:
        return {
            "viable": False,
            "error": "No se pudo crear el solver.",
            "cached": False,
        }

    # En áreas reales hay miles de combinaciones posibles. Una solución
    # ``FEASIBLE`` es igual de válida que una óptima para confirmar o valorar
    # una opción: ambas respetan todas las cuotas, disponibilidad y solapes.
    # El límite solo detiene la mejora estética de la solución (menos cortes),
    # no permite ninguna asignación incompleta o incompatible.
    solver.SetTimeLimit(tiempo_limite_ms or settings.SOLVER_MAX_TIME_MS)

    # Construir lookups antes de procesar elecciones forzadas
    prof_por_nombre = {
        f"{p['apellidos']}, {p['nombre']}": p["id"]
        for p in profesores
    }

    actividad_por_clave = {("id", a["id"]): a["id"] for a in actividades}
    # La clave textual se mantiene para borradores antiguos y pruebas. Si es
    # ambigua entre áreas, no se acepta: el cliente debe usar actividad_id.
    for a in actividades:
        clave_legacy = (a["codigo"], a["codigo_grupo"], a["tipo"])
        actividad_por_clave[clave_legacy] = (
            None if clave_legacy in actividad_por_clave else a["id"]
        )

    # Validar elecciones forzadas antes de construir el modelo
    for e in elecciones_forzadas:
        if prof_por_nombre.get(e["profesor"]) is None:
            return {
                "viable": False,
                "error": f"Profesor no encontrado: {e['profesor']}",
                "cached": False,
            }
        if actividad_por_clave.get(_clave_actividad(e)) is None:
            return _resultado_actividad_no_encontrada(e)

    h_prof = {
        p["id"]: _esc(p["horas_objetivo"])
        for p in profesores
    }

    h_actividad = {
        a["id"]: _esc(a["horas_totales"])
        for a in actividades
    }

    # Calcular horas ya forzadas por profesor (confirmadas + borrador)
    h_forzadas: Dict[int, int] = {}
    for e in elecciones_forzadas:
        pid = prof_por_nombre[e["profesor"]]
        h_forzadas[pid] = h_forzadas.get(pid, 0) + _esc(float(e["horas"]))

    x = {}
    y = {}

    for p in profesores:
        for a in actividades:
            k = (p["id"], a["id"])
            areas_incompatibles = not _profesor_puede_cubrir(p, a)

            x[k] = solver.IntVar(
                0,
                0 if areas_incompatibles else h_actividad[a["id"]],
                f"x_{p['id']}_{a['id']}",
            )

            y[k] = solver.IntVar(
                0,
                0 if areas_incompatibles else 1,
                f"y_{p['id']}_{a['id']}",
            )

    # Constraint de carga docente por profesor.
    # Profesores que ya han completado su carga (h_forzadas >= h_prof): exacto.
    # Profesores en proceso: hasta su carga máxima (flexible).
    # Esto permite que el solver sea viable aunque el total de horas de
    # profesores no cuadre exactamente con el total de actividades.
    for p in profesores:
        pid = p["id"]
        total_x = sum(x[(pid, a["id"])] for a in actividades)
        h = h_prof[pid]
        h_ya = h_forzadas.get(pid, 0)

        if h_ya >= h:
            # Profesor con turno completo: fijar exactamente
            solver.Add(total_x == h)
        else:
            # Profesor aún en proceso: no superar su carga
            solver.Add(total_x <= h)
            if h_ya > 0:
                solver.Add(total_x >= h_ya)

    # Cada actividad debe quedar completamente cubierta.
    for a in actividades:
        solver.Add(
            sum(x[(p["id"], a["id"])] for p in profesores)
            == h_actividad[a["id"]]
        )

    # Un profesor multiarea no duplica su carga: cada área tiene una fracción
    # explícita de su objetivo. Sin este límite una cola podría consumir horas
    # reservadas para otra área aunque sus turnos sean simultáneos.
    for p in profesores:
        cargas_area = p.get("horas_objetivo_por_area") or {}
        for area_id_raw, horas_objetivo in cargas_area.items():
            area_id = int(area_id_raw)
            solver.Add(
                sum(
                    x[(p["id"], a["id"])]
                    for a in actividades
                    if a.get("area_id") == area_id
                ) == _esc(float(horas_objetivo))
            )

    # Enlace entre variable de horas x y variable binaria y.
    for p in profesores:
        for a in actividades:
            k = (p["id"], a["id"])

            solver.Add(x[k] <= h_actividad[a["id"]] * y[k])
            solver.Add(x[k] >= y[k])  # mínimo 0.1h si se asigna

    # Incompatibilidades horarias.
    for p in profesores:
        for a1, a2 in incompatibles:
            solver.Add(y[(p["id"], a1)] + y[(p["id"], a2)] <= 1)

    # Elecciones forzadas.
    for e in elecciones_forzadas:
        pid = prof_por_nombre[e["profesor"]]
        aid = actividad_por_clave[_clave_actividad(e)]
        solver.Add(x[(pid, aid)] == _esc(float(e["horas"])))

    # Penalizar dividir actividades entre varios profesores.
    split = {}
    max_profes_por_actividad = len(profesores)

    for a in actividades:
        aid = a["id"]

        split[aid] = solver.IntVar(0, 1, f"split_{aid}")

        suma_y = sum(y[(p["id"], aid)] for p in profesores)

        solver.Add(
            suma_y
            <= 1 + (max_profes_por_actividad - 1) * split[aid]
        )

    PESO_SPLIT = len(profesores) * len(actividades) + 1

    if not solo_factibilidad:
        solver.Minimize(
            PESO_SPLIT * sum(split[a["id"]] for a in actividades)
            + sum(
                y[(p["id"], a["id"])]
                for p in profesores
                for a in actividades
            )
        )

    estado = solver.Solve()

    if estado not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        # En modelos muy grandes SCIP puede agotar el límite mientras mejora
        # una solución. El respaldo no relaja restricciones: solo acepta una
        # distribución si cuadra cada carga, cuota y par incompatible.
        respaldo = construir_reparto_heuristico(
            elecciones_forzadas, profesores, actividades, incompatibles, ESCALA,
        )
        if respaldo.get("viable"):
            if cachear:
                solver_cache.set(elecciones_forzadas, profesores, actividades, respaldo)
            return respaldo
        resultado = {
            "viable": False,
            "cached": False,
        }
        if estado != pywraplp.Solver.INFEASIBLE:
            resultado['indeterminado'] = True
            resultado['diagnostico'] = ['El solver no ha encontrado una solución dentro del límite de cálculo; esto no demuestra que la ordenación sea imposible. Reintenta la validación.']
            return resultado
        resultado = _con_diagnostico(resultado, elecciones_forzadas, profesores, actividades)

        if cachear:
            solver_cache.set(elecciones_forzadas, profesores, actividades, resultado)

        return resultado

    reparto = []
    total_repartos = 0
    actividades_divididas = 0

    for a in actividades:
        if int(split[a["id"]].solution_value()) == 1:
            actividades_divididas += 1

    for p in profesores:
        actividades_prof = []
        total_h = 0.0

        for a in actividades:
            val = int(x[(p["id"], a["id"])].solution_value())

            if val > 0:
                h = _desc(val)

                actividades_prof.append({
                    "actividad_id": a["id"],
                    "codigo": a["codigo"],
                    "tipo": a["tipo"],
                    "tipo_actividad": a["tipo"],
                    "codigo_grupo": a["codigo_grupo"],
                    "grupo": a["grupo"],
                    "idioma": a.get("idioma"),
                    "duracion": a.get("duracion"),
                    "turno": a.get("turno"),
                    "horas": h,
                })

                total_h += h
                total_repartos += 1

        reparto.append({
            "profesor": p["nombre"],
            "horas_totales": total_h,
            "actividades": actividades_prof,
        })

    resultado = {
        "viable": True,
        "reparto": reparto,
        "total_repartos": total_repartos,
        "actividades_divididas": actividades_divididas,
        "cached": False,
        "sin_optimizacion": solo_factibilidad,
    }

    if cachear:
        solver_cache.set(elecciones_forzadas, profesores, actividades, resultado)

    return resultado
