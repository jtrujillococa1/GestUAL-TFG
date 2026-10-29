from typing import List, Dict

from typing import Any, Optional

from domain.ordenacion.turnos import obtener_carga_docente, obtener_nombre_profesor
from domain.ordenacion.disponibilidad import (
    cuatrimestres_actividad,
    normalizar_disponibilidad,
    profesor_disponible_para_actividad,
)
from solver.compatibilidad import actividades_incompatibles


def _clave_actividad(item: Dict):
    if item.get("actividad_id") is not None:
        return ("id", item["actividad_id"])
    return (item["codigo"], item["codigo_grupo"], item.get("tipo") or item.get("tipo_actividad"))


def calcular_equilibrio_horas(profesores: List[Dict], actividades: List[Dict], tolerancia: float = 0.01) -> Dict:
    horas_profesores = sum(float(p["horas_objetivo"]) for p in profesores)
    horas_actividades = sum(float(a["horas_totales"]) for a in actividades)
    diferencia = round(horas_profesores - horas_actividades, 1)
    equilibrado = abs(diferencia) < tolerancia
    
    return {
        "equilibrado": equilibrado,
        "horas_profesores": horas_profesores,
        "horas_actividades": horas_actividades,
        "diferencia": diferencia,
    }

def calcular_riesgo_global(profesores: List[Dict], actividades: List[Dict], confirmadas: List[Dict]) -> Dict:
    equilibrio = calcular_equilibrio_horas(profesores, actividades)
    
    horas_conf_por_id: Dict = {}
    horas_conf_legacy: Dict = {}
    for c in confirmadas:
        destino = horas_conf_por_id if c.get("actividad_id") is not None else horas_conf_legacy
        k = _clave_actividad(c)
        destino[k] = destino.get(k, 0.0) + float(c["horas"])
    
    actividades_incompletas = 0
    for a in actividades:
        clave_id = ("id", a["id"]) if a.get("id") is not None else None
        clave_legacy = _clave_actividad(a)
        asignadas = horas_conf_por_id.get(clave_id, 0.0) + horas_conf_legacy.get(clave_legacy, 0.0)
        if float(a["horas_totales"]) - asignadas > 0.01:
            actividades_incompletas += 1
    
    horas_conf_por_prof: Dict = {}
    for c in confirmadas:
        horas_conf_por_prof[c["profesor"]] = horas_conf_por_prof.get(c["profesor"], 0.0) + float(c["horas"])
    
    profesores_pendientes = 0
    for p in profesores:
        nombre_completo = p["nombre"] if ", " in p["nombre"] else (
            f"{p['apellidos']}, {p['nombre']}"
            if p.get("apellidos") is not None
            else p["nombre"]
        )
        asignadas = horas_conf_por_prof.get(nombre_completo, 0.0)
        carga_docente = float(
            p["carga_docente"] if "carga_docente" in p else p["horas_objetivo"]
        )
        if carga_docente - asignadas > 0.01:
            profesores_pendientes += 1
    
    score = 0
    if not equilibrio["equilibrado"]:
        score += 25
    if actividades_incompletas > 0:
        score += min(actividades_incompletas * 2, 35)
    if profesores_pendientes > 0:
        score += min(profesores_pendientes * 3, 25)
    
    riesgo = min(score, 100)
    
    if riesgo <= 25:
        nivel = "BAJO"
    elif riesgo <= 50:
        nivel = "MODERADO"
    elif riesgo <= 75:
        nivel = "ALTO"
    else:
        nivel = "CRITICO"
    
    return {
        "riesgo": riesgo,
        "nivel": nivel,
        "motivo": f"Desequilibrio={not equilibrio['equilibrado']}, actividades incompletas={actividades_incompletas}, profesores pendientes={profesores_pendientes}",
        "actividades_incompletas": actividades_incompletas,
        "profesores_pendientes": profesores_pendientes,
        "equilibrado": equilibrio["equilibrado"],
    }


def _identificador_actividad(actividad: Dict) -> tuple:
    """Devuelve una clave estable, compatible también con datos heredados."""
    if actividad.get("id") is not None:
        return ("id", actividad["id"])
    return _clave_actividad(actividad)


def _areas_profesor(profesor: Dict) -> set[int]:
    areas = profesor.get("area_ids")
    if areas is not None:
        return {int(area) for area in areas}
    return {int(profesor["area_id"])} if profesor.get("area_id") is not None else set()


