"""
Servicios - Capa de lógica de negocio.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .actividad_service import ActividadService
    from .ordenacion_service import OrdenacionService
    from .profesor_service import ProfesorService
    from .planificacion_docente_service import PlanificacionDocenteService

__all__ = ["OrdenacionService", "ProfesorService", "ActividadService", "PlanificacionDocenteService"]


def __getattr__(nombre: str):
    """Carga solo el servicio solicitado; el importador no necesita el solver."""
    if nombre == "OrdenacionService":
        from .ordenacion_service import OrdenacionService
        return OrdenacionService
    if nombre == "ProfesorService":
        from .profesor_service import ProfesorService
        return ProfesorService
    if nombre == "ActividadService":
        from .actividad_service import ActividadService
        return ActividadService
    if nombre == "PlanificacionDocenteService":
        from .planificacion_docente_service import PlanificacionDocenteService
        return PlanificacionDocenteService
    raise AttributeError(f"El módulo services no define {nombre!r}")
