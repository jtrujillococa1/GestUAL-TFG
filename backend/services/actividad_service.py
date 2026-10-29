"""
Servicio de Actividades.
"""
from typing import List, Dict, Optional
from repositories import ActividadRepository, MapeoRepository
from solver.cache import solver_cache
from core.exceptions import ActividadNotFound


class ActividadService:
    def __init__(self):
        self.repo = ActividadRepository()
        self.mapeo_repo = MapeoRepository()
    
    def get_all(self) -> List[Dict]:
        return self.repo.find_all()
    
    def get_by_id(self, actividad_id: int) -> Dict:
        actividad = self.repo.find_by_id(actividad_id)
        if not actividad:
            raise ActividadNotFound(f"Actividad {actividad_id} no encontrada.")
        return actividad
    
    def create(
        self, codigo: str, tipo: str, codigo_grupo: str, grupo: str, idioma: Optional[str],
        duracion: str, turno: str, dias: Optional[str], horario: Optional[str],
        horas_asignatura: float, horas_actividad: float, horas_area: float, area_id: Optional[int],
        metadata: Optional[Dict] = None, requiere_horario: bool = True,
    ) -> Dict:
        actividad = self.repo.create(
            codigo, tipo, codigo_grupo, grupo, idioma, duracion, turno,
            dias, horario, horas_asignatura, horas_actividad, horas_area, area_id, metadata,
            requiere_horario,
        )
        solver_cache.clear()
        self.mapeo_repo.clear_cache()
        return actividad

    def create_many(
        self, codigo: str, tipo: str, codigo_grupo: str, grupo: str, idioma: Optional[str],
        duracion: str, turno: str, dias: str, horario: str,
        horas_asignatura: float, horas_actividad: float, horas_area: float, area_ids: List[int],
        metadata: Optional[Dict] = None, cuotas_por_area: Optional[Dict[int, float]] = None,
        requiere_horario: bool = True,
    ) -> List[Dict]:
        actividades = self.repo.create_many(
            codigo, tipo, codigo_grupo, grupo, idioma, duracion, turno, dias, horario,
            horas_asignatura, horas_actividad, horas_area, area_ids, metadata, cuotas_por_area,
            requiere_horario,
        )
        solver_cache.clear()
        self.mapeo_repo.clear_cache()
        return actividades
    
    def update(self, actividad_id: int, **kwargs) -> Dict:
        updates = {k: v for k, v in kwargs.items() if v is not None}
        if not updates:
            raise ValueError("No se proporcionó ningún campo para actualizar.")
        
        actividad = self.repo.update(actividad_id, updates)
        solver_cache.clear()
        self.mapeo_repo.clear_cache()
        # Si la actividad ya estaba adjudicada, un cambio de horario debe verse
        # inmediatamente en el calendario semanal. No se cambia ninguna hora
        # confirmada: solo se reconstruye su proyección por sesiones.
        if actividad.get("tiene_asignaciones"):
            try:
                from services.planificacion_docente_service import PlanificacionDocenteService
                PlanificacionDocenteService().regenerar_actividad(actividad_id)
            except Exception:
                pass
        return actividad
    
    def delete(self, actividad_id: int) -> None:
        self.repo.delete(actividad_id)
        solver_cache.clear()
        self.mapeo_repo.clear_cache()