def _profesor_puede_cubrir(profesor: Dict, actividad: Dict) -> bool:
    area_actividad = actividad.get("area_id")
    areas_profesor = _areas_profesor(profesor)
    area_compatible = area_actividad is None or not areas_profesor or area_actividad in areas_profesor
    return area_compatible and profesor_disponible_para_actividad(profesor, actividad)


def _objetivo_en_ambito(profesor: Dict, area_id: Optional[int]) -> float:
    """Carga disponible en el ámbito evaluado, sin duplicar a un multiarea."""
    if area_id is None:
        return obtener_carga_docente(profesor)

    objetivos_por_area = profesor.get("horas_objetivo_por_area") or {}
    objetivo = objetivos_por_area.get(area_id, objetivos_por_area.get(str(area_id)))
    if objetivo is not None:
        return float(objetivo)

    # Compatibilidad con perfiles anteriores a la cuota explícita por área.
    return (
        obtener_carga_docente(profesor)
        if profesor.get("area_id") == area_id
        else 0.0
    )


def _actividad_de_eleccion(eleccion: Dict, actividades_por_clave: Dict[tuple, Dict]) -> Optional[Dict]:
    if eleccion.get("actividad_id") is not None:
        actividad = actividades_por_clave.get(("id", eleccion["actividad_id"]))
        if actividad is not None:
            return actividad
    return actividades_por_clave.get(_clave_actividad(eleccion))


def _nivel_riesgo(riesgo: int) -> str:
    if riesgo <= 20:
        return "BAJO"
    if riesgo <= 45:
        return "MODERADO"
    if riesgo <= 70:
        return "ALTO"
    return "CRITICO"


