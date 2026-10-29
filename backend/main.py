"""
FastAPI Application - Ordenacion Docente.
"""
import multiprocessing
import sys

# Fix para Windows + Python 3.13
if sys.platform == "win32":
    try:
        multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError:
        pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from core.config import settings
except ImportError as e:
    print(f"❌ Error importando config: {e}")
    sys.exit(1)

# Importar routers
try:
    from api.routes.actividades import router as actividades_router
    from api.routes.admin import router as admin_router
    from api.routes.areas import router as areas_router
    from api.routes.auth import router as auth_router
    from api.routes.categorias import router as categorias_router
    from api.routes.dashboard import router as dashboard_router
    from api.routes.departamentos import router as departamentos_router
    from api.routes.ordenacion import router as ordenacion_router
    from api.routes.planificacion_docente import router as planificacion_docente_router
    from api.routes.importacion import router as importacion_router
    from api.routes.profesores import router as profesores_router
    from api.routes.usuarios import router as usuarios_router
except ImportError as e:
    print(f"❌ Error importando routers: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="API para gestión de ordenación docente con OR-Tools.",
    # ✅ QUITAR redirect_slashes=False
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(auth_router)
app.include_router(usuarios_router)
app.include_router(profesores_router)
app.include_router(actividades_router)
app.include_router(areas_router)
app.include_router(departamentos_router)
app.include_router(categorias_router)
app.include_router(ordenacion_router)
app.include_router(planificacion_docente_router)
app.include_router(importacion_router)
app.include_router(dashboard_router)
app.include_router(admin_router)


@app.get("/", tags=["root"])
def root():
    """Endpoint raíz - Información de la API."""
    return {
        "message": "Ordenación Docente API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "status": "running",
    }


@app.get("/health", tags=["health"])
def health_check():
    """Health check básico."""
    return {
        "status": "healthy",
        "version": "1.0.0",
    }


@app.on_event("startup")
async def startup_event():
    """Evento de inicio de la aplicación."""
    from services.avisos_turno import iniciar
    iniciar()
    print("\n" + "=" * 60)
    print(f"🚀 {settings.PROJECT_NAME} v1.0.0")
    print("=" * 60)
    print(f"📝 Documentación: http://localhost:8000/docs")
    print(f"🔍 Redoc: http://localhost:8000/redoc")
    print(f"💚 Health: http://localhost:8000/health")
    print("=" * 60 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    """Evento de cierre de la aplicación."""
    from services.avisos_turno import detener
    detener()
    # Libera de forma explícita las conexiones reutilizables antes de terminar
    # el proceso. No modifica datos ni reglas de negocio.
    from db.connection import cerrar_pool
    cerrar_pool()
    print("\n" + "=" * 60)
    print("🛑 Cerrando aplicación...")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
