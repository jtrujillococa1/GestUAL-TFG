"""
Repositories Package
"""
from repositories.profesor_repository import ProfesorRepository
from repositories.actividad_repository import ActividadRepository
from repositories.usuario_repository import UsuarioRepository
from repositories.area_repository import AreaRepository
from repositories.departamento_repository import DepartamentoRepository
from repositories.categoria_repository import CategoriaRepository
from repositories.reparto_repository import RepartoRepository
from repositories.mapeo_repository import MapeoRepository
from repositories.dashboard_repository import DashboardRepository
from repositories.planificacion_docente_repository import PlanificacionDocenteRepository

__all__ = [
    "ProfesorRepository",
    "ActividadRepository",
    "UsuarioRepository",
    "AreaRepository",
    "DepartamentoRepository",
    "CategoriaRepository",
    "RepartoRepository",
    "MapeoRepository",
    "DashboardRepository",
    "PlanificacionDocenteRepository",
]
