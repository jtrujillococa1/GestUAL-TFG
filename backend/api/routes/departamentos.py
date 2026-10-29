"""
API Routes - Departamentos.

Endpoints para gestión de departamentos.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from repositories import DepartamentoRepository, ProfesorRepository
from core.exceptions import DepartamentoNotFound, ConstraintViolation
from core.auth import get_current_user, require_admin
from core.ambito_gestion import obtener_ambito_gestor

router = APIRouter(prefix="/api/v1/departamentos", tags=["departamentos"])


def _departamentos_del_profesor(profesor: dict) -> set[int]:
    departamentos = set(profesor.get("departamento_ids") or [])
    if not departamentos and profesor.get("departamento_id") is not None:
        departamentos.add(profesor["departamento_id"])
    return departamentos


# ═══════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════

class CreateDepartamentoRequest(BaseModel):
    """Request para crear departamento."""
    codigo: str
    nombre: str
    responsable_departamento_id: Optional[int] = None


class UpdateDepartamentoRequest(BaseModel):
    """Request para actualizar departamento."""
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    responsable_departamento_id: Optional[int] = None


class AsignarResponsableRequest(BaseModel):
    """Request para asignar responsable."""
    responsable_id: Optional[int] = None


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _verificar_acceso_departamento(current_user: dict, departamento_id: int, operacion: str):
    """
    Verifica acceso al departamento.
    
    SOLO ADMIN puede crear/editar/eliminar departamentos.
    Otros roles solo pueden ver su propio departamento.
    """
    rol = current_user["rol"]
    
    # ADMIN puede todo
    if rol == "admin":
        return True
    
    # Solo lectura para otros roles
    if operacion != "read":
        raise HTTPException(status_code=403, detail="Solo administradores pueden modificar departamentos")
    
    if rol == "responsable_departamento":
        departamentos = obtener_ambito_gestor(current_user["user_id"], rol)["departamentos"]
    elif rol == "responsable_area":
        departamentos = obtener_ambito_gestor(current_user["user_id"], rol)["departamentos"]
    else:
        usuario_autenticado = ProfesorRepository().find_by_usuario_id(current_user["user_id"])
        departamentos = _departamentos_del_profesor(usuario_autenticado) if usuario_autenticado else set()
    if departamento_id not in departamentos:
        raise HTTPException(status_code=403, detail="Solo puedes ver tu propio departamento")
    
    return True


def _filtrar_departamentos_por_acceso(current_user: dict, departamentos: List[dict]) -> List[dict]:
    """Filtra departamentos según acceso."""
    rol = current_user["rol"]
    
    if rol == "admin":
        return departamentos
    
    if rol in {"responsable_departamento", "responsable_area"}:
        departamentos_usuario = obtener_ambito_gestor(current_user["user_id"], rol)["departamentos"]
    else:
        usuario_autenticado = ProfesorRepository().find_by_usuario_id(current_user["user_id"])
        if not usuario_autenticado:
            return []
        departamentos_usuario = _departamentos_del_profesor(usuario_autenticado)
    return [d for d in departamentos if d.get("id") in departamentos_usuario]


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/", summary="Listar departamentos")
def get_departamentos(
    current_user: dict = Depends(get_current_user)  # ✅ Todos autenticados
):
    """
    Obtiene departamentos según permisos.
    
    **Roles permitidos:**
    - ADMIN: Todos los departamentos
    - Otros: Solo su propio departamento
    """
    repo = DepartamentoRepository()
    departamentos = repo.find_all()
    return _filtrar_departamentos_por_acceso(current_user, departamentos)


@router.get("/{departamento_id}", summary="Obtener departamento por ID")
def get_departamento(
    departamento_id: int,
    current_user: dict = Depends(get_current_user)  # ✅ Verificar acceso
):
    """
    Obtiene un departamento específico.
    
    **Roles permitidos:**
    - ADMIN: Cualquier departamento
    - Otros: Solo su propio departamento
    """
    _verificar_acceso_departamento(current_user, departamento_id, "read")
    
    repo = DepartamentoRepository()
    departamento = repo.find_by_id(departamento_id)
    if not departamento:
        raise HTTPException(
            status_code=404,
            detail=f"Departamento {departamento_id} no encontrado."
        )
    return departamento


@router.post("/", status_code=status.HTTP_201_CREATED, summary="Crear departamento")
def create_departamento(
    body: CreateDepartamentoRequest,
    current_user: dict = Depends(require_admin)  # ✅ SOLO ADMIN
):
    """
    Crea un nuevo departamento.
    
    **Roles permitidos:** ADMIN
    """
    repo = DepartamentoRepository()
    try:
        return repo.create(
            body.codigo,
            body.nombre,
            body.responsable_departamento_id,
        )
    except ConstraintViolation as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{departamento_id}", summary="Actualizar departamento")
def update_departamento(
    departamento_id: int,
    body: UpdateDepartamentoRequest,
    current_user: dict = Depends(require_admin)  # ✅ SOLO ADMIN
):
    """
    Actualiza un departamento.
    
    **Roles permitidos:** ADMIN
    """
    repo = DepartamentoRepository()
    
    updates = {}
    if body.codigo is not None:
        updates["codigo"] = body.codigo
    if body.nombre is not None:
        updates["nombre"] = body.nombre
    if "responsable_departamento_id" in body.model_fields_set:
        updates["responsable_departamento_id"] = body.responsable_departamento_id
    
    if not updates:
        raise HTTPException(status_code=400, detail="No se proporcionó ningún campo")
    
    try:
        return repo.update(departamento_id, updates)
    except DepartamentoNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConstraintViolation as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{departamento_id}/responsable", summary="Asignar responsable")
def asignar_responsable_departamento(
    departamento_id: int,
    body: AsignarResponsableRequest,
    current_user: dict = Depends(require_admin)  # ✅ SOLO ADMIN
):
    """
    Asigna o quita el responsable de un departamento.
    
    **Roles permitidos:** ADMIN
    """
    repo = DepartamentoRepository()
    try:
        return repo.asignar_responsable(departamento_id, body.responsable_id)
    except DepartamentoNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConstraintViolation as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{departamento_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar departamento")
def delete_departamento(
    departamento_id: int,
    current_user: dict = Depends(require_admin)  # ✅ SOLO ADMIN
):
    """
    Elimina un departamento.
    
    **Roles permitidos:** ADMIN
    """
    repo = DepartamentoRepository()
    try:
        repo.delete(departamento_id)
    except DepartamentoNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConstraintViolation as e:
        raise HTTPException(status_code=400, detail=str(e))
