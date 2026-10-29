"""Acceso a calendario académico y sesiones docentes planificadas."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, List, Optional

from db.connection import conexion_ctx, cursor_ctx


class PlanificacionDocenteRepository:
    def get_actividad(self, actividad_id: int) -> Optional[Dict[str, Any]]:
        with cursor_ctx() as cur:
            cur.execute("SELECT * FROM actividades WHERE id=%s", (actividad_id,))
            return cur.fetchone()

    def get_actividades_logicas(self, actividad_id: int) -> List[Dict[str, Any]]:
        """Devuelve las cuotas que forman el mismo grupo docente.

        Una actividad puede tener cuotas independientes por área. Comparten el
        horario oficial y las horas globales de actividad, aunque cada cola del
        solver solo gestione su cuota de área.
        """
        with cursor_ctx() as cur:
            cur.execute(
                """
                SELECT hermana.*
                FROM actividades AS origen
                JOIN actividades AS hermana
                  ON hermana.codigo=origen.codigo
                 AND hermana.tipo=origen.tipo
                 AND hermana.codigo_grupo=origen.codigo_grupo
                 AND hermana.curso_academico IS NOT DISTINCT FROM origen.curso_academico
                WHERE origen.id=%s
                ORDER BY hermana.id ASC
                """,
                (actividad_id,),
            )
            return list(cur.fetchall())

    def get_repartos_actividades(self, actividad_ids: Iterable[int]) -> List[Dict[str, Any]]:
        """Agrupa la cuota real de cada docente en un grupo compartido.

        Se conserva el primer reparto como vínculo trazable y su orden de
        confirmación. Si un profesor participa desde dos áreas, sus cuotas se
        suman pero el horario completo solo se muestra una vez.
        """
        ids = sorted({int(actividad_id) for actividad_id in actividad_ids})
        if not ids:
            return []
        with cursor_ctx() as cur:
            cur.execute(
                """
                SELECT MIN(rd.id) AS reparto_id, MIN(rd.actividad_id) AS actividad_id,
                       rd.profesor_id, SUM(rd.horas_asignadas) AS horas_asignadas,
                       profesor.nombre, profesor.apellidos
                FROM reparto_docente AS rd
                JOIN profesores AS profesor ON profesor.id=rd.profesor_id
                WHERE rd.actividad_id = ANY(%s)
                GROUP BY rd.profesor_id, profesor.nombre, profesor.apellidos
                ORDER BY MIN(rd.id) ASC
                """,
                (ids,),
            )
            return list(cur.fetchall())

    def get_periodos(self, curso_academico: str, tipo_estudio: str) -> List[Dict[str, Any]]:
        with cursor_ctx() as cur:
            cur.execute(
                """
                SELECT curso_academico, tipo_estudio, cuatrimestre, fecha_inicio, fecha_fin,
                       descripcion, fuente
                FROM calendario_docente_periodos
                WHERE curso_academico=%s AND tipo_estudio=%s
                ORDER BY fecha_inicio
                """,
                (curso_academico, tipo_estudio),
            )
            return list(cur.fetchall())

    def get_excepciones(self, curso_academico: str) -> List[Dict[str, Any]]:
        with cursor_ctx() as cur:
            cur.execute(
                """
                SELECT fecha, tipo, nombre, bloquea_docencia, fuente
                FROM calendario_docente_excepciones
                WHERE curso_academico=%s
                ORDER BY fecha, nombre
                """,
                (curso_academico,),
            )
            return list(cur.fetchall())

    def borrar_plan_actividades(self, actividad_ids: Iterable[int]) -> None:
        ids = sorted({int(actividad_id) for actividad_id in actividad_ids})
        if not ids:
            return
        with conexion_ctx() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM planificacion_docente_sesiones WHERE actividad_id = ANY(%s)", (ids,))

    def guardar_plan(self, actividad_id: int, curso_academico: str, sesiones: Iterable[Dict[str, Any]]) -> int:
        filas = list(sesiones)
        if not filas:
            return 0
        with conexion_ctx() as conn:
            cur = conn.cursor()
            cur.executemany(
                """
                INSERT INTO planificacion_docente_sesiones (
                    actividad_id, profesor_id, reparto_id, curso_academico, fecha,
                    hora_inicio, hora_fin, horas, orden_adjudicacion, orden_sesion,
                    estado, origen, observacion, horas_adjudicadas, es_horario_referencia
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, 'AUTOMATICO', %s, %s, %s
                )
                """,
                [
                    (
                        actividad_id, fila["profesor_id"], fila.get("reparto_id"), curso_academico,
                        fila.get("fecha"), fila.get("inicio"), fila.get("fin"), fila["horas"],
                        fila["orden_adjudicacion"], fila["orden_sesion"], fila["estado"],
                        fila.get("observacion"), fila.get("horas_adjudicadas"),
                        bool(fila.get("es_horario_referencia", False)),
                    )
                    for fila in filas
                ],
            )
        return len(filas)

    def get_cursos_profesor(self, profesor_id: int) -> List[str]:
        with cursor_ctx() as cur:
            cur.execute(
                """
                SELECT DISTINCT curso_academico
                FROM planificacion_docente_sesiones
                WHERE profesor_id=%s
                UNION
                SELECT DISTINCT COALESCE(a.curso_academico, '')
                FROM reparto_docente rd
                JOIN actividades a ON a.id=rd.actividad_id
                WHERE rd.profesor_id=%s
                ORDER BY 1 DESC
                """,
                (profesor_id, profesor_id),
            )
            return [fila["curso_academico"] for fila in cur.fetchall() if fila["curso_academico"]]

    def get_primer_dia_planificado(self, profesor_id: int, curso_academico: str) -> Optional[date]:
        with cursor_ctx() as cur:
            cur.execute(
                """
                SELECT MIN(fecha) AS fecha
                FROM planificacion_docente_sesiones
                WHERE profesor_id=%s AND curso_academico=%s AND estado='PLANIFICADA'
                """,
                (profesor_id, curso_academico),
            )
            fila = cur.fetchone()
            return fila["fecha"] if fila else None

    def get_sesiones_profesor(
        self, profesor_id: int, curso_academico: str, inicio: date, fin: date,
    ) -> List[Dict[str, Any]]:
        with cursor_ctx() as cur:
            cur.execute(
                """
                SELECT plan.id, plan.actividad_id, plan.reparto_id, plan.fecha,
                       plan.hora_inicio::TEXT AS hora_inicio, plan.hora_fin::TEXT AS hora_fin,
                       plan.horas, plan.orden_adjudicacion, plan.orden_sesion,
                       plan.estado, plan.origen, plan.observacion, plan.horas_adjudicadas,
                       plan.es_horario_referencia,
                       actividad.codigo, actividad.nombre_asignatura, actividad.tipo,
                       actividad.codigo_grupo, actividad.grupo, actividad.horas_actividad, actividad.area_id,
                       area.codigo AS area_codigo, area.nombre AS area_nombre
                FROM planificacion_docente_sesiones AS plan
                JOIN actividades AS actividad ON actividad.id=plan.actividad_id
                LEFT JOIN areas AS area ON area.id=actividad.area_id
                WHERE plan.profesor_id=%s AND plan.curso_academico=%s
                  AND plan.estado='PLANIFICADA' AND plan.fecha BETWEEN %s AND %s
                ORDER BY plan.fecha, plan.hora_inicio, plan.id
                """,
                (profesor_id, curso_academico, inicio, fin),
            )
            return list(cur.fetchall())

    def get_incidencias_profesor(self, profesor_id: int, curso_academico: str) -> List[Dict[str, Any]]:
        with cursor_ctx() as cur:
            cur.execute(
                """
                SELECT plan.id, plan.actividad_id, plan.reparto_id, plan.horas,
                       plan.horas_adjudicadas, plan.es_horario_referencia,
                       plan.estado, plan.observacion, actividad.codigo,
                       actividad.nombre_asignatura, actividad.tipo,
                         actividad.codigo_grupo, actividad.grupo, actividad.horas_actividad,
                         actividad.requiere_horario
                FROM planificacion_docente_sesiones AS plan
                JOIN actividades AS actividad ON actividad.id=plan.actividad_id
                WHERE plan.profesor_id=%s AND plan.curso_academico=%s
                  AND plan.estado <> 'PLANIFICADA'
                ORDER BY plan.orden_adjudicacion, plan.orden_sesion, plan.id
                """,
                (profesor_id, curso_academico),
            )
            return list(cur.fetchall())

    def get_excepciones_semana(self, curso_academico: str, inicio: date, fin: date) -> List[Dict[str, Any]]:
        with cursor_ctx() as cur:
            cur.execute(
                """
                SELECT fecha, tipo, nombre
                FROM calendario_docente_excepciones
                WHERE curso_academico=%s AND fecha BETWEEN %s AND %s
                ORDER BY fecha, nombre
                """,
                (curso_academico, inicio, fin),
            )
            return list(cur.fetchall())

    def get_cursos_con_calendario(self) -> List[str]:
        with cursor_ctx() as cur:
            cur.execute("SELECT DISTINCT curso_academico FROM calendario_docente_periodos ORDER BY curso_academico DESC")
            return [fila["curso_academico"] for fila in cur.fetchall()]
