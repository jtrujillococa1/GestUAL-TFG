"""Repositorio de perfiles docentes y sus pertenencias a áreas."""
from datetime import date
from typing import Dict, List, Optional

from psycopg.errors import ForeignKeyViolation

from core.exceptions import ConstraintViolation, DuplicateResourceError, ProfesorNotFound
from db.connection import conexion_ctx, cursor_ctx
from repositories.base import BaseRepository, build_update_query
from domain.ordenacion.disponibilidad import (
    normalizar_disponibilidad,
    profesor_disponible_para_actividad,
)


_CAMPOS_PROFESOR = """
    p.id, p.usuario_id, p.nombre, p.apellidos, p.categoria,
    p.fecha_ingreso, p.carga_docente, p.area_id, p.es_psi, p.disponibilidad_cuatrimestre,
    p.identificador_origen, p.activo_origen,
    COALESCE((
        SELECT ARRAY_AGG(pa.area_id ORDER BY ar.codigo)
        FROM profesor_areas pa
        JOIN areas ar ON ar.id = pa.area_id
        WHERE pa.profesor_id = p.id
    ), ARRAY[]::INTEGER[]) AS area_ids,
    COALESCE((
        SELECT JSONB_AGG(JSONB_BUILD_OBJECT(
            'id', ar.id,
            'codigo', ar.codigo,
            'nombre', ar.nombre,
            'departamento_id', ar.departamento_id,
            'horas_objetivo', pa.horas_objetivo
        ) ORDER BY ar.codigo)
        FROM profesor_areas pa
        JOIN areas ar ON ar.id = pa.area_id
        WHERE pa.profesor_id = p.id
    ), '[]'::JSONB) AS areas,
    COALESCE((
        SELECT JSONB_OBJECT_AGG(pa.area_id::TEXT, pa.horas_objetivo)
        FROM profesor_areas pa
        WHERE pa.profesor_id = p.id
    ), '{}'::JSONB) AS horas_objetivo_por_area,
    COALESCE((
        SELECT JSONB_AGG(JSONB_BUILD_OBJECT(
            'codigo', ppa.asignatura_codigo,
            'nombre', COALESCE(nombre_asignatura.nombre_asignatura, ppa.asignatura_codigo),
            'prioridad', ppa.prioridad
        ) ORDER BY ppa.prioridad, ppa.asignatura_codigo)
        FROM profesor_prioridades_asignaturas ppa
        LEFT JOIN LATERAL (
            SELECT a.nombre_asignatura
            FROM actividades a
            WHERE a.codigo = ppa.asignatura_codigo
            ORDER BY a.nombre_asignatura NULLS LAST
            LIMIT 1
        ) nombre_asignatura ON TRUE
        WHERE ppa.profesor_id = p.id
    ), '[]'::JSONB) AS prioridades_asignaturas,
    COALESCE((
        SELECT ARRAY_AGG(DISTINCT ar.departamento_id ORDER BY ar.departamento_id)
        FROM profesor_areas pa
        JOIN areas ar ON ar.id = pa.area_id
        WHERE pa.profesor_id = p.id
    ), ARRAY[]::INTEGER[]) AS departamento_ids,
    (
        SELECT MIN(ar.departamento_id)
        FROM profesor_areas pa
        JOIN areas ar ON ar.id = pa.area_id
        WHERE pa.profesor_id = p.id
    ) AS departamento_id,
    EXISTS(SELECT 1 FROM reparto_docente rd WHERE rd.profesor_id = p.id) AS tiene_asignaciones
"""


