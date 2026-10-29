"""
Repository para mapeos entre nombres completos/IDs.
"""
from typing import Dict
from db.connection import cursor_ctx
from core.activity_values import normalizar_tipo_actividad
import threading


class MapeoRepository:
    """Gestiona mapeos bidireccionales entre profesores/actividades y sus IDs."""
    
    def __init__(self):
        self._cache: Dict = {}
        self._lock = threading.Lock()
    
    def get_mapeos(self) -> Dict:
        """Obtiene todos los mapeos (con cache)."""
        with self._lock:
            if self._cache:
                return self._cache
            mapeos = self._cargar_mapeos()
            self._cache = mapeos
            return mapeos
    
    def clear_cache(self) -> None:
        """Limpia el cache de mapeos."""
        with self._lock:
            self._cache.clear()
    
    def get_profesor_id(self, nombre_completo: str) -> int:
        """Obtiene ID del profesor por nombre completo."""
        mapeos = self.get_mapeos()
        return mapeos["prof_a_id"][nombre_completo]
    
    def get_actividad_id(self, codigo: str, codigo_grupo: str, tipo: str) -> int:
        """Obtiene ID de actividad por clave (codigo, grupo, tipo)."""
        mapeos = self.get_mapeos()
        return mapeos["actividad_a_id"][(codigo, codigo_grupo, tipo)]
    
    def _cargar_mapeos(self) -> Dict:
        """Carga mapeos desde la base de datos."""
        with cursor_ctx() as cur:
            # Mapeos de profesores
            cur.execute("SELECT id, nombre, apellidos FROM profesores")
            prof_a_id = {}
            id_a_prof = {}
            for r in cur.fetchall():
                nc = f"{r['apellidos']}, {r['nombre']}"
                prof_a_id[nc] = r["id"]
                id_a_prof[r["id"]] = nc
            
            # Mapeos de actividades
            cur.execute("SELECT id, codigo, tipo, codigo_grupo FROM actividades")
            actividad_a_id = {}
            id_a_actividad = {}
            for r in cur.fetchall():
                clave = (
                    r["codigo"],
                    r["codigo_grupo"],
                    normalizar_tipo_actividad(r["tipo"]),
                )
                actividad_a_id[clave] = r["id"]
                id_a_actividad[r["id"]] = clave
        
        return {
            "prof_a_id": prof_a_id,
            "actividad_a_id": actividad_a_id,
            "id_a_prof": id_a_prof,
            "id_a_actividad": id_a_actividad,
        }
