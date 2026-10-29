from typing import List, Dict

def calcular_horas_asignadas(profesor_nombre: str, elecciones: List[Dict]) -> float:
    return sum(float(e["horas"]) for e in elecciones if e["profesor"] == profesor_nombre)

def calcular_porcentaje_completado(horas_asignadas: float, carga_docente: float) -> float:
    if carga_docente == 0:
        return 0.0
    return round((horas_asignadas / carga_docente) * 100, 1)

def esta_completo(horas_asignadas: float, carga_docente: float, tolerancia: float = 0.01) -> bool:
    return abs(carga_docente - horas_asignadas) < tolerancia
