"""
Repository para actividades docentes.
"""
import json
from typing import List, Dict, Optional
from db.connection import conexion_ctx, cursor_ctx
from repositories.base import BaseRepository, build_update_query
from core.exceptions import ActividadNotFound, DuplicateResourceError, ConstraintViolation
from core.activity_values import normalizar_tipo_actividad, normalizar_turno


CAMPOS_ACADEMICOS = (
    "nombre_asignatura", "tipo_estudio", "codigo_plan", "nombre_plan",
    "codigo_centro", "nombre_centro", "ciclo", "curso", "caracter",
    "actividad_oficial_id", "nombre_actividad", "codigo_grupo_oficial",
    "curso_academico", "horario_confirmado", "origen_horario",
    "horario_detallado", "fuente_horario",
)


def _fila_a_actividad(row: Dict) -> Dict:
    """Convierte una fila de BD a dict de actividad."""
    return {
        "id": row["id"],
        "codigo": row["codigo"],
        "tipo": normalizar_tipo_actividad(row["tipo"]),
        "codigo_grupo": row["codigo_grupo"],
        "grupo": row["grupo"],
        "idioma": row.get("idioma"),
        "duracion": row["duracion"],
        "turno": normalizar_turno(row["turno"]),
        "dias": row.get("dias"),
        "horario": row.get("horario"),
        "requiere_horario": row.get("requiere_horario", True),
        "horario_confirmado": row.get("horario_confirmado", False),
        "origen_horario": row.get("origen_horario", "PENDIENTE"),
        "horario_detallado": row.get("horario_detallado") or [],
        "fuente_horario": row.get("fuente_horario"),
        "horas_asignatura": float(row["horas_asignatura"]),
        "horas_actividad": float(row["horas_actividad"]),
        "horas_area": float(row["horas_area"]),
        "area_id": row.get("area_id"),
        "area_codigo": row.get("area_codigo"),
        "area_nombre": row.get("area_nombre"),
        "area_ids": list(row.get("area_ids") or ([row["area_id"]] if row.get("area_id") else [])),
        "areas": row.get("areas") or [],
        "horas_asignadas": float(row.get("horas_asignadas", 0)),
        "horas_pendientes": float(row.get("horas_pendientes", 0)),
        "tiene_asignaciones": row.get("tiene_asignaciones", False),
        **{
            campo: row.get(campo)
            for campo in CAMPOS_ACADEMICOS
            if campo not in {"horario_confirmado", "origen_horario", "horario_detallado", "fuente_horario"}
        },
    }


