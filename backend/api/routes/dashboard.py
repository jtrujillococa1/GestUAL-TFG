"""
API Routes - Dashboard
Endpoints para datos del dashboard según rol del usuario
"""

from collections import defaultdict
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user
from core.ambito_gestion import obtener_ambito_gestor
from repositories import ProfesorRepository, ActividadRepository, AreaRepository, DepartamentoRepository, RepartoRepository

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _pertenece_a_area(profesor: dict, area_id: int) -> bool:
    return area_id in set(
        profesor.get("area_ids")
        or ([profesor["area_id"]] if profesor.get("area_id") else [])
    )


def _pertenece_a_departamento(profesor: dict, departamento_id: int) -> bool:
    departamentos = set(profesor.get("departamento_ids") or [])
    if not departamentos and profesor.get("departamento_id") is not None:
        departamentos.add(profesor["departamento_id"])
    return departamento_id in departamentos


def _crear_indices(profesores: list, actividades: list, repartos: list) -> dict:
    """Agrupa los datos una vez para no recorrer el catálogo por cada área."""
    profesores_por_area = defaultdict(list)
    profesores_por_departamento = defaultdict(list)
    actividades_por_area = defaultdict(list)
    repartos_por_actividad = defaultdict(list)
    repartos_por_profesor = defaultdict(list)

    for profesor in profesores:
        area_ids = profesor.get("area_ids") or ([profesor["area_id"]] if profesor.get("area_id") else [])
        for area_id in area_ids:
            profesores_por_area[area_id].append(profesor)
        departamento_ids = profesor.get("departamento_ids") or ([] if profesor.get("departamento_id") is None else [profesor["departamento_id"]])
        for departamento_id in departamento_ids:
            profesores_por_departamento[departamento_id].append(profesor)

    # area_id es la cuota que se ordena. actividad_areas solo expresa la
    # pertenencia académica visible y no debe duplicar la demanda.
    for actividad in actividades:
        if actividad.get("area_id") is not None:
            actividades_por_area[actividad["area_id"]].append(actividad)

    for reparto in repartos:
        repartos_por_actividad[reparto.get("actividad_id")].append(reparto)
        repartos_por_profesor[reparto.get("profesor_id")].append(reparto)

    return {
        "profesores_por_area": profesores_por_area,
        "profesores_por_departamento": profesores_por_departamento,
        "actividades_por_area": actividades_por_area,
        "repartos_por_actividad": repartos_por_actividad,
        "repartos_por_profesor": repartos_por_profesor,
    }


def _metricas_de_area(area: dict, indices: dict) -> dict:
    """Calcula el avance real usando los grupos preindexados del catálogo."""
    profesores_area = [
        profesor for profesor in indices["profesores_por_area"].get(area["id"], [])
    ]
    actividades_area = indices["actividades_por_area"].get(area["id"], [])
    horas_actividades = sum(float(actividad.get("horas_area", 0)) for actividad in actividades_area)
    horas_asignadas = sum(
        float(reparto.get("horas", 0))
        for actividad in actividades_area
        for reparto in indices["repartos_por_actividad"].get(actividad["id"], [])
    )
    return {
        "id": area["id"],
        "codigo": area.get("codigo"),
        "nombre": area["nombre"],
        "num_profesores": len(profesores_area),
        "num_actividades": len(actividades_area),
        "horas_profesores": sum(float(profesor.get("carga_docente", 0)) for profesor in profesores_area),
        "horas_actividades": horas_actividades,
        "horas_asignadas": horas_asignadas,
        "horas_pendientes": max(0, round(horas_actividades - horas_asignadas, 1)),
        "progreso": round((horas_asignadas / horas_actividades * 100), 1) if horas_actividades else 0,
    }


