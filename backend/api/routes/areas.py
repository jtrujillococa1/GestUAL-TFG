"""
API Routes - Áreas.

Endpoints para gestión de áreas académicas.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from repositories import AreaRepository, DepartamentoRepository, ProfesorRepository
from core.exceptions import AreaNotFound, DepartamentoNotFound, ConstraintViolation
from core.auth import get_current_user, require_admin
from core.ambito_gestion import obtener_ambito_gestor

router = APIRouter(prefix="/api/v1/areas", tags=["areas"])


def _areas_del_profesor(profesor: dict) -> set[int]:
    return set(profesor.get("area_ids") or ([profesor["area_id"]] if profesor.get("area_id") else []))


def _departamentos_del_profesor(profesor: dict) -> set[int]:
    departamentos = set(profesor.get("departamento_ids") or [])
    if not departamentos and profesor.get("departamento_id") is not None:
        departamentos.add(profesor["departamento_id"])
    return departamentos


# ═══════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════

class CreateAreaRequest(BaseModel):
    """Request para crear área."""
    codigo: str
    nombre: str
    departamento_id: int
    responsable_area_id: Optional[int] = None


class UpdateAreaRequest(BaseModel):
    """Request para actualizar área."""
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    departamento_id: Optional[int] = None
    responsable_area_id: Optional[int] = None


class AsignarResponsableRequest(BaseModel):
    """Request para asignar responsable."""
    responsable_id: Optional[int] = None


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _verificar_acceso_area(current_user: dict, area_id: int, operacion: str):
    """
    Verifica acceso al área según rol.
    """
    rol = current_user["rol"]
    
    # ADMIN puede todo
    if rol == "admin":
        return True
    
    # Obtener área objetivo
    repo = AreaRepository()
    area_target = repo.find_by_id(area_id)
    
    if not area_target:
        raise HTTPException(status_code=404, detail="Área no encontrada")
    
    # RESPONSABLE_DEPARTAMENTO: puede gestionar áreas de su departamento
    if rol == "responsable_departamento":
        ambito = obtener_ambito_gestor(current_user["user_id"], rol)
        if area_target["departamento_id"] not in ambito["departamentos"]:
            raise HTTPException(status_code=403, detail="Solo puedes gestionar áreas de tu departamento")
        
        if operacion in ["create", "update", "delete", "assign_responsable", "read"]:
            return True
    
    # RESPONSABLE_AREA: solo lectura de su área (NO puede crear/editar/eliminar áreas)
    if rol == "responsable_area":
        if operacion != "read":
            raise HTTPException(status_code=403, detail="No puedes modificar áreas")
        
        ambito = obtener_ambito_gestor(current_user["user_id"], rol)
        if area_target["id"] not in ambito["areas"]:
            raise HTTPException(status_code=403, detail="Solo puedes ver tu área")
        
        return True
    
    # PROFESOR/PSI: solo lectura de su área
    if rol in ["profesor", "psi"]:
        usuario_autenticado = ProfesorRepository().find_by_usuario_id(current_user["user_id"])
        if not usuario_autenticado:
            raise HTTPException(status_code=403, detail="No tienes perfil de profesor")
        if operacion != "read":
            raise HTTPException(status_code=403, detail="No tienes permisos para modificar áreas")
        
        if area_target["id"] not in _areas_del_profesor(usuario_autenticado):
            raise HTTPException(status_code=403, detail="Solo puedes ver tu área")
        
        return True
    
    raise HTTPException(status_code=403, detail="Acceso denegado")


def _filtrar_areas_por_acceso(current_user: dict, areas: List[dict]) -> List[dict]:
    """Filtra áreas según acceso del usuario."""
    rol = current_user["rol"]
    
    if rol == "admin":
        return areas
    
    # RESPONSABLE_DEPARTAMENTO: áreas de su departamento
    if rol == "responsable_departamento":
        ambito = obtener_ambito_gestor(current_user["user_id"], rol)
        return [a for a in areas if a.get("departamento_id") in ambito["departamentos"]]
    if rol == "responsable_area":
        ambito = obtener_ambito_gestor(current_user["user_id"], rol)
        return [a for a in areas if a.get("id") in ambito["areas"]]
    
    # PROFESOR, PSI: solo su área docente.
    usuario_autenticado = ProfesorRepository().find_by_usuario_id(current_user["user_id"])
    if not usuario_autenticado:
        return []
    areas_usuario = _areas_del_profesor(usuario_autenticado)
    return [a for a in areas if a.get("id") in areas_usuario]


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS - ÁREAS
# ═══════════════════════════════════════════════════════════════

@router.get("/", summary="Listar áreas")
def get_areas(
    current_user: dict = Depends(get_current_user)  # ✅ Todos autenticados
):
    """
    Obtiene áreas según permisos del usuario.
    
    **Roles permitidos:**
    - ADMIN: Todas las áreas
    - RESPONSABLE_DEPARTAMENTO: Áreas de su departamento
    - RESPONSABLE_AREA/PROFESOR/PSI: Solo su área
    """
    repo = AreaRepository()
    areas = repo.find_all()
    return _filtrar_areas_por_acceso(current_user, areas)


@router.get("/{area_id}", summary="Obtener área por ID")
def get_area(
    area_id: int,
    current_user: dict = Depends(get_current_user)  # ✅ Verificar acceso
):
    """
    Obtiene un área específica.
    
    **Roles permitidos:** Mismo criterio que listar
    """
    _verificar_acceso_area(current_user, area_id, "read")
    
    repo = AreaRepository()
    area = repo.find_by_id(area_id)
    if not area:
        raise HTTPException(status_code=404, detail=f"Área {area_id} no encontrada.")
    return area


@router.get("/departamento/{departamento_id}", summary="Áreas por departamento")
def get_areas_por_departamento(
    departamento_id: int,
    current_user: dict = Depends(get_current_user)  # ✅ Verificar acceso
):
    """
    Obtiene áreas de un departamento.
    
    **Roles permitidos:**
    - ADMIN: Cualquier departamento
    - RESPONSABLE_DEPARTAMENTO: Solo su departamento
    - Otros: No permitido directamente (usar GET /)
    """
    rol = current_user["rol"]
    
    if rol != "admin":
        if rol == "responsable_departamento":
            ambito = obtener_ambito_gestor(current_user["user_id"], rol)
            if departamento_id not in ambito["departamentos"]:
                raise HTTPException(status_code=403, detail="Solo puedes ver áreas de tu departamento")
        elif rol == "responsable_area":
            ambito = obtener_ambito_gestor(current_user["user_id"], rol)
            if not any(area["id"] in ambito["areas"] for area in AreaRepository().find_by_departamento(departamento_id)):
                raise HTTPException(status_code=403, detail="No tienes acceso a este departamento")
        else:
            usuario_autenticado = ProfesorRepository().find_by_usuario_id(current_user["user_id"])
            if not usuario_autenticado or departamento_id not in _departamentos_del_profesor(usuario_autenticado):
                raise HTTPException(status_code=403, detail="No tienes acceso a este departamento")
    
    repo = AreaRepository()
    return repo.find_by_departamento(departamento_id)


@router.post("/", status_code=status.HTTP_201_CREATED, summary="Crear área")
def create_area(
    body: CreateAreaRequest,
    current_user: dict = Depends(get_current_user)  # ✅ Verificar permisos
):
    """
    Crea una nueva área.
    
    **Roles permitidos:**
    - ADMIN: En cualquier departamento
    - RESPONSABLE_DEPARTAMENTO: Solo en su departamento
    - Otros: No permitido
    """
    rol = current_user["rol"]
    
    # Solo ADMIN y RESPONSABLE_DEPARTAMENTO pueden crear áreas
    if rol not in ["admin", "responsable_departamento"]:
        raise HTTPException(status_code=403, detail="No tienes permisos para crear áreas")
    
    # Verificar departamento si es RESPONSABLE_DEPARTAMENTO
    if rol == "responsable_departamento":
        ambito = obtener_ambito_gestor(current_user["user_id"], rol)
        if body.departamento_id not in ambito["departamentos"]:
            raise HTTPException(status_code=403, detail="Solo puedes crear áreas en tu departamento")
    
    repo = AreaRepository()
    try:
        return repo.create(
            body.codigo,
            body.nombre,
            body.departamento_id,
            body.responsable_area_id,
        )
    except ConstraintViolation as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{area_id}", summary="Actualizar área")
def update_area(
    area_id: int,
    body: UpdateAreaRequest,
    current_user: dict = Depends(get_current_user)  # ✅ Verificar permisos
):
    """
    Actualiza un área existente.
    
    **Roles permitidos:**
    - ADMIN: Cualquier área
    - RESPONSABLE_DEPARTAMENTO: Áreas de su departamento
    - Otros: No permitido
    """
    _verificar_acceso_area(current_user, area_id, "update")
    
    repo = AreaRepository()
    
    updates = {}
    if body.codigo is not None:
        updates["codigo"] = body.codigo
    if body.nombre is not None:
        updates["nombre"] = body.nombre
    if body.departamento_id is not None:
        updates["departamento_id"] = body.departamento_id
    if "responsable_area_id" in body.model_fields_set:
        updates["responsable_area_id"] = body.responsable_area_id
    
    if not updates:
        raise HTTPException(status_code=400, detail="No se proporcionó ningún campo")
    
    try:
        return repo.update(area_id, updates)
    except AreaNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConstraintViolation as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{area_id}/responsable", summary="Asignar responsable")
def asignar_responsable_area(
    area_id: int,
    body: AsignarResponsableRequest,
    current_user: dict = Depends(get_current_user)  # ✅ Verificar permisos
):
    """
    Asigna o quita el responsable de un área.
    
    **Roles permitidos:**
    - ADMIN: Cualquier área
    - RESPONSABLE_DEPARTAMENTO: Áreas de su departamento
    - Otros: No permitido
    """
    _verificar_acceso_area(current_user, area_id, "assign_responsable")
    
    repo = AreaRepository()
    try:
        return repo.asignar_responsable(area_id, body.responsable_id)
    except AreaNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConstraintViolation as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{area_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar área")
def delete_area(
    area_id: int,
    current_user: dict = Depends(get_current_user)  # ✅ Verificar permisos
):
    """
    Elimina un área.
    
    **Roles permitidos:**
    - ADMIN: Cualquier área
    - RESPONSABLE_DEPARTAMENTO: Áreas de su departamento
    - Otros: No permitido
    """
    _verificar_acceso_area(current_user, area_id, "delete")
    
    repo = AreaRepository()
    try:
        repo.delete(area_id)
    except AreaNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConstraintViolation as e:
        raise HTTPException(status_code=400, detail=str(e))
