from datetime import date
from typing import Callable, Dict, List, Optional, Tuple

from solver.compatibilidad import actividades_incompatibles
from domain.ordenacion.planificacion_semanal import horas_entre
from domain.ordenacion.disponibilidad import (
    motivo_no_disponibilidad,
    profesor_disponible_para_actividad,
)


def validar_opcion_con_solver(nueva_opcion: Dict, confirmadas: List[Dict], borrador: List[Dict],
                              profesores: List[Dict], actividades: List[Dict],
                              resolver_fn: Callable, usar_cache: bool = True) -> Dict:
    return resolver_fn(confirmadas + borrador + [nueva_opcion], profesores, actividades, usar_cache=usar_cache)


def validar_estado_actual(confirmadas: List[Dict], borrador: List[Dict],
                         profesores: List[Dict], actividades: List[Dict],
                         resolver_fn: Callable, usar_cache: bool = True) -> Dict:
    return resolver_fn(confirmadas + borrador, profesores, actividades, usar_cache=usar_cache)


def _actividad_de_eleccion(eleccion: Dict, actividades_por_id: Dict[object, Dict]) -> Optional[Dict]:
    """Obtiene la ficha del catálogo, también para elecciones heredadas."""
    actividad_id = eleccion.get("actividad_id")
    if actividad_id in actividades_por_id:
        return actividades_por_id[actividad_id]
    return next(
        (
            actividad for actividad in actividades_por_id.values()
            if (actividad.get("codigo"), actividad.get("tipo"), actividad.get("codigo_grupo")) == (
                eleccion.get("codigo"), eleccion.get("tipo") or eleccion.get("tipo_actividad"),
                eleccion.get("codigo_grupo"),
            )
        ),
        None,
    )


def _sesiones_fechadas(actividad: Dict) -> List[Dict]:
    """Convierte el horario oficial a franjas físicas ordenables.

    Solo se usa cuando el catálogo dispone de fechas concretas. Los horarios
    semanales manuales se validan con la regla de compatibilidad habitual.
    """
    if not actividad.get("requiere_horario", True):
        return []
    sesiones: List[Dict] = []
    for sesion in actividad.get("horario_detallado") or []:
        if not isinstance(sesion, dict):
            continue
        try:
            fecha = date.fromisoformat(str(sesion.get("fecha") or "")[:10])
            inicio, fin = str(sesion.get("inicio") or "")[:5], str(sesion.get("fin") or "")[:5]
            horas = horas_entre(inicio, fin)
        except (TypeError, ValueError):
            continue
        if horas > 0:
            sesiones.append({"fecha": fecha, "inicio": inicio, "fin": fin, "horas": horas})
    return sorted(sesiones, key=lambda sesion: (sesion["fecha"], sesion["inicio"], sesion["fin"]))


