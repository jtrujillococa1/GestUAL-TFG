from typing import List, Dict, Tuple

def calcular_horas_asignadas_actividad(actividad_codigo: str, actividad_codigo_grupo: str,
                                       actividad_tipo: str, elecciones: List[Dict]) -> float:
    return sum(
        float(e["horas"]) for e in elecciones
        if (e["codigo"] == actividad_codigo and e["codigo_grupo"] == actividad_codigo_grupo and 
            (e.get("tipo") or e.get("tipo_actividad")) == actividad_tipo)
    )

def calcular_porcentaje_cobertura(horas_asignadas: float, horas_actividad: float) -> float:
    if horas_actividad == 0:
        return 0.0
    return round((horas_asignadas / horas_actividad) * 100, 1)

def esta_completa(horas_asignadas: float, horas_actividad: float, tolerancia: float = 0.01) -> bool:
    return abs(horas_actividad - horas_asignadas) < tolerancia