def _fila_a_profesor(row: Dict) -> Dict:
    area_ids = list(row.get("area_ids") or [])
    if not area_ids and row.get("area_id") is not None:
        area_ids = [row["area_id"]]
    cargas_raw = row.get("horas_objetivo_por_area") or {}
    cargas_por_area = {int(area_id): float(horas) for area_id, horas in cargas_raw.items()}
    if not cargas_por_area and row.get("area_id") is not None:
        cargas_por_area[row["area_id"]] = float(row["carga_docente"])
    return {
        "id": row["id"],
        "usuario_id": row["usuario_id"],
        "nombre": row["nombre"],
        "apellidos": row["apellidos"],
        "categoria": row["categoria"],
        "fecha_ingreso": row["fecha_ingreso"],
        "carga_docente": float(row["carga_docente"]),
        # area_id se conserva como área principal para clientes antiguos.
        "area_id": row.get("area_id") or (area_ids[0] if area_ids else None),
        "area_ids": area_ids,
        "areas": row.get("areas") or [],
        "horas_objetivo_por_area": cargas_por_area,
        "prioridades_asignaturas": row.get("prioridades_asignaturas") or [],
        "departamento_id": row.get("departamento_id"),
        "departamento_ids": list(row.get("departamento_ids") or []),
        "es_psi": row["es_psi"],
        "disponibilidad_cuatrimestre": row.get("disponibilidad_cuatrimestre", "AMBOS"),
        "identificador_origen": row.get("identificador_origen"),
        "activo_origen": row.get("activo_origen"),
        "tiene_asignaciones": row.get("tiene_asignaciones", False),
    }


