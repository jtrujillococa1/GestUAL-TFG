"""
API Routes Package
"""
from api.routes.actividades import router as actividades_router
from api.routes.admin import router as admin_router
from api.routes.areas import router as areas_router
from api.routes.auth import router as auth_router
from api.routes.categorias import router as categorias_routes
from api.routes.dashboard import router as dashboard_router  
from api.routes.departamentos import router as departamentos_router
from api.routes.ordenacion import router as ordenacion_router
from api.routes.planificacion_docente import router as planificacion_docente_router
from api.routes.profesores import router as profesores_router
from api.routes.usuarios import router as usuarios_router

__all__ = [
    "actividades_router",
    "admin_router",
    "areas_router",
    "auth_router",
    "categorias_router",
    "dashboard_router",  
    "departamentos_router",
    "ordenacion_router",
    "planificacion_docente_router",
    "profesores_router",
    "usuarios_router",
]   
