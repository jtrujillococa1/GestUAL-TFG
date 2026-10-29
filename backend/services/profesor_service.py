"""
Servicio de Profesores.
"""

from typing import List, Dict, Optional
from datetime import date

# ✅ IMPORTS CORREGIDOS
from repositories import ProfesorRepository, MapeoRepository
from solver.cache import solver_cache
from core.exceptions import ProfesorNotFound


class ProfesorService:
    def __init__(self):
        # ✅ INSTANCIAS CORREGIDAS
        self.repo = ProfesorRepository()
        self.mapeo_repo = MapeoRepository()
    
    def get_all(self, incluir_psi: bool = True) -> List[Dict]:
        return self.repo.find_all(incluir_psi=incluir_psi)
    
    def get_by_id(self, profesor_id: int) -> Dict:
        profesor = self.repo.find_by_id(profesor_id)
        if not profesor:
            raise ProfesorNotFound(f"Profesor {profesor_id} no encontrado.")
        return profesor
    
    def create(
        self,
        usuario_id: Optional[int],
        nombre: str,
        apellidos: str,
        categoria: str,
        fecha_ingreso: date,
        carga_docente: float,
        area_id: Optional[int],
        area_ids: Optional[List[int]] = None,
        horas_objetivo_por_area: Optional[Dict[int, float]] = None,
        es_psi: bool = False,
        disponibilidad_cuatrimestre: str = "AMBOS",
        prioridades_asignaturas: Optional[List[str]] = None,
    ) -> Dict:
        profesor = self.repo.create(
            usuario_id, nombre, apellidos, categoria,
            fecha_ingreso, carga_docente, area_id, es_psi, area_ids, horas_objetivo_por_area,
            disponibilidad_cuatrimestre, prioridades_asignaturas,
        )
        solver_cache.clear()
        self.mapeo_repo.clear_cache()  # ✅ USAR INSTANCIA
        return profesor
    
    def update(self, profesor_id: int, **kwargs) -> Dict:
        updates = {k: v for k, v in kwargs.items() if v is not None}
        if not updates:
            raise ValueError("No se proporciono ningun campo para actualizar.")
        
        profesor = self.repo.update(profesor_id, updates)
        solver_cache.clear()
        self.mapeo_repo.clear_cache()  # ✅ USAR INSTANCIA
        return profesor
    
    def delete(self, profesor_id: int) -> None:
        self.repo.delete(profesor_id)
        solver_cache.clear()
        self.mapeo_repo.clear_cache()  # ✅ USAR INSTANCIA