class ProfesorRepository(BaseRepository):
    """Gestiona perfiles docentes y su relación N:M con las áreas."""

    def __init__(self):
        super().__init__("profesores")

    def _buscar(self, where: str = "", parametros: tuple = ()) -> List[Dict]:
        with cursor_ctx() as cur:
            cur.execute(f"""
                SELECT {_CAMPOS_PROFESOR}
                FROM profesores p
                {where}
                ORDER BY p.apellidos ASC, p.nombre ASC
            """, parametros)
            return [_fila_a_profesor(row) for row in cur.fetchall()]

    def find_by_id(self, profesor_id: int) -> Optional[Dict]:
        resultados = self._buscar("WHERE p.id=%s", (profesor_id,))
        return resultados[0] if resultados else None

    def find_all(self, incluir_psi: bool = True) -> List[Dict]:
        filtro = "" if incluir_psi else "WHERE p.es_psi = FALSE"
        with cursor_ctx() as cur:
            cur.execute(f"""
                SELECT {_CAMPOS_PROFESOR}
                FROM profesores p
                JOIN categoria_pesos cp ON cp.categoria = p.categoria
                {filtro}
                ORDER BY cp.peso ASC, p.fecha_ingreso ASC, p.apellidos ASC, p.nombre ASC
            """)
            return [_fila_a_profesor(row) for row in cur.fetchall()]

    def find_for_ordenacion(self) -> List[Dict]:
        with cursor_ctx() as cur:
            cur.execute("""
                SELECT p.id, p.nombre, p.apellidos, p.carga_docente, p.categoria,
                       p.fecha_ingreso, p.area_id, p.es_psi, p.disponibilidad_cuatrimestre,
                       COALESCE((
                           SELECT ARRAY_AGG(pa.area_id ORDER BY pa.area_id)
                           FROM profesor_areas pa
                           WHERE pa.profesor_id = p.id
                       ), ARRAY[]::INTEGER[]) AS area_ids
                       , COALESCE((
                           SELECT JSONB_OBJECT_AGG(pa.area_id::TEXT, pa.horas_objetivo)
                           FROM profesor_areas pa
                           WHERE pa.profesor_id = p.id
                       ), '{}'::JSONB) AS horas_objetivo_por_area
                       , COALESCE((
                           SELECT JSONB_OBJECT_AGG(ppa.asignatura_codigo, ppa.prioridad)
                           FROM profesor_prioridades_asignaturas ppa
                           WHERE ppa.profesor_id = p.id
                       ), '{}'::JSONB) AS prioridades_asignaturas
                FROM profesores p
                JOIN categoria_pesos cp ON cp.categoria = p.categoria
                ORDER BY cp.peso ASC, p.fecha_ingreso ASC, p.apellidos ASC, p.nombre ASC
            """)
            return [
                {
                    "id": r["id"],
                    "nombre": r["nombre"],
                    "apellidos": r["apellidos"],
                    "horas_objetivo": float(r["carga_docente"]),
                    "carga_docente": float(r["carga_docente"]),
                    "categoria": r["categoria"],
                    "area_id": r["area_id"],
                    "area_ids": list(r.get("area_ids") or ([r["area_id"]] if r["area_id"] else [])),
                    "horas_objetivo_por_area": {
                        int(area_id): float(horas)
                        for area_id, horas in (r.get("horas_objetivo_por_area") or {}).items()
                    },
                    "prioridades_asignaturas": {
                        str(codigo): int(prioridad)
                        for codigo, prioridad in (r.get("prioridades_asignaturas") or {}).items()
                    },
                    "es_psi": r["es_psi"],
                    "disponibilidad_cuatrimestre": r.get("disponibilidad_cuatrimestre", "AMBOS"),
                }
                for r in cur.fetchall()
            ]

    def find_by_usuario_id(self, usuario_id: int) -> Optional[Dict]:
        resultados = self._buscar("WHERE p.usuario_id=%s", (usuario_id,))
        return resultados[0] if resultados else None

    def find_by_nombre_completo(self, nombre_completo: str) -> Optional[Dict]:
        if ", " not in nombre_completo:
            return None
        apellidos, nombre = nombre_completo.split(", ", 1)
        resultados = self._buscar("WHERE p.apellidos=%s AND p.nombre=%s", (apellidos, nombre))
        return resultados[0] if resultados else None

    @staticmethod
    def _normalizar_areas(area_id: Optional[int], area_ids: Optional[List[int]]) -> List[int]:
        resultado = list(dict.fromkeys(area_ids or ([] if area_id is None else [area_id])))
        if not resultado:
            raise ConstraintViolation("Selecciona al menos un área para el profesor.")
        if any(area < 1 for area in resultado):
            raise ConstraintViolation("El área indicada no es válida.")
        return resultado

    @staticmethod
    def _guardar_areas(
        cur, profesor_id: int, area_ids: List[int], carga_docente: float,
        area_principal: Optional[int], horas_objetivo_por_area: Optional[Dict[int, float]] = None,
    ) -> None:
        cur.execute("DELETE FROM profesor_areas WHERE profesor_id=%s", (profesor_id,))
        cargas = horas_objetivo_por_area or {}
        if not cargas:
            # Alta manual sin reparto explícito: distribuye la carga entre sus
            # áreas para no duplicarla en las colas concurrentes.
            base = round(float(carga_docente) / len(area_ids), 1)
            cargas = {area_id: base for area_id in area_ids}
            cargas[area_ids[0]] = round(float(carga_docente) - base * (len(area_ids) - 1), 1)
        if set(cargas) != set(area_ids) or any(float(horas) < 0 for horas in cargas.values()):
            raise ConstraintViolation("Indica una carga no negativa para cada área del profesor.")
        if abs(sum(float(horas) for horas in cargas.values()) - float(carga_docente)) > 0.01:
            raise ConstraintViolation("La suma de cargas por área debe coincidir con la carga docente total.")
        cur.executemany(
            "INSERT INTO profesor_areas (profesor_id, area_id, horas_objetivo) VALUES (%s, %s, %s)",
            [(profesor_id, area_id, cargas[area_id]) for area_id in area_ids],
        )

    @staticmethod
    def _guardar_prioridades_asignaturas(
        cur, profesor_id: int, asignaturas: Optional[List[str]], area_ids: List[int],
    ) -> None:
        """Guarda una lista ordenada de preferencias, válida en sus áreas."""
        codigos = list(dict.fromkeys(
            codigo.strip() for codigo in (asignaturas or []) if isinstance(codigo, str) and codigo.strip()
        ))
        if codigos:
            cur.execute(
                """
                SELECT DISTINCT codigo
                FROM actividades
                WHERE codigo = ANY(%s) AND area_id = ANY(%s)
                """,
                (codigos, area_ids),
            )
            encontrados = {fila['codigo'] if isinstance(fila, dict) else fila[0] for fila in cur.fetchall()}
            no_validos = [codigo for codigo in codigos if codigo not in encontrados]
            if no_validos:
                raise ConstraintViolation(
                    "Solo se pueden priorizar asignaturas de las áreas del profesor: "
                    + ", ".join(no_validos[:3])
                )
        cur.execute("DELETE FROM profesor_prioridades_asignaturas WHERE profesor_id=%s", (profesor_id,))
        if codigos:
            cur.executemany(
                """
                INSERT INTO profesor_prioridades_asignaturas (profesor_id, asignatura_codigo, prioridad)
                VALUES (%s, %s, %s)
                """,
                [(profesor_id, codigo, posicion) for posicion, codigo in enumerate(codigos, start=1)],
            )

    def create(
        self, usuario_id: Optional[int], nombre: str, apellidos: str, categoria: str,
        fecha_ingreso: date, carga_docente: float, area_id: Optional[int], es_psi: bool = False,
        area_ids: Optional[List[int]] = None, horas_objetivo_por_area: Optional[Dict[int, float]] = None,
        disponibilidad_cuatrimestre: str = "AMBOS", prioridades_asignaturas: Optional[List[str]] = None,
    ) -> Dict:
        areas = self._normalizar_areas(area_id, area_ids)
        try:
            with conexion_ctx() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM profesores WHERE nombre=%s AND apellidos=%s", (nombre, apellidos))
                if cur.fetchone():
                    raise DuplicateResourceError(f"Ya existe un profesor llamado '{apellidos}, {nombre}'.")
                cur.execute("""
                    INSERT INTO profesores (usuario_id, nombre, apellidos, categoria, fecha_ingreso,
                                           carga_docente, area_id, es_psi, disponibilidad_cuatrimestre)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    usuario_id, nombre, apellidos, categoria, fecha_ingreso,
                    carga_docente, areas[0], es_psi, normalizar_disponibilidad(disponibilidad_cuatrimestre),
                ))
                profesor_id = cur.fetchone()[0]
                self._guardar_areas(cur, profesor_id, areas, carga_docente, areas[0], horas_objetivo_por_area)
                self._guardar_prioridades_asignaturas(cur, profesor_id, prioridades_asignaturas, areas)
        except ForeignKeyViolation as exc:
            raise ConstraintViolation("La categoría, el usuario o una de las áreas indicadas no existe.") from exc
        return self.find_by_id(profesor_id)

    def update(self, profesor_id: int, updates: Dict) -> Dict:
        if not self.exists(profesor_id):
            raise ProfesorNotFound(f"Profesor {profesor_id} no encontrado.")
        if "disponibilidad_cuatrimestre" in updates:
            updates["disponibilidad_cuatrimestre"] = normalizar_disponibilidad(
                updates["disponibilidad_cuatrimestre"]
            )
            # Evita que un cambio de perfil deje confirmaciones o borradores
            # existentes en un periodo en que el docente ya no está disponible.
            perfil_futuro = {
                **(self.find_by_id(profesor_id) or {}),
                "disponibilidad_cuatrimestre": updates["disponibilidad_cuatrimestre"],
            }
            with cursor_ctx() as cur:
                cur.execute(
                    """
                    SELECT a.id, a.codigo, a.nombre_asignatura, a.duracion,
                           a.horario_detallado, 'confirmada' AS origen
                    FROM reparto_docente rd
                    JOIN actividades a ON a.id=rd.actividad_id
                    WHERE rd.profesor_id=%s
                    UNION ALL
                    SELECT a.id, a.codigo, a.nombre_asignatura, a.duracion,
                           a.horario_detallado, 'borrador' AS origen
                    FROM reparto_docente_borrador rb
                    JOIN actividades a ON a.id=rb.actividad_id
                    WHERE rb.profesor_id=%s
                    """,
                    (profesor_id, profesor_id),
                )
                incompatibles = [
                    actividad for actividad in cur.fetchall()
                    if not profesor_disponible_para_actividad(perfil_futuro, actividad)
                ]
            if incompatibles:
                actividad = incompatibles[0]
                etiqueta = actividad.get("nombre_asignatura") or actividad.get("codigo") or "una actividad"
                raise ConstraintViolation(
                    f"No se puede limitar la disponibilidad: ya tiene {actividad['origen']} "
                    f"en {etiqueta} fuera del cuatrimestre elegido. Devuelve o elimina esa adjudicación antes."
                )
        if "carga_docente" in updates:
            with cursor_ctx() as cur:
                cur.execute("SELECT COUNT(*) FROM reparto_docente WHERE profesor_id=%s", (profesor_id,))
                if cur.fetchone()["count"] > 0:
                    raise ConstraintViolation("No se puede cambiar la carga docente con asignaciones confirmadas.")

        area_ids = updates.pop("area_ids", None)
        horas_objetivo_por_area = updates.pop("horas_objetivo_por_area", None)
        prioridades_asignaturas = updates.pop("prioridades_asignaturas", None)
        existente = self.find_by_id(profesor_id)
        if area_ids is not None:
            areas = self._normalizar_areas(updates.get("area_id"), area_ids)
            area_principal = updates.get("area_id")
            if area_principal not in areas:
                area_principal = existente.get("area_id") if existente else None
            updates["area_id"] = area_principal if area_principal in areas else areas[0]
            # No permitir que un cambio de perfil invalide repartos ya
            # confirmados en alguna de las áreas que el docente impartía.
            with cursor_ctx() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM reparto_docente rd
                    JOIN actividades a ON a.id = rd.actividad_id
                    WHERE rd.profesor_id=%s
                      AND NOT (a.area_id = ANY(%s))
                    """,
                    (profesor_id, areas),
                )
                if cur.fetchone()["count"] > 0:
                    raise ConstraintViolation(
                        "No se pueden quitar áreas que tienen docencia confirmada para este profesor."
                    )
        elif horas_objetivo_por_area is not None:
            # También se puede reajustar únicamente el reparto de la carga,
            # sin cambiar las áreas de pertenencia del perfil.
            areas = self._normalizar_areas(existente.get("area_id"), existente.get("area_ids"))
        else:
            areas = None
        try:
            with conexion_ctx() as conn:
                cur = conn.cursor()
                if updates:
                    query, values = build_update_query("profesores", profesor_id, updates)
                    cur.execute(query, values)
                if areas is not None:
                    carga_final = float(updates.get("carga_docente", existente["carga_docente"]))
                    self._guardar_areas(cur, profesor_id, areas, carga_final, updates.get("area_id"), horas_objetivo_por_area)
                if prioridades_asignaturas is not None:
                    self._guardar_prioridades_asignaturas(
                        cur, profesor_id, prioridades_asignaturas,
                        areas or self._normalizar_areas(existente.get("area_id"), existente.get("area_ids")),
                    )
        except ForeignKeyViolation as exc:
            raise ConstraintViolation("La categoría, el usuario o una de las áreas indicadas no existe.") from exc
        return self.find_by_id(profesor_id)

    def delete(self, profesor_id: int) -> None:
        with conexion_ctx() as conn:
            cur = conn.cursor()
            if not self.exists(profesor_id):
                raise ProfesorNotFound(f"Profesor {profesor_id} no encontrado.")
            cur.execute("SELECT COUNT(*) FROM reparto_docente WHERE profesor_id=%s", (profesor_id,))
            if cur.fetchone()[0] > 0:
                raise ConstraintViolation("No se puede eliminar: tiene asignaciones confirmadas.")
            cur.execute("DELETE FROM reparto_docente_borrador WHERE profesor_id=%s", (profesor_id,))
            cur.execute("DELETE FROM profesores WHERE id=%s", (profesor_id,))

    def find_by_area(self, area_id: int) -> List[Dict]:
        return self._buscar(
            "WHERE EXISTS (SELECT 1 FROM profesor_areas pa WHERE pa.profesor_id=p.id AND pa.area_id=%s)",
            (area_id,),
        )

    def find_by_departamento(self, departamento_id: int) -> List[Dict]:
        return self._buscar("""
            WHERE EXISTS (
                SELECT 1
                FROM profesor_areas pa
                JOIN areas a ON a.id=pa.area_id
                WHERE pa.profesor_id=p.id AND a.departamento_id=%s
            )
        """, (departamento_id,))