@router.get("/")
def get_dashboard_data(current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Obtiene datos del dashboard según el rol del usuario.
    
    - ADMIN: Datos globales de toda la universidad
    - RESPONSABLE_DEPARTAMENTO: Datos de su departamento (desglosados por áreas)
    - RESPONSABLE_AREA: Datos de su área
    - PROFESOR: Datos de su área (limitados)
    - PSI: Datos de su área (solo lectura)
    """
    rol = current_user["rol"]
    user_id = current_user["user_id"]
    
    # Repositorios
    profesor_repo = ProfesorRepository()
    actividad_repo = ActividadRepository()
    area_repo = AreaRepository()
    departamento_repo = DepartamentoRepository()
    reparto_repo = RepartoRepository()
    
    # --- ADMIN: Vista global ---
    if rol == "admin":
        return _get_dashboard_admin(
            profesor_repo, actividad_repo, area_repo, departamento_repo, reparto_repo
        )

    # --- RESPONSABLE DEPARTAMENTO: Vista de su departamento ---
    if rol == "responsable_departamento":
        ambito = obtener_ambito_gestor(user_id, rol)
        departamento_id = next(iter(ambito["departamentos"]), None)
        if not departamento_id:
            raise HTTPException(status_code=403, detail="Responsable sin departamento asignado")
        
        return _get_dashboard_departamento(
            departamento_id, profesor_repo, actividad_repo, area_repo, departamento_repo, reparto_repo
        )
    
    # --- RESPONSABLE ÁREA: vista de su área asignada institucionalmente ---
    if rol == "responsable_area":
        ambito = obtener_ambito_gestor(user_id, rol)
        area_id = next(iter(ambito["areas"]), None)
        if not area_id:
            raise HTTPException(status_code=403, detail="Responsable sin área asignada")
        return _get_dashboard_area(
            area_id, profesor_repo, actividad_repo, area_repo, reparto_repo, rol
        )

    # --- PROFESOR / PSI: vista de su área docente ---
    else:
        usuario_profesor = profesor_repo.find_by_usuario_id(user_id)
        if not usuario_profesor:
            raise HTTPException(status_code=403, detail="Usuario sin perfil de profesor")
        
        area_id = next(iter(usuario_profesor.get("area_ids") or []), usuario_profesor.get("area_id"))
        if not area_id:
            raise HTTPException(status_code=403, detail="Usuario sin área asignada")
        
        return _get_dashboard_area(
            area_id, profesor_repo, actividad_repo, area_repo, reparto_repo, rol
        )


# ═══════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES POR ROL
# ═══════════════════════════════════════════════════════════════

def _get_dashboard_admin(profesor_repo, actividad_repo, area_repo, departamento_repo, reparto_repo):
    """Dashboard para ADMIN: vista global de toda la universidad"""
    
    profesores = profesor_repo.find_all()
    actividades = actividad_repo.find_all()
    areas = area_repo.find_all()
    departamentos = departamento_repo.find_all()
    repartos = reparto_repo.find_all_confirmadas()
    indices = _crear_indices(profesores, actividades, repartos)
    areas_por_departamento = defaultdict(list)
    for area in areas:
        areas_por_departamento[area.get("departamento_id")].append(area)
    departamentos_por_id = {departamento["id"]: departamento for departamento in departamentos}
    metricas_por_area = {area["id"]: _metricas_de_area(area, indices) for area in areas}
    
    # Estadísticas globales
    total_profesores = len(profesores)
    total_actividades = len(actividades)
    total_areas = len(areas)
    total_departamentos = len(departamentos)
    
    # Carga docente global
    total_horas_profesores = sum(float(p.get("carga_docente", 0)) for p in profesores)
    total_horas_actividades = sum(float(a.get("horas_area", 0)) for a in actividades)
    horas_asignadas = sum(float(r.get("horas", 0)) for r in repartos)
    
    # Progreso de ordenación
    progreso_ordenacion = round((horas_asignadas / total_horas_actividades * 100), 1) if total_horas_actividades > 0 else 0
    
    # Por departamento
    stats_departamentos = []
    for depto in departamentos:
        areas_depto = areas_por_departamento.get(depto["id"], [])
        profesores_depto = [
            profesor for profesor in indices["profesores_por_departamento"].get(depto["id"], [])
        ]
        actividades_depto = [
            actividad for area in areas_depto
            for actividad in indices["actividades_por_area"].get(area["id"], [])
        ]
        desglose_areas = [metricas_por_area[area["id"]] for area in areas_depto]
        horas_asignadas_depto = sum(metricas["horas_asignadas"] for metricas in desglose_areas)
        horas_actividades_depto = sum(metricas["horas_actividades"] for metricas in desglose_areas)

        stats_departamentos.append({
            "id": depto["id"],
            "codigo": depto["codigo"],
            "nombre": depto["nombre"],
            "num_areas": len(areas_depto),
            "num_profesores": len(profesores_depto),
            "num_actividades": len(actividades_depto),
            "horas_profesores": sum(float(p.get("carga_docente", 0)) for p in profesores_depto),
            "horas_actividades": horas_actividades_depto,
            "horas_asignadas": horas_asignadas_depto,
            "horas_pendientes": max(0, round(horas_actividades_depto - horas_asignadas_depto, 1)),
            "progreso": round((horas_asignadas_depto / horas_actividades_depto * 100), 1) if horas_actividades_depto else 0,
            "areas": desglose_areas,
        })
    
    # Por área
    stats_areas = []
    for area in areas:
        metricas_area = {
            **metricas_por_area[area["id"]],
            "departamento": departamentos_por_id.get(area.get("departamento_id"), {}).get("nombre", "Sin depto"),
        }
        stats_areas.append(metricas_area)
    
    return {
        "rol": "admin",
        "vista": "global",
        "resumen": {
            "total_departamentos": total_departamentos,
            "total_areas": total_areas,
            "total_profesores": total_profesores,
            "total_actividades": total_actividades,
            "total_horas_profesores": total_horas_profesores,
            "total_horas_actividades": total_horas_actividades,
            "horas_asignadas": horas_asignadas,
            "progreso_ordenacion": progreso_ordenacion,
        },
        "departamentos": stats_departamentos,
        "areas": stats_areas,
    }


def _get_dashboard_departamento(departamento_id, profesor_repo, actividad_repo, area_repo, departamento_repo, reparto_repo):
    """Dashboard para RESPONSABLE DEPARTAMENTO: vista de su departamento desglosada por áreas"""
    
    departamento = departamento_repo.find_by_id(departamento_id)
    if not departamento:
        raise HTTPException(status_code=404, detail="Departamento no encontrado")
    
    areas = area_repo.find_by_departamento(departamento_id)
    profesores_depto = profesor_repo.find_by_departamento(departamento_id)
    actividades_todas = actividad_repo.find_all()
    repartos_confirmados = reparto_repo.find_all_confirmadas()
    indices = _crear_indices(profesores_depto, actividades_todas, repartos_confirmados)
    
    # Estadísticas del departamento
    profesores_no_psi = profesores_depto
    total_profesores = len(profesores_no_psi)
    total_horas_profesores = sum(float(p.get("carga_docente", 0)) for p in profesores_no_psi)
    
    # Por área
    stats_areas = []
    total_actividades_depto = 0
    total_horas_actividades_depto = 0
    
    for area in areas:
        metricas_area = _metricas_de_area(area, indices)
        total_actividades_depto += metricas_area["num_actividades"]
        total_horas_actividades_depto += metricas_area["horas_actividades"]
        stats_areas.append(metricas_area)
    
    return {
        "rol": "responsable_departamento",
        "vista": "departamento",
        "departamento": {
            "id": departamento["id"],
            "nombre": departamento["nombre"],
        },
        "resumen": {
            "total_areas": len(areas),
            "total_profesores": total_profesores,
            "total_actividades": total_actividades_depto,
            "total_horas_profesores": total_horas_profesores,
            "total_horas_actividades": total_horas_actividades_depto,
        },
        "areas": stats_areas,
    }


def _get_dashboard_area(area_id, profesor_repo, actividad_repo, area_repo, reparto_repo, rol):
    """Dashboard para RESPONSABLE AREA / PROFESOR / PSI: vista de su área"""
    
    area = area_repo.find_by_id(area_id)
    if not area:
        raise HTTPException(status_code=404, detail="Área no encontrada")
    
    profesores_area = profesor_repo.find_by_area(area_id)
    actividades_area = [
        actividad for actividad in actividad_repo.find_all()
        if actividad.get("area_id") == area_id
    ]
    repartos_all = reparto_repo.find_all_confirmadas()
    indices = _crear_indices(profesores_area, actividades_area, repartos_all)
    repartos_area = [
        reparto for actividad in actividades_area
        for reparto in indices["repartos_por_actividad"].get(actividad["id"], [])
    ]
    
    profesores_no_psi = profesores_area
    
    total_horas_profesores = sum(float(p.get("carga_docente", 0)) for p in profesores_no_psi)
    total_horas_actividades = sum(float(a.get("horas_area", 0)) for a in actividades_area)
    horas_asignadas = sum(float(r.get("horas", 0)) for r in repartos_area)
    
    progreso = round((horas_asignadas / total_horas_actividades * 100), 1) if total_horas_actividades > 0 else 0
    
    # Por profesor
    stats_profesores = []
    for profesor in profesores_no_psi:
        repartos_prof = indices["repartos_por_profesor"].get(profesor["id"], [])

        horas_asignadas_prof = sum(float(r.get("horas", 0)) for r in repartos_prof)
        carga_prof = float(profesor.get("carga_docente", 0))
        
        stats_profesores.append({
            "id": profesor["id"],
            "nombre_completo": f"{profesor.get('apellidos', '')}, {profesor.get('nombre', '')}".strip(", "),
            "categoria": profesor.get("categoria", ""),
            "carga_docente": carga_prof,
            "horas_asignadas": horas_asignadas_prof,
            "horas_restantes": carga_prof - horas_asignadas_prof,
            "progreso": round((horas_asignadas_prof / carga_prof * 100), 1) if carga_prof > 0 else 0,
        })
    
    # Por tipo de actividad (GD=Teoría, GT=Prácticas, GL=Laboratorio, GA=Seminario)
    TIPO_LABEL = {"GD": "Teoría", "GT": "Prácticas", "GL": "Laboratorio", "GA": "Seminario"}
    stats_actividades = {label: {"count": 0, "horas": 0} for label in TIPO_LABEL.values()}

    for act in actividades_area:
        label = TIPO_LABEL.get(act.get("tipo", ""), "Otros")
        if label not in stats_actividades:
            stats_actividades[label] = {"count": 0, "horas": 0}
        stats_actividades[label]["count"] += 1
        stats_actividades[label]["horas"] += float(act.get("horas_area", 0))
    
    return {
        "rol": rol,
        "vista": "area",
        "area": {
            "id": area["id"],
            "nombre": area["nombre"],
        },
        "resumen": {
            "total_profesores": len(profesores_no_psi),
            "total_actividades": len(actividades_area),
            "total_horas_profesores": total_horas_profesores,
            "total_horas_actividades": total_horas_actividades,
            "horas_asignadas": horas_asignadas,
            "progreso_ordenacion": progreso,
        },
        "profesores": stats_profesores,
        "actividades_por_tipo": stats_actividades,
    }