def _solape_de_sesiones_reales(
    elecciones: List[Dict], actividades_por_id: Dict[object, Dict],
) -> Tuple[Optional[Dict], set[object]]:
    """Comprueba el tiempo exacto que ocupa cada elección con horario oficial.

    Cada docente reserva el horario completo de sus actividades, aunque
    comparta las horas adjudicadas con otra persona. El reparto de semanas
    se acuerda después y no permite eludir solapes durante la ordenación.
    """
    por_actividad: Dict[object, List[Tuple[Dict, Dict]]] = {}
    actividades_con_horario_real: set[object] = set()
    for indice, eleccion in enumerate(elecciones):
        actividad = _actividad_de_eleccion(eleccion, actividades_por_id)
        profesor = eleccion.get("profesor")
        if actividad is None or not profesor:
            continue
        clave = actividad.get("id") if actividad.get("id") is not None else ("eleccion", indice)
        por_actividad.setdefault(clave, []).append((eleccion, actividad))

    franjas_por_profesor: Dict[str, List[Tuple[Dict, Dict]]] = {}
    for clave, bloque in por_actividad.items():
        actividad = bloque[0][1]
        sesiones = _sesiones_fechadas(actividad)
        if not sesiones:
            continue
        actividades_con_horario_real.add(clave)
        adjudicaciones = [
            {"profesor_id": eleccion["profesor"], "horas": float(eleccion.get("horas", 0))}
            for eleccion, _ in bloque
            if float(eleccion.get("horas", 0)) > 0
        ]
        for adjudicacion in adjudicaciones:
            for sesion in sesiones:
                franjas_por_profesor.setdefault(str(adjudicacion['profesor_id']), []).append((sesion, actividad))

    for profesor, franjas in franjas_por_profesor.items():
        for indice, (primera, actividad_primera) in enumerate(franjas):
            for segunda, actividad_segunda in franjas[indice + 1:]:
                if actividad_primera.get("id") == actividad_segunda.get("id"):
                    continue
                if primera["fecha"] != segunda["fecha"]:
                    continue
                if not (primera["inicio"] < segunda["fin"] and segunda["inicio"] < primera["fin"]):
                    continue
                etiqueta = actividad_segunda.get("nombre_asignatura") or actividad_segunda.get("codigo") or "otra actividad"
                grupo = actividad_segunda.get("grupo") or actividad_segunda.get("codigo_grupo")
                return {
                    "motivo": f"Se solapa con {etiqueta} · {grupo}.",
                    "profesor": profesor,
                    "actividad_id": actividad_primera.get("id"),
                    "otra_actividad_id": actividad_segunda.get("id"),
                }, actividades_con_horario_real
    return None, actividades_con_horario_real


def detectar_conflicto_en_elecciones(elecciones: List[Dict], actividades: List[Dict]) -> Optional[Dict]:
    """Describe el primer solape de horario de un profesor.

    Los horarios sintéticos sin confirmar se omiten en la comprobación global
    porque son una estimación de catálogo. Sin embargo, en un borrador deben
    ser útiles: un profesor no puede preseleccionar dos clases que se dibujan
    en la misma franja. Por eso aquí se opta expresamente por considerarlos.
    """
    actividades_por_id = {actividad.get("id"): actividad for actividad in actividades if actividad.get("id") is not None}
    conflicto_real, actividades_reales = _solape_de_sesiones_reales(elecciones, actividades_por_id)
    if conflicto_real:
        return conflicto_real

    por_profesor: Dict[str, List[Tuple[Dict, object]]] = {}
    for eleccion in elecciones:
        profesor = eleccion.get("profesor")
        actividad = _actividad_de_eleccion(eleccion, actividades_por_id)
        if profesor and actividad:
            clave = actividad.get("id") if actividad.get("id") is not None else None
            por_profesor.setdefault(profesor, []).append((actividad, clave))

    for actividades_profesor in por_profesor.values():
        for indice, (actividad, clave) in enumerate(actividades_profesor):
            for otra, otra_clave in actividades_profesor[indice + 1:]:
                # Entre dos actividades con sesiones oficiales fechadas ya se
                # ha comparado el tramo exacto de cada profesor arriba.
                if clave in actividades_reales and otra_clave in actividades_reales:
                    continue
                if actividades_incompatibles(
                    actividad, otra, considerar_horarios_sinteticos=True,
                ):
                    etiqueta = otra.get("nombre_asignatura") or otra.get("codigo") or "otra actividad"
                    grupo = otra.get("grupo") or otra.get("codigo_grupo")
                    return {
                        "motivo": f"Se solapa con {etiqueta} · {grupo}.",
                        "profesor": profesor,
                        "actividad_id": actividad.get("id"),
                        "otra_actividad_id": otra.get("id"),
                    }
    return None


def detectar_solape_en_elecciones(elecciones: List[Dict], actividades: List[Dict]) -> Optional[str]:
    """Devuelve el mensaje del primer solape real dentro del horario."""
    conflicto = detectar_conflicto_en_elecciones(elecciones, actividades)
    return conflicto["motivo"] if conflicto else None


