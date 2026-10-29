import hashlib
import json
from collections import OrderedDict
from threading import RLock
from typing import Optional

from core.config import settings


class SolverCache:
    """Caché LRU acotada para resultados de factibilidad.

    Las respuestas del solver pueden contener repartos completos con cientos
    de líneas. Limitar solo el número de claves permitía que un conjunto de
    áreas grande retuviera una cantidad de memoria difícil de prever. Se
    mantiene el mismo contrato de lectura/escritura, pero se conservan los
    resultados utilizados más recientemente y se acota también su tamaño.
    """

    def __init__(self, max_size: int = 1000, max_bytes: int = 64 * 1024 * 1024):
        self._cache: OrderedDict[str, tuple[dict, int]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._max_size = max(1, int(max_size))
        self._max_bytes = max(1, int(max_bytes))
        self._current_bytes = 0
        self._lock = RLock()
    
    def _clave_eleccion(self, e: dict):
        return (
            e.get("profesor"),
            e.get("actividad_id"),
            e.get("codigo"),
            e.get("codigo_grupo"),
            e.get("tipo") or e.get("tipo_actividad"),
            float(e.get("horas", 0)),
        )
    
    def _generar_clave(
        self,
        elecciones_forzadas: list,
        profesores: list,
        actividades: list,
    ) -> str:
        elecciones_sorted = sorted(elecciones_forzadas, key=self._clave_eleccion)
        estado = {
            "elecciones": elecciones_sorted,
            "profesores": [
                (
                    p["id"],
                    p["nombre"],
                    float(p["horas_objetivo"]),
                    p.get("area_id"),
                    sorted(p.get("area_ids") or []),
                    p.get("disponibilidad_cuatrimestre", "AMBOS"),
                )
                for p in profesores
            ],
            "actividades": [
                (
                    a["id"],
                    a["codigo"],
                    a["codigo_grupo"],
                    a.get("tipo") or a.get("tipo_actividad"),
                    float(a["horas_totales"]),
                    a.get("area_id"),
                    a.get("duracion"),
                    a.get("turno"),
                    a.get("dias"),
                    a.get("horario"),
                    a.get("horario_confirmado"),
                    a.get("origen_horario"),
                )
                for a in actividades
            ],
        }
        json_str = json.dumps(estado, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(json_str.encode()).hexdigest()

    @staticmethod
    def _tamano_estimado(resultado: dict) -> int:
        """Estima los bytes retenidos por una entrada serializable del solver."""
        serializado = json.dumps(
            resultado,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        # Incluye una pequeña reserva por la clave y los objetos de la tabla.
        return len(serializado.encode("utf-8")) + 128

    def _expulsar_hasta_que_quepa(self, bytes_nuevos: int) -> None:
        while self._cache and (
            len(self._cache) >= self._max_size
            or self._current_bytes + bytes_nuevos > self._max_bytes
        ):
            _, (_, bytes_eliminados) = self._cache.popitem(last=False)
            self._current_bytes -= bytes_eliminados
    
    def get(
        self,
        elecciones_forzadas: list,
        profesores: list,
        actividades: list,
    ) -> Optional[dict]:
        clave = self._generar_clave(elecciones_forzadas, profesores, actividades)
        with self._lock:
            entrada = self._cache.get(clave)
            if entrada is not None:
                resultado, _ = entrada
                # LRU: la siguiente expulsión conserva los estados que la
                # interfaz acaba de consultar en lugar de los más antiguos.
                self._cache.move_to_end(clave)
                self._hits += 1
                copia = dict(resultado)
                copia["cached"] = True
                return copia

            self._misses += 1
            return None
    
    def set(
        self,
        elecciones_forzadas: list,
        profesores: list,
        actividades: list,
        resultado: dict,
    ):
        clave = self._generar_clave(elecciones_forzadas, profesores, actividades)
        guardar = dict(resultado)
        guardar["cached"] = False
        bytes_entrada = self._tamano_estimado(guardar)

        # Un único resultado excepcionalmente grande no debe desalojar toda
        # la caché ni mantenerse indefinidamente. Se devuelve normalmente al
        # cliente; simplemente no se reutiliza en memoria.
        if bytes_entrada > self._max_bytes:
            return

        with self._lock:
            anterior = self._cache.pop(clave, None)
            if anterior is not None:
                self._current_bytes -= anterior[1]
            self._expulsar_hasta_que_quepa(bytes_entrada)
            self._cache[clave] = (guardar, bytes_entrada)
            self._current_bytes += bytes_entrada
    
    def clear(self):
        with self._lock:
            self._cache.clear()
            self._current_bytes = 0
            self._hits = 0
            self._misses = 0
    
    def get_stats(self) -> dict:
        """Obtiene estadísticas seguras para la pantalla de administración."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                "size": len(self._cache),
                "bytes": self._current_bytes,
                "max_bytes": self._max_bytes,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{hit_rate:.1f}%",
            }


solver_cache = SolverCache(
    max_size=settings.SOLVER_CACHE_MAX_SIZE,
    max_bytes=settings.SOLVER_CACHE_MAX_BYTES,
)