class ActividadRepository(BaseRepository):
    """Gestiona operaciones CRUD de actividades."""
    
    def __init__(self):
        super().__init__("actividades")
    
    def find_by_id(self, actividad_id: int) -> Optional[Dict]:
        """Obtiene una actividad por ID."""
        with cursor_ctx() as cur:
            cur.execute("""
                SELECT a.*, ar.codigo AS area_codigo, ar.nombre AS area_nombre,
                       COALESCE((SELECT ARRAY_AGG(aa.area_id ORDER BY aa.area_id) FROM actividad_areas aa WHERE aa.actividad_id=a.id), ARRAY[]::INTEGER[]) AS area_ids,
                       COALESCE((SELECT JSONB_AGG(JSONB_BUILD_OBJECT('id', aa.area_id, 'codigo', ar2.codigo, 'nombre', ar2.nombre) ORDER BY ar2.codigo) FROM actividad_areas aa JOIN areas ar2 ON ar2.id=aa.area_id WHERE aa.actividad_id=a.id), '[]'::JSONB) AS areas,
                       COALESCE(SUM(rd.horas_asignadas), 0) AS horas_asignadas,
                       a.horas_area - COALESCE(SUM(rd.horas_asignadas), 0) AS horas_pendientes,
                       COUNT(rd.id) > 0 AS tiene_asignaciones
                FROM actividades a
                LEFT JOIN reparto_docente rd ON rd.actividad_id = a.id
                LEFT JOIN areas ar ON ar.id = a.area_id
                WHERE a.id=%s
                GROUP BY a.id, ar.id
            """, (actividad_id,))
            row = cur.fetchone()
            return _fila_a_actividad(row) if row else None
    
    def find_all(self) -> List[Dict]:
        """Obtiene todas las actividades."""
        with cursor_ctx() as cur:
            cur.execute("""
                SELECT a.*, ar.codigo AS area_codigo, ar.nombre AS area_nombre,
                       COALESCE((SELECT ARRAY_AGG(aa.area_id ORDER BY aa.area_id) FROM actividad_areas aa WHERE aa.actividad_id=a.id), ARRAY[]::INTEGER[]) AS area_ids,
                       COALESCE((SELECT JSONB_AGG(JSONB_BUILD_OBJECT('id', aa.area_id, 'codigo', ar2.codigo, 'nombre', ar2.nombre) ORDER BY ar2.codigo) FROM actividad_areas aa JOIN areas ar2 ON ar2.id=aa.area_id WHERE aa.actividad_id=a.id), '[]'::JSONB) AS areas,
                       COALESCE(SUM(rd.horas_asignadas), 0) AS horas_asignadas,
                       a.horas_area - COALESCE(SUM(rd.horas_asignadas), 0) AS horas_pendientes,
                       COUNT(rd.id) > 0 AS tiene_asignaciones
                FROM actividades a
                LEFT JOIN reparto_docente rd ON rd.actividad_id = a.id
                LEFT JOIN areas ar ON ar.id = a.area_id
                GROUP BY a.id, ar.id
                ORDER BY a.codigo ASC, a.codigo_grupo ASC, a.tipo ASC
            """)
            return [_fila_a_actividad(row) for row in cur.fetchall()]
    
    def find_for_ordenacion(self) -> List[Dict]:
        """Obtiene actividades en formato para el algoritmo de ordenacion."""
        with cursor_ctx() as cur:
            cur.execute("""
                SELECT *
                FROM actividades
                ORDER BY id ASC
            """)
            return [
                {
                    "id": r["id"],
                    "codigo": r["codigo"],
                    "nombre_asignatura": r.get("nombre_asignatura"),
                    "tipo": normalizar_tipo_actividad(r["tipo"]),
                    "tipo_actividad": normalizar_tipo_actividad(r["tipo"]),
                    "codigo_grupo": r["codigo_grupo"],
                    "grupo": r["grupo"],
                    "idioma": r["idioma"],
                    "duracion": r["duracion"],
                    "cuatrimestre": r["duracion"],
                    "turno": normalizar_turno(r["turno"]),
                    "dias": r["dias"],
                    "horario": r["horario"],
                    "requiere_horario": r.get("requiere_horario", True),
                    "horario_confirmado": r.get("horario_confirmado", False),
                    "origen_horario": r.get("origen_horario", "PENDIENTE"),
                    "horario_detallado": r.get("horario_detallado") or [],
                    "fuente_horario": r.get("fuente_horario"),
                    "horas_asignatura": float(r["horas_asignatura"]),
                    "horas_actividad": float(r["horas_actividad"]),
                    "horas_area": float(r["horas_area"]),
                    # La ordenación cubre la cuota del área, no el total de una
                    # actividad que puede compartirse con otras áreas.
                    "horas_totales": float(r["horas_area"]),
                    "area_id": r["area_id"],
                }
                for r in cur.fetchall()
            ]
    
    def create(
        self, codigo: str, tipo: str, codigo_grupo: str, grupo: str, idioma: Optional[str],
        duracion: str, turno: str, dias: Optional[str], horario: Optional[str],
        horas_asignatura: float, horas_actividad: float, horas_area: float, area_id: Optional[int],
        metadata: Optional[Dict] = None, requiere_horario: bool = True,
    ) -> Dict:
        """Crea una nueva actividad."""
        return self.create_many(
            codigo, tipo, codigo_grupo, grupo, idioma, duracion, turno, dias, horario,
            horas_asignatura, horas_actividad, horas_area, [area_id], metadata,
            requiere_horario=requiere_horario,
        )[0]

    def create_many(
        self, codigo: str, tipo: str, codigo_grupo: str, grupo: str, idioma: Optional[str],
        duracion: str, turno: str, dias: str, horario: str,
        horas_asignatura: float, horas_actividad: float, horas_area: float, area_ids: List[int],
        metadata: Optional[Dict] = None, cuotas_por_area: Optional[Dict[int, float]] = None,
        requiere_horario: bool = True,
    ) -> List[Dict]:
        """Crea las cuotas de una actividad para una o varias áreas de forma atómica."""
        metadata = metadata or {}
        campos = list(CAMPOS_ACADEMICOS)
        valores_metadata = [
            metadata.get("horario_confirmado", False) if campo == "horario_confirmado"
            else metadata.get("origen_horario", "PENDIENTE") if campo == "origen_horario"
            else json.dumps(metadata.get(campo) or []) if campo == "horario_detallado"
            else metadata.get(campo)
            for campo in campos
        ]
        columnas_metadata = ", ".join(campos)
        marcadores_metadata = ", ".join(["%s"] * len(campos))
        nuevos_ids: List[int] = []

        with conexion_ctx() as conn:
            cur = conn.cursor()
            for area_id in area_ids:
                horas_cuota = float((cuotas_por_area or {}).get(area_id, horas_area))
                cur.execute("""
                    SELECT id FROM actividades
                    WHERE codigo=%s AND tipo=%s AND codigo_grupo=%s
                      AND area_id IS NOT DISTINCT FROM %s
                      AND COALESCE(curso_academico, '') = COALESCE(%s, '')
                """, (codigo, tipo, codigo_grupo, area_id, metadata.get("curso_academico")))
                if cur.fetchone():
                    raise DuplicateResourceError(
                        f"Ya existe la actividad {codigo} - {codigo_grupo} ({tipo}) en esa área y curso."
                    )
                cur.execute(f"""
                    INSERT INTO actividades (codigo, tipo, codigo_grupo, grupo, idioma, duracion, turno,
                                           dias, horario, requiere_horario, horas_asignatura, horas_actividad, horas_area, area_id,
                                           {columnas_metadata})
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, {marcadores_metadata})
                    RETURNING id
                """, (codigo, tipo, codigo_grupo, grupo, idioma, duracion, turno, dias, horario, requiere_horario,
                       horas_asignatura, horas_actividad, horas_cuota, area_id, *valores_metadata))
                nuevo_id = cur.fetchone()[0]
                cur.executemany(
                    "INSERT INTO actividad_areas (actividad_id, area_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    [(nuevo_id, area_relacionada) for area_relacionada in area_ids],
                )
                nuevos_ids.append(nuevo_id)
        return [self.find_by_id(nuevo_id) for nuevo_id in nuevos_ids]
    
    def update(self, actividad_id: int, updates: Dict) -> Dict:
        """Actualiza una actividad."""
        if not self.exists(actividad_id):
            raise ActividadNotFound(f"Actividad {actividad_id} no encontrada.")

        # Al declarar una actividad sin horario fijo se eliminan las franjas
        # anteriores. Así una práctica externa no conserva un horario sintético
        # y no puede generar un solape falso.
        if updates.get("requiere_horario") is False:
            updates.update({
                "dias": None,
                "horario": None,
                "horario_confirmado": False,
                "origen_horario": "NO_APLICA",
                "horario_detallado": [],
                "fuente_horario": None,
            })

        # psycopg no adapta de forma uniforme los diccionarios/listas a JSONB
        # entre las versiones soportadas por el proyecto. Serializar aquí hace
        # que tanto el formulario como la carga oficial tengan el mismo camino.
        if "horario_detallado" in updates:
            updates["horario_detallado"] = json.dumps(updates["horario_detallado"] or [])

        area_ids = updates.pop("area_ids", None)
        if area_ids is not None:
            area_ids = list(dict.fromkeys(area_ids))
            if not area_ids or any(area_id < 1 for area_id in area_ids):
                raise ConstraintViolation("Selecciona al menos un área válida para la actividad.")
        
        if {"horas_actividad", "horas_area"}.intersection(updates):
            with cursor_ctx() as cur:
                cur.execute("SELECT COUNT(*) FROM reparto_docente WHERE actividad_id=%s", (actividad_id,))
                if cur.fetchone()["count"] > 0:
                    raise ConstraintViolation("No se pueden cambiar las horas con asignaciones confirmadas.")

        if "area_id" in updates:
            with cursor_ctx() as cur:
                cur.execute("SELECT area_id FROM actividades WHERE id=%s", (actividad_id,))
                area_actual = cur.fetchone()["area_id"]
                if updates["area_id"] != area_actual:
                    cur.execute("SELECT COUNT(*) FROM reparto_docente WHERE actividad_id=%s", (actividad_id,))
                    if cur.fetchone()["count"] > 0:
                        raise ConstraintViolation(
                            "No se puede cambiar el área de cuota con asignaciones confirmadas."
                        )
        
        with conexion_ctx() as conn:
            cur = conn.cursor()
            if updates:
                query, values = build_update_query("actividades", actividad_id, updates)
                cur.execute(query, values)
            if area_ids is not None:
                cur.execute("SELECT area_id FROM actividades WHERE id=%s", (actividad_id,))
                area_principal = cur.fetchone()[0]
                # Cada fila conserva su cuota en area_id; el puente expresa las
                # áreas académicas compartidas que se usan en perfiles y filtros.
                if area_principal not in area_ids:
                    area_ids.insert(0, area_principal)
                cur.execute("DELETE FROM actividad_areas WHERE actividad_id=%s", (actividad_id,))
                cur.executemany(
                    "INSERT INTO actividad_areas (actividad_id, area_id) VALUES (%s, %s)",
                    [(actividad_id, area_id) for area_id in area_ids],
                )
        return self.find_by_id(actividad_id)
    
    def delete(self, actividad_id: int) -> None:
        """Elimina una actividad."""
        with conexion_ctx() as conn:
            cur = conn.cursor()
            if not self.exists(actividad_id):
                raise ActividadNotFound(f"Actividad {actividad_id} no encontrada.")
            
            cur.execute("SELECT COUNT(*) FROM reparto_docente WHERE actividad_id=%s", (actividad_id,))
            if cur.fetchone()[0] > 0:
                raise ConstraintViolation("No se puede eliminar: tiene asignaciones confirmadas.")
            
            cur.execute("DELETE FROM reparto_docente_borrador WHERE actividad_id=%s", (actividad_id,))
            cur.execute("DELETE FROM actividades WHERE id=%s", (actividad_id,))
   
    def find_by_area(self, area_id: int) -> List[Dict]:
        """Obtener todas las actividades de un área"""
        with cursor_ctx() as cur:
            cur.execute("""
                SELECT a.*, ar.codigo AS area_codigo, ar.nombre AS area_nombre,
                       COALESCE((SELECT ARRAY_AGG(aa.area_id ORDER BY aa.area_id) FROM actividad_areas aa WHERE aa.actividad_id=a.id), ARRAY[]::INTEGER[]) AS area_ids,
                       COALESCE((SELECT JSONB_AGG(JSONB_BUILD_OBJECT('id', aa.area_id, 'codigo', ar2.codigo, 'nombre', ar2.nombre) ORDER BY ar2.codigo) FROM actividad_areas aa JOIN areas ar2 ON ar2.id=aa.area_id WHERE aa.actividad_id=a.id), '[]'::JSONB) AS areas,
                       COALESCE(SUM(rd.horas_asignadas), 0) AS horas_asignadas,
                       a.horas_area - COALESCE(SUM(rd.horas_asignadas), 0) AS horas_pendientes,
                       COUNT(rd.id) > 0 AS tiene_asignaciones
                FROM actividades a
                LEFT JOIN reparto_docente rd ON rd.actividad_id = a.id
                LEFT JOIN areas ar ON ar.id = a.area_id
                WHERE EXISTS (
                    SELECT 1 FROM actividad_areas aa
                    WHERE aa.actividad_id = a.id AND aa.area_id = %s
                )
                GROUP BY a.id, ar.id
                ORDER BY a.codigo ASC, a.tipo ASC
            """, (area_id,))
            return [_fila_a_actividad(row) for row in cur.fetchall()]
