"""
Modulo de turnos para ordenacion docente.
"""
from typing import List, Dict, Optional, Tuple
from models.schemas import ProfesorEstadoSchema


def calcular_nombre_completo(nombre: str, apellidos: str) -> str:
    """Formatea nombre completo en formato 'Apellidos, Nombre'."""
    return f"{apellidos}, {nombre}"


def obtener_nombre_profesor(profesor: Dict) -> str:
    """Obtiene el nombre canónico desde el formato de repositorio o solver."""
    if ", " in profesor["nombre"]:
        return profesor["nombre"]
    if profesor.get("apellidos") is not None:
        return calcular_nombre_completo(profesor["nombre"], profesor["apellidos"])
    return profesor["nombre"]


def obtener_carga_docente(profesor: Dict) -> float:
    """Obtiene la carga desde el formato de repositorio o solver."""
    if "carga_docente" in profesor:
        return float(profesor["carga_docente"])
    return float(profesor["horas_objetivo"])


def calcular_horas_por_profesor(profesores: List[Dict], confirmadas: List[Dict]) -> Dict[str, float]:
    """Calcula horas confirmadas por profesor."""
    horas: Dict[str, float] = {}
    for eleccion in confirmadas:
        profesor = eleccion["profesor"]
        horas[profesor] = horas.get(profesor, 0.0) + float(eleccion["horas"])
    return horas


def clasificar_profesores(
    profesores: List[Dict], 
    horas_confirmadas: Dict[str, float]
) -> Tuple[List[ProfesorEstadoSchema], List[ProfesorEstadoSchema]]:
    """Clasifica profesores en completados y pendientes."""
    completados: List[ProfesorEstadoSchema] = []
    pendientes: List[ProfesorEstadoSchema] = []
    
    for p in profesores:
        
        # Construir nombre completo
        nombre_completo = obtener_nombre_profesor(p)
        
        # Obtener horas asignadas
        asignadas = horas_confirmadas.get(nombre_completo, 0.0)
        carga_docente = float(p["carga_docente"])
        restantes = round(carga_docente - asignadas, 1)
        
        # Crear estado del profesor
        estado = ProfesorEstadoSchema(
            id=p["id"],
            nombre=p["nombre"],
            apellidos=p["apellidos"],
            categoria=p["categoria"],
            carga_docente=carga_docente,
            horas_confirmadas=asignadas,
            horas_restantes=restantes,
            area_id=p.get("area_id"),
            area_ids=list(p.get("area_ids") or ([p["area_id"]] if p.get("area_id") else [])),
            es_psi=p.get("es_psi", False),
        )
        
        # Clasificar
        if abs(restantes) < 0.01:
            completados.append(estado)
        else:
            pendientes.append(estado)
    
    return completados, pendientes


def obtener_profesor_actual(pendientes: List[ProfesorEstadoSchema]) -> Optional[str]:
    """Obtiene el nombre completo del profesor actual."""
    if not pendientes:
        return None
    return calcular_nombre_completo(pendientes[0].nombre, pendientes[0].apellidos)


def detectar_incidencias(pendientes: List[ProfesorEstadoSchema]) -> Optional[str]:
    """Detecta incidencias en profesores pendientes."""
    if not pendientes:
        return None
    
    primer_profesor = pendientes[0]
    
    # Caso 1: Horas negativas
    if primer_profesor.horas_restantes < 0:
        return (
            f"INCIDENCIA: '{primer_profesor.apellidos}, {primer_profesor.nombre}' "
            f"tiene horas_restantes={primer_profesor.horas_restantes} (negativas)"
        )
    
    # Caso 2: Horas restantes mayores que carga total
    if primer_profesor.horas_restantes > primer_profesor.carga_docente:
        return (
            f"INCIDENCIA: '{primer_profesor.apellidos}, {primer_profesor.nombre}' "
            f"tiene horas_restantes={primer_profesor.horas_restantes} "
            f"mayor que carga_docente={primer_profesor.carga_docente}"
        )
    
    return None


def validar_turno_completo(
    nombre_completo: str, 
    profesores: List[Dict], 
    todas_elecciones: List[Dict], 
    tolerancia: float = 0.01
) -> Tuple[bool, float, Optional[str]]:
    """Valida si un turno está completo."""
    # Buscar profesor por nombre completo
    profesor = None
    for p in profesores:
        nc = obtener_nombre_profesor(p)
        if nc == nombre_completo:
            profesor = p
            break
    
    if not profesor:
        return False, 0.0, f"Profesor '{nombre_completo}' no encontrado."
    
    # Calcular horas asignadas
    horas_asignadas = sum(
        float(e["horas"]) 
        for e in todas_elecciones 
        if e["profesor"] == nombre_completo
    )
    
    carga_docente = obtener_carga_docente(profesor)
    horas_restantes = round(carga_docente - horas_asignadas, 1)
    
    # Validar
    if abs(horas_restantes) < tolerancia:
        return True, horas_restantes, None
    
    if horas_restantes > 0:
        return False, horas_restantes, f"Faltan {horas_restantes}h por asignar."
    
    return False, horas_restantes, f"Se paso por {abs(horas_restantes)}h."