def buscar_opciones_viables(profesor_nombre: str, actividad: Dict, horas_candidatas: List[float],
                           confirmadas: List[Dict], borrador: List[Dict],
                           profesores: List[Dict], actividades: List[Dict],
                           resolver_fn: Callable,
                           resultado_rapido: Optional[Dict] = None) -> Optional[Dict]:
    """Devuelve una opción visible, incluso si el solver la declara inviable."""
    if not horas_candidatas:
        return None

    base = confirmadas + borrador
    profesor = next(
        (
            perfil for perfil in profesores
            if f"{perfil.get('apellidos')}, {perfil.get('nombre')}" == profesor_nombre
        ),
        None,
    )
    if profesor is not None and not profesor_disponible_para_actividad(profesor, actividad):
        motivo = motivo_no_disponibilidad(profesor, actividad)
        return {
            "horas": horas_candidatas[0],
            "resultado_solver": {
                "viable": False,
                "cached": False,
                "motivo_restriccion": motivo,
            },
            "viable": False,
            "motivo_no_viable": motivo,
            "bloqueada_por_solape": False,
        }

    nueva_base = {
        "profesor": profesor_nombre,
        "actividad_id": actividad.get("id"),
        "codigo": actividad["codigo"],
        "tipo": actividad["tipo"],
        "tipo_actividad": actividad["tipo"],
        "codigo_grupo": actividad["codigo_grupo"],
        "grupo": actividad["grupo"],
        "horas": horas_candidatas[0],
    }
    # Un solape solo puede producirse entre las actividades del mismo docente.
    # La petición puede contener cientos de adjudicaciones confirmadas de
    # otras áreas; analizarlas para cada tarjeta repetía innecesariamente la
    # expansión del calendario completo y acababa provocando timeouts.
    elecciones_profesor = [
        eleccion for eleccion in base
        if eleccion.get("profesor") == profesor_nombre
    ]
    motivo_solape = detectar_solape_en_elecciones(
        [nueva_base] + elecciones_profesor, actividades,
    )
    if motivo_solape:
        return {
            "horas": horas_candidatas[0],
            "resultado_solver": {"viable": False, "cached": False},
            "viable": False,
            "motivo_no_viable": motivo_solape,
            "bloqueada_por_solape": True,
        }

    if resultado_rapido is not None:
        return {"horas": horas_candidatas[0], "resultado_solver": resultado_rapido, "viable": True}

    ultimo_resultado: Optional[Dict] = None
    resultado_indeterminado: Optional[Dict] = None
    for horas in horas_candidatas:
        nueva = {
            "profesor": profesor_nombre,
            "actividad_id": actividad.get("id"),
            "codigo": actividad["codigo"],
            "tipo": actividad["tipo"],
            "tipo_actividad": actividad["tipo"],
            "codigo_grupo": actividad["codigo_grupo"],
            "grupo": actividad["grupo"],
            "horas": horas,
        }
        resultado = resolver_fn(base + [nueva], profesores, actividades, usar_cache=True)
        if resultado["viable"]:
            return {"horas": horas, "resultado_solver": resultado, "viable": True}
        ultimo_resultado = resultado
        if resultado.get("indeterminado"):
            resultado_indeterminado = resultado

    ultimo_resultado = resultado_indeterminado or ultimo_resultado
    diagnostico = (ultimo_resultado or {}).get("diagnostico") or []
    motivo = " ".join(diagnostico[:2]) if diagnostico else "No mantiene la viabilidad global de la ordenación."
    return {
        "horas": horas_candidatas[0],
        "resultado_solver": ultimo_resultado or {"viable": False, "cached": False},
        "viable": False,
        "motivo_no_viable": motivo,
        "bloqueada_por_solape": False,
    }


def confirmar_bloque_con_solver(bloque: List[Dict], profesores: List[Dict],
                                actividades: List[Dict], resolver_fn: Callable) -> Dict:
    return resolver_fn(bloque, profesores, actividades, usar_cache=True)