def preparar_contexto_riesgo(
    profesores: List[Dict], actividades: List[Dict], area_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Precalcula datos inmutables para evaluar las opciones de un mismo turno."""
    actividades_ambito = [
        actividad for actividad in actividades
        if area_id is None or actividad.get("area_id") == area_id
    ]
    # Conserva las agendas de otras áreas de los docentes compartidos, sin
    # comparar entre sí áreas ajenas a esta cola.
    areas_relacionadas = set()
    for profesor in profesores:
        areas = _areas_profesor(profesor)
        if area_id is None or area_id in areas:
            areas_relacionadas.update(areas)
    actividades_agenda = [a for a in actividades if area_id is None or a.get('area_id') in areas_relacionadas or a in actividades_ambito]
    actividades_por_clave: Dict[tuple, Dict] = {}
    for actividad in actividades_agenda:
        actividades_por_clave[_identificador_actividad(actividad)] = actividad
        actividades_por_clave.setdefault(_clave_actividad(actividad), actividad)

    incompatibilidades = set()
    for indice, primera in enumerate(actividades_ambito):
        for segunda in actividades_agenda:
            if primera is segunda:
                continue
            if actividades_incompatibles(primera, segunda):
                incompatibilidades.add(
                    frozenset((_identificador_actividad(primera), _identificador_actividad(segunda)))
                )

    return {
        "profesores": profesores,
        "actividades_ambito": actividades_ambito,
        "actividades_por_clave": actividades_por_clave,
        "incompatibilidades": incompatibilidades,
        "area_id": area_id,
    }


def calcular_riesgo_estado(elecciones: List[Dict], contexto: Dict[str, Any]) -> Dict[str, Any]:
    """Mide la fragilidad residual dentro del área, tras elecciones concretas.

    Solo tiene en cuenta restricciones operativas: cobertura compatible, cuota
    restante y solapes de horarios confirmados. No confunde preferencias del
    docente con riesgo técnico.
    """
    actividades_ambito: List[Dict] = contexto["actividades_ambito"]
    actividades_por_clave: Dict[tuple, Dict] = contexto["actividades_por_clave"]
    profesores: List[Dict] = contexto["profesores"]
    area_id: Optional[int] = contexto["area_id"]

    if not actividades_ambito:
        return {
            "riesgo": 0,
            "nivel": "BAJO",
            "motivos": [],
            "desglose": {"cobertura": 0, "margen": 0, "configuracion": 0, "cuatrimestre": 0},
            "horas_pendientes": 0.0,
            "actividades_criticas": 0,
        }

    elecciones_por_actividad: Dict[tuple, float] = {}
    elecciones_por_profesor: Dict[str, List[Dict]] = {}
    horas_por_profesor_ambito: Dict[str, float] = {}
    for eleccion in elecciones:
        actividad = _actividad_de_eleccion(eleccion, actividades_por_clave)
        if actividad is None:
            continue
        clave = _identificador_actividad(actividad)
        elecciones_por_actividad[clave] = elecciones_por_actividad.get(clave, 0.0) + float(eleccion["horas"])
        profesor = eleccion.get("profesor")
        if profesor:
            elecciones_por_profesor.setdefault(profesor, []).append(actividad)
            if area_id is None or actividad.get("area_id") == area_id:
                horas_por_profesor_ambito[profesor] = (
                    horas_por_profesor_ambito.get(profesor, 0.0) + float(eleccion["horas"])
                )

    capacidad_restante: Dict[str, float] = {}
    profesores_relevantes: List[Dict] = []
    for profesor in profesores:
        if not any(
            actividad.get("area_id") is None
            or not _areas_profesor(profesor)
            or actividad.get("area_id") in _areas_profesor(profesor)
            for actividad in actividades_ambito
        ):
            continue
        nombre = obtener_nombre_profesor(profesor)
        objetivo = _objetivo_en_ambito(profesor, area_id)
        if objetivo <= 0:
            continue
        profesores_relevantes.append(profesor)
        capacidad_restante[nombre] = max(
            0.0,
            round(objetivo - horas_por_profesor_ambito.get(nombre, 0.0), 1),
        )

    horas_pendientes = 0.0
    horas_criticas = 0.0
    horas_limitadas = 0.0
    horas_margen_ajustado = 0.0
    horas_restringidas_cuatrimestre = 0.0
    demanda_por_cuatrimestre = {"C1": 0.0, "C2": 0.0}
    actividades_criticas: List[str] = []
    actividades_limitadas: List[str] = []
    incompatibilidades = contexto["incompatibilidades"]
    demandas_compartidas: Dict[frozenset, float] = {}

    for actividad in actividades_ambito:
        clave = _identificador_actividad(actividad)
        pendientes = max(0.0, round(float(actividad["horas_totales"]) - elecciones_por_actividad.get(clave, 0.0), 1))
        if pendientes <= 0.01:
            continue
        horas_pendientes += pendientes
        cuatrimestres = cuatrimestres_actividad(actividad)
        # Las actividades anuales requieren disponibilidad en ambos periodos,
        # pero no se pueden reservar íntegramente contra uno solo de ellos.
        if len(cuatrimestres) == 1:
            demanda_por_cuatrimestre[next(iter(cuatrimestres))] += pendientes
        candidatos = 0
        nombres_candidatos = set()
        capacidad_candidata = 0.0
        bloqueados_por_cuatrimestre = 0

        for profesor in profesores_relevantes:
            nombre = obtener_nombre_profesor(profesor)
            disponible = capacidad_restante.get(nombre, 0.0)
            area_actividad = actividad.get("area_id")
            if area_actividad is not None and area_actividad not in _areas_profesor(profesor):
                continue
            if disponible <= 0.01:
                continue
            if not profesor_disponible_para_actividad(profesor, actividad):
                bloqueados_por_cuatrimestre += 1
                continue

            tiene_solape = any(
                otra is not actividad
                and frozenset((_identificador_actividad(actividad), _identificador_actividad(otra))) in incompatibilidades
                for otra in elecciones_por_profesor.get(nombre, [])
            )
            if tiene_solape:
                continue

            candidatos += 1
            nombres_candidatos.add(nombre)
            capacidad_candidata += min(disponible, pendientes)

        etiqueta = actividad.get("nombre_asignatura") or actividad.get("codigo") or "actividad"
        clave_candidatos = frozenset(nombres_candidatos)
        demandas_compartidas[clave_candidatos] = demandas_compartidas.get(clave_candidatos, 0.0) + pendientes
        if candidatos <= 1:
            horas_criticas += pendientes
            actividades_criticas.append(str(etiqueta))
        elif candidatos == 2:
            horas_limitadas += pendientes
            actividades_limitadas.append(str(etiqueta))

        if bloqueados_por_cuatrimestre and candidatos <= 2:
            horas_restringidas_cuatrimestre += pendientes

        if capacidad_candidata < pendientes * 1.15:
            horas_margen_ajustado += pendientes

    reservas_cuatrimestre: List[tuple[str, float, float]] = []
    riesgo_reservas_cuatrimestre = 0
    reservas_imposibles: List[tuple[str, float, float]] = []
    for cuatrimestre, disponibilidad in (("C1", "PRIMERO"), ("C2", "SEGUNDO")):
        demanda = demanda_por_cuatrimestre[cuatrimestre]
        if demanda <= 0.01:
            continue
        reserva = sum(
            capacidad_restante.get(obtener_nombre_profesor(profesor), 0.0)
            for profesor in profesores_relevantes
            if normalizar_disponibilidad(profesor.get("disponibilidad_cuatrimestre")) == disponibilidad
        )
        if reserva <= 0.01:
            continue

        # Esta carga no es una preferencia: debe quedar disponible para las
        # actividades exclusivas del cuatrimestre correspondiente. Incluso
        # con margen suficiente se informa desde el primer turno; conforme
        # otras elecciones consumen ese periodo, la proporción y el riesgo
        # aumentan hasta señalar una reserva prácticamente agotada.
        proporcion_reservada = reserva / demanda
        if reserva > demanda + 0.01:
            reservas_imposibles.append((cuatrimestre, reserva, demanda))
        impacto = max(2, round(15 * min(proporcion_reservada, 1.0)))
        margen = demanda - reserva
        if margen <= demanda * 0.20:
            impacto += min(10, round(10 * (1 - max(margen, 0.0) / max(demanda * 0.20, 1.0))))
        riesgo_reservas_cuatrimestre += min(25, impacto)
        reservas_cuatrimestre.append((cuatrimestre, reserva, demanda))

    capacidad_total = round(sum(capacidad_restante.values()), 1)
    desajuste = abs(capacidad_total - horas_pendientes)
    proporcion_desajuste = desajuste / max(horas_pendientes, capacidad_total, 1.0)

    desglose = {"cobertura": 0, "margen": 0, "configuracion": 0, "cuatrimestre": 0}
    # Examina conjuntos de actividades que dependen del mismo grupo de
    # docentes. Cada capacidad se cuenta una sola vez dentro del conjunto.
    # Incluye grupos contenidos (p. ej. {A}, {B}, {A,B}), sin enumerar
    # exponencialmente todos los subconjuntos. No sustituye al solver exacto.
    competencia = 0
    for grupo in demandas_compartidas:
        demanda_grupo = sum(h for candidatos, h in demandas_compartidas.items() if candidatos <= grupo)
        capacidad_grupo = sum(capacidad_restante[nombre] for nombre in grupo)
        if demanda_grupo > capacidad_grupo + 0.01:
            competencia = 100
            break
        if demanda_grupo > 0:
            margen_grupo = (capacidad_grupo - demanda_grupo) / demanda_grupo
            competencia = max(competencia, round(25 * max(0.0, 1 - margen_grupo / 0.15)))
    desglose["competencia"] = competencia
    motivos: List[str] = []
    if horas_pendientes > 0:
        desglose["cobertura"] = min(
            35,
            round(35 * horas_criticas / horas_pendientes + 15 * horas_limitadas / horas_pendientes),
        )
        desglose["margen"] = min(25, round(25 * horas_margen_ajustado / horas_pendientes))
        desglose["cuatrimestre"] = min(
            25,
            max(
                round(20 * horas_restringidas_cuatrimestre / horas_pendientes),
                riesgo_reservas_cuatrimestre,
            ),
        )
    if reservas_imposibles:
        # No hay suficientes actividades exclusivas de ese periodo para que
        # los docentes restringidos completen su carga: el área ya nace sin
        # salida y debe verse como crítica antes de iniciar ningún turno.
        desglose["cuatrimestre"] = 100

    if proporcion_desajuste > 0.02:
        desglose["configuracion"] = min(30, 10 + round(20 * min(proporcion_desajuste, 1.0)))
        direccion = "faltan" if capacidad_total < horas_pendientes else "sobran"
        motivos.append(
            f"En el área {direccion} {desajuste:g} h de carga frente a las actividades pendientes."
        )
    if actividades_criticas:
        ejemplo = ", ".join(dict.fromkeys(actividades_criticas[:2]))
        motivos.append(f"Cobertura crítica: solo queda una alternativa para {ejemplo}.")
    elif actividades_limitadas:
        ejemplo = ", ".join(dict.fromkeys(actividades_limitadas[:2]))
        motivos.append(f"Cobertura limitada: solo quedan dos alternativas para {ejemplo}.")
    if horas_margen_ajustado > 0.01:
        motivos.append("La capacidad compatible restante tiene un margen inferior al 15% en alguna actividad.")
    if horas_restringidas_cuatrimestre > 0.01:
        motivos.append("La disponibilidad por cuatrimestre limita alternativas en actividades pendientes.")
    for cuatrimestre, reserva, demanda in reservas_cuatrimestre:
        etiqueta = "primer" if cuatrimestre == "C1" else "segundo"
        motivos.append(
            f"Reserva de {reserva:g} h para docentes limitados al {etiqueta} cuatrimestre "
            f"frente a {demanda:g} h de actividades de ese periodo."
        )
    for cuatrimestre, reserva, demanda in reservas_imposibles:
        etiqueta = "primer" if cuatrimestre == "C1" else "segundo"
        motivos.append(
            f"Inviable desde el inicio: la reserva de {reserva:g} h para el {etiqueta} "
            f"cuatrimestre supera las {demanda:g} h de actividades de ese periodo."
        )

    riesgo = min(100, sum(desglose.values()))
    return {
        "riesgo": riesgo,
        "nivel": _nivel_riesgo(riesgo),
        "motivos": motivos,
        "desglose": desglose,
        "horas_pendientes": round(horas_pendientes, 1),
        "actividades_criticas": len(set(actividades_criticas)),
    }


def evaluar_riesgo_opcion(
    elecciones: List[Dict],
    resultado_solver: Dict,
    contexto: Dict[str, Any],
    riesgo_base: Optional[Dict[str, Any]] = None,
    resultado_base: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Evalúa el impacto concreto de una elección ya simulada por el solver."""
    if resultado_solver.get("indeterminado"):
        return {
            "riesgo": None, "nivel": "PENDIENTE", "impacto": None,
            "motivos": resultado_solver.get("diagnostico") or ["Pendiente de verificación: no se ha demostrado que sea inviable."],
            "desglose": {},
        }
    if not resultado_solver.get("viable", False):
        motivo_restriccion = resultado_solver.get("motivo_restriccion")
        return {
            "riesgo": 100,
            "nivel": "CRITICO",
            "impacto": None,
            "motivos": [motivo_restriccion or "La elección no mantiene la viabilidad global de la ordenación."],
            "desglose": {
                "cobertura": 0,
                "margen": 0,
                "configuracion": 0,
                "cuatrimestre": 100 if motivo_restriccion else 0,
                "fragmentacion": 0,
                "repartos": 0,
            },
        }

    estado = calcular_riesgo_estado(elecciones, contexto)
    base = riesgo_base or calcular_riesgo_estado([], contexto)
    desglose = dict(estado["desglose"])
    motivos = list(estado["motivos"])

    # En el listado masivo de opciones se puede usar el modelo en modo de
    # factibilidad para responder con agilidad. Ese modo certifica que hay
    # solución, pero no busca el mínimo número de cortes; por ello no sería
    # honesto convertir su reparto incidental en una penalización de riesgo.
    # Los componentes de cobertura, margen y cuatrimestre siguen siendo
    # exactos y son los que determinan la seguridad de la elección.
    sin_optimizacion = bool(
        resultado_solver.get("sin_optimizacion")
        or (resultado_base or {}).get("sin_optimizacion")
    )
    repartos_base = int((resultado_base or {}).get("total_repartos", 0))
    divisiones_base = int((resultado_base or {}).get("actividades_divididas", 0))
    incremento_divisiones = 0 if sin_optimizacion else max(
        0, int(resultado_solver.get("actividades_divididas", 0)) - divisiones_base,
    )
    incremento_repartos = 0 if sin_optimizacion else max(
        0, int(resultado_solver.get("total_repartos", 0)) - repartos_base,
    )
    desglose["fragmentacion"] = min(24, incremento_divisiones * 12)
    desglose["repartos"] = min(15, incremento_repartos * 3)

    if incremento_divisiones:
        unidad = "actividad" if incremento_divisiones == 1 else "actividades"
        adicional = "adicional" if incremento_divisiones == 1 else "adicionales"
        motivos.append(f"Esta elección obliga a dividir {incremento_divisiones} {unidad} {adicional}.")
    if incremento_repartos:
        unidad = "asignación" if incremento_repartos == 1 else "asignaciones"
        adicional = "adicional" if incremento_repartos == 1 else "adicionales"
        motivos.append(f"El reparto final necesitaría {incremento_repartos} {unidad} {adicional}.")

    riesgo = min(100, sum(desglose.values()))
    impacto = riesgo - int(base.get("riesgo", 0))
    return {
        "riesgo": riesgo,
        "nivel": _nivel_riesgo(riesgo),
        "impacto": impacto,
        "motivos": motivos,
        "desglose": desglose,
        "horas_pendientes": estado["horas_pendientes"],
        "actividades_criticas": estado["actividades_criticas"],
    }
