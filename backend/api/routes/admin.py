"""
API Routes - Administración.

Endpoints administrativos: cache, reset, configuración.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from solver.cache import solver_cache
from repositories import AreaRepository, DepartamentoRepository, MapeoRepository
from services import OrdenacionService
from core.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get('/avisos-turno', summary='Estado de los avisos por correo')
def get_avisos_turno(current_user: dict = Depends(require_admin)):
    from db.connection import cursor_ctx
    from services.avisos_turno import correo_configurado
    with cursor_ctx() as cur:
        cur.execute('SELECT id,area_id,profesor_id,estado,intentos,creado_en,enviado_en,error FROM avisos_turno_correo ORDER BY id DESC LIMIT 100')
        return {'correo_configurado': correo_configurado(), 'avisos': cur.fetchall()}


class ResetOrdenacionAlcanceRequest(BaseModel):
    """Alcance explícito de un reinicio administrativo de ordenación."""

    tipo: Literal["area", "departamento"]
    id: int


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS - CACHE (SOLO ADMIN)
# ═══════════════════════════════════════════════════════════════

@router.get("/cache/stats", summary="Estadísticas de cache")
def get_cache_stats(
    current_user: dict = Depends(require_admin)  # ✅ SOLO ADMIN
):
    """
    Obtiene estadísticas del cache del solver.
    
    **Roles permitidos:** ADMIN
    """
    stats = solver_cache.get_stats()
    return {
        "size": stats["size"],
        "hits": stats["hits"],
        "misses": stats["misses"],
        "hit_rate": round(
            stats["hits"] / (stats["hits"] + stats["misses"]) * 100, 2
        ) if (stats["hits"] + stats["misses"]) > 0 else 0.0,
    }


@router.post("/cache/clear", summary="Limpiar cache")
def clear_cache(
    current_user: dict = Depends(require_admin)  # ✅ SOLO ADMIN
):
    """
    Limpia completamente el cache del solver.
    
    **Roles permitidos:** ADMIN
    """
    solver_cache.clear()
    return {"ok": True, "mensaje": "Cache limpiado."}


@router.post("/cache/clear-mapeos", summary="Limpiar cache de mapeos")
def clear_mapeos_cache(
    current_user: dict = Depends(require_admin)  # ✅ SOLO ADMIN
):
    """
    Limpia el cache de mapeos de IDs.
    
    **Roles permitidos:** ADMIN
    """
    mapeo_repo = MapeoRepository()
    mapeo_repo.clear_cache()
    return {"ok": True, "mensaje": "Cache de mapeos limpiado."}


@router.post("/cache/clear-all", summary="Limpiar todos los caches")
def clear_all_caches(
    current_user: dict = Depends(require_admin)  # ✅ SOLO ADMIN
):
    """
    Limpia todos los caches del sistema.
    
    **Roles permitidos:** ADMIN
    """
    solver_cache.clear()
    mapeo_repo = MapeoRepository()
    mapeo_repo.clear_cache()
    return {"ok": True, "mensaje": "Todos los caches limpiados."}


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS - RESET (SOLO ADMIN)
# ═══════════════════════════════════════════════════════════════

@router.post("/reset-ordenacion", summary="Reiniciar ordenación")
def reset_ordenacion(
    current_user: dict = Depends(require_admin)  # ✅ SOLO ADMIN
):
    """
    Reinicia completamente la ordenación.
    
    **CUIDADO:** Elimina todas las confirmaciones y borradores.
    
    **Roles permitidos:** ADMIN
    """
    service = OrdenacionService()
    return service.reset_ordenacion()


@router.post("/reset-ordenacion/alcance", summary="Reiniciar ordenación por área o departamento")
def reset_ordenacion_por_alcance(
    body: ResetOrdenacionAlcanceRequest,
    current_user: dict = Depends(require_admin),
):
    """Elimina borradores y confirmaciones del área o departamento indicado.

    El identificador se resuelve en el servidor para impedir que un cliente
    amplíe el alcance del reinicio. Solo el administrador puede ejecutarlo.
    """
    area_repo = AreaRepository()

    if body.tipo == "area":
        area = area_repo.find_by_id(body.id)
        if not area:
            raise HTTPException(status_code=404, detail="Área no encontrada.")
        areas = [area]
        etiqueta = f"el área {area['codigo']} · {area['nombre']}"
    else:
        departamento = DepartamentoRepository().find_by_id(body.id)
        if not departamento:
            raise HTTPException(status_code=404, detail="Departamento no encontrado.")
        areas = area_repo.find_by_departamento(body.id)
        etiqueta = f"el departamento {departamento['codigo']} · {departamento['nombre']}"

    resultado = OrdenacionService().reset_ordenacion_por_areas([area["id"] for area in areas])
    return {
        **resultado,
        "tipo": body.tipo,
        "id": body.id,
        "areas_afectadas": len(areas),
        "mensaje": (
            f"Ordenación reiniciada para {etiqueta}: "
            f"{resultado['confirmaciones_eliminadas']} confirmaciones y "
            f"{resultado['borradores_eliminados']} borradores eliminados."
        ),
    }


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS - SISTEMA (PÚBLICO O AUTH)
# ═══════════════════════════════════════════════════════════════

@router.get("/health-check", summary="Health check completo")
def health_check():
    """
    Verifica el estado del sistema.
    
    **Acceso:** PÚBLICO (para monitoreo)
    """
    from db.connection import cursor_ctx
    
    # Verificar BD
    try:
        with cursor_ctx() as cur:
            cur.execute("SELECT 1")
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    # Verificar cache
    cache_stats = solver_cache.get_stats()
    
    # Verificar ordenación
    try:
        service = OrdenacionService()
        estado = service.get_estado()
        ordenacion_status = {
            "profesor_actual": estado.profesor_actual,
            "terminada": estado.ordenacion_terminada,
            "completados": len(estado.profesores_completados),
            "pendientes": len(estado.profesores_pendientes),
        }
    except Exception as e:
        ordenacion_status = f"error: {str(e)}"
    
    return {
        "database": db_status,
        "cache": {
            "size": cache_stats["size"],
            "operational": True,
        },
        "ordenacion": ordenacion_status,
    }
