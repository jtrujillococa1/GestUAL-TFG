"""
API Routes - Categorías Docentes.
Endpoints para gestión de categorías y sus pesos.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from repositories import CategoriaRepository
from core.exceptions import ValidationError
from core.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/v1/categorias", tags=["categorias"])


# ═══════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════

class UpdatePesoRequest(BaseModel):
    """Request para actualizar peso de categoría."""
    peso: int


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/", summary="Listar categorías")
def get_categorias(
    current_user: dict = Depends(get_current_user)  # ✅ Todos autenticados
):
    """
    Obtiene todas las categorías con sus pesos.
    
    **Roles permitidos:** TODOS (autenticados)
    
    Ordenadas por peso (menor peso = mayor prioridad).
    """
    repo = CategoriaRepository()
    return repo.find_all()


@router.get("/prioridad", summary="Orden de prioridad")
def get_prioridad_ordenada(
    current_user: dict = Depends(get_current_user)  # ✅ Todos autenticados
):
    """
    Obtiene el orden de prioridad de las categorías.
    
    **Roles permitidos:** TODOS (autenticados)
    """
    repo = CategoriaRepository()
    return {
        "orden": repo.get_prioridad_ordenada(),
        "descripcion": "Menor peso = Mayor prioridad (eligen primero)"
    }


@router.get("/{categoria}", summary="Obtener categoría")
def get_categoria(
    categoria: str,
    current_user: dict = Depends(get_current_user)  # ✅ Todos autenticados
):
    """
    Obtiene información de una categoría específica.
    
    **Roles permitidos:** TODOS (autenticados)
    """
    repo = CategoriaRepository()
    try:
        return repo.find_by_categoria(categoria)
    except ValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{categoria}/peso", summary="Actualizar peso")
def update_peso_categoria(
    categoria: str,
    body: UpdatePesoRequest,
    current_user: dict = Depends(require_admin)  # ✅ SOLO ADMIN
):
    """
    Actualiza el peso de una categoría.
    
    **Roles permitidos:** ADMIN
    
    El peso determina la prioridad en la ordenación:
    - Peso menor = mayor prioridad (eligen primero)
    - Peso mayor = menor prioridad (eligen después)
    """
    repo = CategoriaRepository()
    try:
        from solver.cache import solver_cache
        from repositories import MapeoRepository
        
        resultado = repo.update_peso(categoria, body.peso)
        
        # Invalidar cachés porque cambia el orden de turnos
        solver_cache.clear()
        mapeo_repo = MapeoRepository()
        mapeo_repo.clear_cache()
        
        return resultado
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))