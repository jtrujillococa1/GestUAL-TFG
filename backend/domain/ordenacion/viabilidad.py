from typing import List, Dict, Tuple, Optional
from core.config import settings
from domain.ordenacion.turnos import obtener_carga_docente, obtener_nombre_profesor


def _misma_actividad(actividad: Dict, eleccion: Dict) -> bool:
    """Usa el ID estable cuando existe; mantiene compatibilidad con datos antiguos."""
    if actividad.get("id") is not None and eleccion.get("actividad_id") is not None:
        return actividad["id"] == eleccion["actividad_id"]
    return (
        eleccion["codigo"] == actividad["codigo"]
        and eleccion["codigo_grupo"] == actividad["codigo_grupo"]
        and (eleccion.get("tipo") or eleccion.get("tipo_actividad")) == actividad["tipo"]
    )

def calcular_horas_restantes_actividad(actividad: Dict, elecciones: List[Dict]) -> float:
    horas_totales = float(actividad["horas_totales"])
    horas_asignadas = sum(
        float(e["horas"]) for e in elecciones
        if _misma_actividad(actividad, e)
    )
    return round(horas_totales - horas_asignadas, 1)

def calcular_horas_restantes_profesor(profesor_nombre: str, profesores: List[Dict], elecciones: List[Dict]) -> Optional[float]:
    profesor = next(
        (p for p in profesores if obtener_nombre_profesor(p) == profesor_nombre),
        None
    )
    if not profesor:
        return None
    horas_asignadas = sum(float(e["horas"]) for e in elecciones if e["profesor"] == profesor_nombre)
    return round(obtener_carga_docente(profesor) - horas_asignadas, 1)

def actividad_en_borrador(actividad: Dict, borrador: List[Dict]) -> bool:
    for e in borrador:
        if _misma_actividad(actividad, e):
            return True
    return False

def generar_candidatos_horas(horas_maximas_actividad: float, horas_restantes_profesor: float) -> List[float]:
    max_probar = round(min(horas_maximas_actividad, horas_restantes_profesor), 1)
    if max_probar < settings.HORAS_MINIMAS:
        return []
    candidatos = []
    h = max_probar
    while h >= settings.HORAS_MINIMAS - 0.001:
        h = round(h, 1)
        candidatos.append(h)
        h = round(h - settings.PASO_HORAS, 1)
    return candidatos

def categorizar_opcion(horas_restantes_tras_asignar: float) -> str:
    if abs(horas_restantes_tras_asignar) < 0.01:
        return "COMPLETA_TURNO"
    if horas_restantes_tras_asignar <= 1.0:
        return "CASI_COMPLETA"
    return "VIABLE"

def construir_opcion_dict(profesor_nombre: str, actividad: Dict, horas: float,
                         horas_restantes: float, horas_maximas_actividad: float,
                         resultado_solver: Dict, riesgo: Dict) -> Dict:
    categoria = categorizar_opcion(horas_restantes)
    return {
        "opcion": {
            "actividad_id": actividad.get("id"),
            "profesor": profesor_nombre,
            "codigo": actividad["codigo"],
            "nombre_asignatura": actividad.get("nombre_asignatura"),
            "tipo": actividad["tipo"],
            "codigo_grupo": actividad["codigo_grupo"],
            "grupo": actividad["grupo"],
            "horas": horas,
            "turno": actividad.get("turno"),
            "duracion": actividad.get("duracion"),
            "idioma": actividad.get("idioma"),
            "dias": actividad.get("dias"),
            "horario": actividad.get("horario"),
            "requiere_horario": actividad.get("requiere_horario", True),
            "horario_confirmado": actividad.get("horario_confirmado", False),
            "origen_horario": actividad.get("origen_horario", "PENDIENTE"),
        },
        "horas_restantes": horas_restantes,
        "horas_maximas_actividad": horas_maximas_actividad,
        "categoria": categoria,
        # Una opción no viable también se muestra al usuario; las respuestas
        # rápidas del solver para un conflicto pueden no incluir estadísticas.
        "total_repartos": int(resultado_solver.get("total_repartos", 0)),
        "actividades_divididas": int(resultado_solver.get("actividades_divididas", 0)),
        "riesgo": riesgo["riesgo"],
        "riesgo_nivel": riesgo["nivel"],
        "riesgo_impacto": riesgo.get("impacto", 0),
        "riesgo_motivos": riesgo.get("motivos", []),
        "riesgo_desglose": riesgo.get("desglose", {}),
        "cached": resultado_solver.get("cached", False),
    }

def priorizar_opciones(opciones: List[Dict]) -> List[Dict]:
    prioridad = {"COMPLETA_TURNO": 0, "CASI_COMPLETA": 1, "VIABLE": 2}
    return sorted(opciones, key=lambda x: (prioridad[x["categoria"]], x.get("riesgo") if x.get("riesgo") is not None else 101,
                                           x["actividades_divididas"], x["total_repartos"],
                                           -x["opcion"]["horas"]))
