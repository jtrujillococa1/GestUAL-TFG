"""
Repository para reparto docente (confirmadas y borrador).
"""
import json
from typing import Any, Dict, List, Optional
from db.connection import conexion_ctx, cursor_ctx
from core.exceptions import ConcurrentModification, ConstraintViolation, OrdenacionClosed
from core.activity_values import normalizar_tipo_actividad, normalizar_turno


def _nc(nombre: str, apellidos: str) -> str:
    """Formatea nombre completo."""
    return f"{apellidos}, {nombre}"


class RepartoRepository:
    """Gestiona asignaciones confirmadas y borradores."""

    @staticmethod
    def _bloquear_control_area(
        cur, area_id: int, version_esperada: Optional[int] = None,
        permitir_cerrada: bool = False,
    ) -> Dict[str, Any]:
        """Bloquea el estado de un área y valida una versión de pantalla.

        El bloqueo y el incremento de versión se realizan en la misma
        transacción que el cambio de borrador o confirmación. Dos pestañas que
        partan de la misma versión no pueden sobrescribirse silenciosamente.
        """
        cur.execute(
            "INSERT INTO ordenacion_areas_control (area_id) VALUES (%s) ON CONFLICT (area_id) DO NOTHING",
            (area_id,),
        )
        cur.execute(
            "SELECT version, estado FROM ordenacion_areas_control WHERE area_id=%s FOR UPDATE",
            (area_id,),
        )
        version, estado = cur.fetchone()
        cur.execute('SELECT iniciada FROM ordenacion_areas_control WHERE area_id=%s', (area_id,))
        if not cur.fetchone()[0] and not permitir_cerrada:
            raise OrdenacionClosed('El área está en preparación. Un gestor debe validar e iniciar la ordenación.')
        if version_esperada is not None and int(version) != int(version_esperada):
            raise ConcurrentModification(
                "La ordenación cambió en otra sesión. Recarga el área antes de continuar.",
                {"version_actual": int(version)},
            )
        if estado == "CERRADA" and not permitir_cerrada:
            raise OrdenacionClosed("La ordenación de esta área está cerrada. Reábrela para realizar correcciones.")
        return {"version": int(version), "estado": estado}

    @staticmethod
    def _avanzar_version(cur, area_id: int) -> int:
        cur.execute(
            """
            UPDATE ordenacion_areas_control
            SET version=version+1, actualizado_en=NOW()
            WHERE area_id=%s
            RETURNING version
            """,
            (area_id,),
        )
        return int(cur.fetchone()[0])

    @staticmethod
    def _registrar_evento(
        cur, area_id: int, tipo: str, usuario_id: Optional[int] = None,
        detalle: Optional[Dict[str, Any]] = None,
    ) -> None:
        cur.execute(
            """
            INSERT INTO ordenacion_eventos (area_id, usuario_id, tipo, detalle)
            VALUES (%s, %s, %s, %s::jsonb)
            """,
            (area_id, usuario_id, tipo, json.dumps(detalle or {}, ensure_ascii=False)),
        )

    def get_control_area(self, area_id: int) -> Dict[str, Any]:
        with cursor_ctx() as cur:
            cur.execute(
                "SELECT version, estado, iniciada, cerrado_por_usuario_id, cerrado_en, actualizado_en "
                "FROM ordenacion_areas_control WHERE area_id=%s",
                (area_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"area_id": area_id, "version": 0, "cerrada": False, "estado": "ABIERTA", "iniciada": False}
            return {
                "area_id": area_id,
                "version": int(row["version"]),
                "estado": row["estado"],
                "iniciada": row['iniciada'],
                "cerrada": row["estado"] == "CERRADA",
                "cerrado_por_usuario_id": row.get("cerrado_por_usuario_id"),
                "cerrado_en": row.get("cerrado_en"),
                "actualizado_en": row.get("actualizado_en"),
            }

    def get_eventos_area(self, area_id: int, limite: int = 100) -> List[Dict[str, Any]]:
        with cursor_ctx() as cur:
            cur.execute(
                """
                SELECT id, area_id, usuario_id, tipo, detalle, creado_en
                FROM ordenacion_eventos
                WHERE area_id=%s
                ORDER BY creado_en DESC, id DESC
                LIMIT %s
                """,
                (area_id, limite),
            )
            return list(cur.fetchall())

    def crear_propuesta_conflicto(
        self, area_id: int, profesor_bloqueado_id: int, version_base: int,
        propuesta: Dict[str, Any], usuario_id: Optional[int],
    ) -> Dict[str, Any]:
        """Guarda una propuesta sin tocar ningún reparto confirmado."""
        with conexion_ctx() as conn:
            cur = conn.cursor()
            self._bloquear_control_area(cur, area_id, version_base, permitir_cerrada=True)
            # Se conservan alternativas de la misma versión para compararlas.
            # El bloqueo del área serializa generación y aprobación.
            cur.execute(
                """
                UPDATE ordenacion_conflictos_propuestas
                SET estado='OBSOLETA', decidida_en=NOW()
                WHERE area_id=%s AND estado='PENDIENTE' AND version_base<>%s
                """,
                (area_id, version_base),
            )
            cur.execute("SELECT propuesta FROM ordenacion_conflictos_propuestas WHERE area_id=%s AND version_base=%s AND profesor_bloqueado_id=%s", (area_id, version_base, profesor_bloqueado_id))
            def firma(plan):
                return sorted((int(f['profesor_id']), int(f['actividad_id']), round(float(f['horas']), 1)) for f in plan)
            nueva_firma = firma(propuesta.get('plan', []))
            if any(firma((fila[0] or {}).get('plan', [])) == nueva_firma for fila in cur.fetchall()):
                raise ConstraintViolation('Esta alternativa ya se ha calculado en otra petición. Busca otra alternativa.')
            cur.execute(
                """
                INSERT INTO ordenacion_conflictos_propuestas
                    (area_id, profesor_bloqueado_id, version_base, propuesta, creada_por_usuario_id)
                VALUES (%s, %s, %s, %s::jsonb, %s)
                RETURNING id, creada_en
                """,
                (area_id, profesor_bloqueado_id, version_base, json.dumps(propuesta, ensure_ascii=False), usuario_id),
            )
            propuesta_id, creada_en = cur.fetchone()
            self._registrar_evento(cur, area_id, "CONFLICTO_PROPUESTO", usuario_id, {
                "propuesta_id": int(propuesta_id),
                "profesor_bloqueado_id": profesor_bloqueado_id,
                "movimientos": propuesta.get("impacto", {}).get("movimientos", 0),
            })
            return {
                "id": int(propuesta_id), "area_id": area_id, "version_base": version_base,
                "estado": "PENDIENTE", "propuesta": propuesta, "creada_en": creada_en,
            }

    def find_propuestas_conflicto(self, area_id: int, limite: Optional[int] = None) -> List[Dict[str, Any]]:
        with cursor_ctx() as cur:
            cur.execute(
                """
                SELECT propuesta.id, propuesta.area_id, propuesta.profesor_bloqueado_id,
                       profesor.nombre, profesor.apellidos, propuesta.version_base,
                       propuesta.estado, propuesta.propuesta, propuesta.creada_en,
                       propuesta.decidida_en, propuesta.motivo_rechazo
                FROM ordenacion_conflictos_propuestas AS propuesta
                JOIN profesores AS profesor ON profesor.id=propuesta.profesor_bloqueado_id
                WHERE propuesta.area_id=%s
                ORDER BY CASE WHEN propuesta.estado='PENDIENTE' THEN 0 ELSE 1 END,
                         propuesta.creada_en DESC, propuesta.id DESC
                LIMIT %s
                """,
                (area_id, limite),
            )
            return [
                {
                    "id": int(fila["id"]), "area_id": int(fila["area_id"]),
                    "profesor_bloqueado_id": int(fila["profesor_bloqueado_id"]),
                    "profesor_bloqueado": _nc(fila["nombre"], fila["apellidos"]),
                    "version_base": int(fila["version_base"]), "estado": fila["estado"],
                    "propuesta": fila["propuesta"], "creada_en": fila["creada_en"],
                    "decidida_en": fila["decidida_en"], "motivo_rechazo": fila["motivo_rechazo"],
                }
                for fila in cur.fetchall()
            ]

    def decidir_propuesta_conflicto(
        self, propuesta_id: int, area_id: int, aprobar: bool, usuario_id: Optional[int],
        motivo_rechazo: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Aprueba o rechaza una propuesta de forma atómica."""
        with conexion_ctx() as conn:
            cur = conn.cursor()
            # Bloquear el único ámbito afectado antes de leer o sustituir sus
            # repartos. La versión base se valida de nuevo tras cargar la
            # propuesta para asegurar que sigue vigente.
            self._bloquear_control_area(cur, area_id, permitir_cerrada=True)
            cur.execute(
                """
                SELECT estado, version_base, propuesta
                FROM ordenacion_conflictos_propuestas
                WHERE id=%s AND area_id=%s
                FOR UPDATE
                """,
                (propuesta_id, area_id),
            )
            fila = cur.fetchone()
            if not fila:
                raise ConstraintViolation("La propuesta de conflicto no existe en esta área.")
            estado_propuesta, version_base, propuesta_guardada = fila
            if estado_propuesta != "PENDIENTE":
                raise ConstraintViolation("La propuesta ya fue decidida o ha quedado obsoleta.")

            control = self._bloquear_control_area(
                cur, area_id, int(version_base), permitir_cerrada=True,
            )
            if not aprobar:
                cur.execute(
                    """
                    UPDATE ordenacion_conflictos_propuestas
                    SET estado='RECHAZADA', decidida_por_usuario_id=%s,
                        decidida_en=NOW(), motivo_rechazo=%s
                    WHERE id=%s
                    """,
                    (usuario_id, motivo_rechazo, propuesta_id),
                )
                self._registrar_evento(cur, area_id, "CONFLICTO_RECHAZADO", usuario_id, {
                    "propuesta_id": propuesta_id, "motivo": motivo_rechazo,
                })
                return {"id": propuesta_id, "area_id": area_id, "estado": "RECHAZADA", "version": control["version"]}

            propuesta = propuesta_guardada or {}
            plan = propuesta.get("plan") if isinstance(propuesta, dict) else None
            if not isinstance(plan, list) or not plan:
                raise ConstraintViolation("La propuesta no contiene un reparto aplicable.")
            actividades_horas: Dict[int, float] = {}
            cur.execute("SELECT id, horas_area FROM actividades WHERE area_id=%s", (area_id,))
            for actividad in cur.fetchall():
                actividades_horas[int(actividad[0])] = float(actividad[1])
            cur.execute(
                """
                SELECT profesor.id,
                       COALESCE(relacion.horas_objetivo,
                                CASE WHEN profesor.area_id=%s THEN profesor.carga_docente ELSE 0 END) AS horas_objetivo
                FROM profesores AS profesor
                LEFT JOIN profesor_areas AS relacion
                  ON relacion.profesor_id=profesor.id AND relacion.area_id=%s
                WHERE relacion.area_id=%s OR profesor.area_id=%s
                """,
                (area_id, area_id, area_id, area_id),
            )
            objetivos_profesor = {
                int(profesor[0]): float(profesor[1])
                for profesor in cur.fetchall()
                if float(profesor[1]) > 0.01
            }

            acumulado: Dict[int, float] = {}
            acumulado_profesor: Dict[int, float] = {}
            filas_plan: List[tuple[int, int, float]] = []
            for linea in plan:
                try:
                    profesor_id = int(linea["profesor_id"])
                    actividad_id = int(linea["actividad_id"])
                    horas = round(float(linea["horas"]), 2)
                except (KeyError, TypeError, ValueError) as exc:
                    raise ConstraintViolation("La propuesta contiene una línea no válida.") from exc
                if actividad_id not in actividades_horas or profesor_id not in objetivos_profesor or horas <= 0:
                    raise ConstraintViolation("La propuesta contiene una actividad fuera del área o sin horas válidas.")
                acumulado[actividad_id] = round(acumulado.get(actividad_id, 0.0) + horas, 2)
                acumulado_profesor[profesor_id] = round(acumulado_profesor.get(profesor_id, 0.0) + horas, 2)
                filas_plan.append((profesor_id, actividad_id, horas))
            if any(abs(acumulado.get(actividad_id, 0.0) - horas_area) > 0.01 for actividad_id, horas_area in actividades_horas.items()):
                raise ConstraintViolation("La propuesta ya no cubre exactamente las cuotas del área.")
            if any(abs(acumulado_profesor.get(profesor_id, 0.0) - objetivo) > 0.01 for profesor_id, objetivo in objetivos_profesor.items()):
                raise ConstraintViolation("La propuesta ya no mantiene las cargas individuales del área.")

            cur.execute(
                """
                DELETE FROM planificacion_docente_sesiones AS planificacion
                USING actividades AS actividad
                WHERE planificacion.actividad_id=actividad.id AND actividad.area_id=%s
                """,
                (area_id,),
            )
            cur.execute(
                """
                DELETE FROM reparto_docente_borrador AS borrador
                USING actividades AS actividad
                WHERE borrador.actividad_id=actividad.id AND actividad.area_id=%s
                """,
                (area_id,),
            )
            cur.execute(
                """
                DELETE FROM reparto_docente AS reparto
                USING actividades AS actividad
                WHERE reparto.actividad_id=actividad.id AND actividad.area_id=%s
                """,
                (area_id,),
            )
            cur.executemany(
                "INSERT INTO reparto_docente (profesor_id, actividad_id, horas_asignadas) VALUES (%s, %s, %s)",
                filas_plan,
            )
            cur.execute(
                """
                UPDATE ordenacion_revisiones
                SET estado='RESUELTA', resuelta_en=NOW(), resuelta_por_usuario_id=%s
                WHERE area_id=%s AND estado='PENDIENTE'
                """,
                (usuario_id, area_id),
            )
            if control["estado"] == "CERRADA":
                cur.execute(
                    """
                    UPDATE ordenacion_areas_control
                    SET estado='ABIERTA', cerrado_por_usuario_id=NULL, cerrado_en=NULL,
                        actualizado_en=NOW()
                    WHERE area_id=%s
                    """,
                    (area_id,),
                )
            version = self._avanzar_version(cur, area_id)
            cur.execute("UPDATE ordenacion_conflictos_propuestas SET estado='OBSOLETA', decidida_en=NOW() WHERE area_id=%s AND estado='PENDIENTE' AND id<>%s", (area_id, propuesta_id))
            cur.execute(
                """
                UPDATE ordenacion_conflictos_propuestas
                SET estado='APROBADA', decidida_por_usuario_id=%s, decidida_en=NOW()
                WHERE id=%s
                """,
                (usuario_id, propuesta_id),
            )
            self._registrar_evento(cur, area_id, "CONFLICTO_APROBADO", usuario_id, {
                "propuesta_id": propuesta_id,
                "movimientos": propuesta.get("impacto", {}).get("movimientos", 0),
                "profesores_afectados": propuesta.get("impacto", {}).get("profesores_afectados", 0),
            })
            return {"id": propuesta_id, "area_id": area_id, "estado": "APROBADA", "version": version}

    def contar_borradores_area(self, area_id: int) -> int:
        with cursor_ctx() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM reparto_docente_borrador borrador
                JOIN actividades actividad ON actividad.id=borrador.actividad_id
                WHERE actividad.area_id=%s
                """,
                (area_id,),
            )
            return int(cur.fetchone()["total"])

    def get_revision_pendiente(self, area_id: int) -> Optional[Dict[str, Any]]:
        """Devuelve la corrección más antigua que debe atender el área.

        Las revisiones tienen prioridad sobre la cola ordinaria, pero no
        cambian su orden ni afectan a ninguna otra área.
        """
        with cursor_ctx() as cur:
            cur.execute(
                """
                SELECT revision.id, revision.area_id, revision.profesor_id,
                       revision.actividad_id, revision.horas_devuelta, revision.motivo,
                       profesor.nombre, profesor.apellidos
                FROM ordenacion_revisiones AS revision
                JOIN profesores AS profesor ON profesor.id=revision.profesor_id
                WHERE revision.area_id=%s AND revision.estado='PENDIENTE'
                ORDER BY revision.creada_en ASC, revision.id ASC
                LIMIT 1
                """,
                (area_id,),
            )
            fila = cur.fetchone()
            if not fila:
                return None
            return {
                "id": int(fila["id"]),
                "area_id": int(fila["area_id"]),
                "profesor_id": int(fila["profesor_id"]),
                "actividad_id": int(fila["actividad_id"]),
                "horas_devuelta": float(fila["horas_devuelta"]),
                "motivo": fila["motivo"],
                "profesor": _nc(fila["nombre"], fila["apellidos"]),
            }

    def find_revisiones_pendientes_profesor(self, area_id: int, profesor_id: int) -> List[Dict[str, Any]]:
        """Devuelve todas las líneas devueltas que un docente debe corregir.

        Una persona puede tener más de una devolución antes de confirmar su
        turno de revisión. Se devuelven todas para que el borrador permita
        sustituir cada una de ellas, no solo la revisión más antigua.
        """
        with cursor_ctx() as cur:
            cur.execute(
                """
                SELECT revision.id, revision.actividad_id, revision.horas_devuelta, revision.motivo,
                       actividad.nombre_asignatura, actividad.codigo, actividad.grupo
                FROM ordenacion_revisiones AS revision
                JOIN actividades AS actividad ON actividad.id=revision.actividad_id
                WHERE revision.area_id=%s AND revision.profesor_id=%s AND revision.estado='PENDIENTE'
                ORDER BY revision.creada_en ASC, revision.id ASC
                """,
                (area_id, profesor_id),
            )
            return [
                {
                    "id": int(fila["id"]),
                    "actividad_id": int(fila["actividad_id"]),
                    "horas_devuelta": float(fila["horas_devuelta"]),
                    "motivo": fila["motivo"],
                    "nombre_asignatura": fila["nombre_asignatura"],
                    "codigo": fila["codigo"],
                    "grupo": fila["grupo"],
                }
                for fila in cur.fetchall()
            ]

    def contar_revisiones_pendientes(self, area_id: int) -> int:
        with cursor_ctx() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total FROM ordenacion_revisiones WHERE area_id=%s AND estado='PENDIENTE'",
                (area_id,),
            )
            return int(cur.fetchone()["total"])
    
    def find_all_confirmadas(self) -> List[Dict]:
        """Obtiene todas las asignaciones confirmadas."""
        with cursor_ctx() as cur:
            cur.execute(f"""
                SELECT p.id AS profesor_id, a.id AS actividad_id, p.nombre, p.apellidos,
                       a.codigo, a.nombre_asignatura, a.tipo, a.codigo_grupo, a.grupo,
                       rd.horas_asignadas
                FROM reparto_docente rd
                JOIN profesores p ON rd.profesor_id = p.id
                JOIN actividades a ON rd.actividad_id = a.id
                ORDER BY rd.id ASC
            """)
            return [
                {
                    "profesor_id": r["profesor_id"],
                    "actividad_id": r["actividad_id"],
                    "profesor": _nc(r["nombre"], r["apellidos"]),
                    "codigo": r["codigo"],
                    "nombre_asignatura": r.get("nombre_asignatura"),
                    "tipo": normalizar_tipo_actividad(r["tipo"]),
                    "tipo_actividad": normalizar_tipo_actividad(r["tipo"]),
                    "codigo_grupo": r["codigo_grupo"],
                    "grupo": r["grupo"],
                    "horas": float(r["horas_asignadas"]),
                }
                for r in cur.fetchall()
            ]

    def find_adjudicaciones_por_actividades(self, actividad_ids: List[int]) -> List[Dict]:
        """Obtiene los docentes y horas confirmadas de cada actividad.

        Los borradores se excluyen deliberadamente: esta consulta es la vista
        fiable de adjudicaciones ya confirmadas para consulta y exportación.
        """
        if not actividad_ids:
            return []
        with cursor_ctx() as cur:
            cur.execute(
                """
                SELECT rd.actividad_id, p.id AS profesor_id, p.nombre, p.apellidos,
                       p.categoria, SUM(rd.horas_asignadas) AS horas_asignadas
                FROM reparto_docente rd
                JOIN profesores p ON p.id=rd.profesor_id
                WHERE rd.actividad_id = ANY(%s)
                GROUP BY rd.actividad_id, p.id, p.nombre, p.apellidos, p.categoria
                ORDER BY rd.actividad_id, p.apellidos, p.nombre
                """,
                (actividad_ids,),
            )
            return [
                {
                    "actividad_id": fila["actividad_id"],
                    "profesor_id": fila["profesor_id"],
                    "nombre": fila["nombre"],
                    "apellidos": fila["apellidos"],
                    "categoria": fila["categoria"],
                    "horas_asignadas": float(fila["horas_asignadas"]),
                }
                for fila in cur.fetchall()
            ]
    
    def find_borrador_by_profesor(self, nombre_completo: str, area_id: int | None = None) -> List[Dict]:
        """Obtiene el borrador de un profesor por nombre completo."""
        partes = nombre_completo.split(",", 1)
        apellidos = partes[0].strip()
        nombre = partes[1].strip() if len(partes) > 1 else ""
        
        with cursor_ctx() as cur:
            filtro_area = " AND a.area_id=%s" if area_id is not None else ""
            cur.execute(f"""
                SELECT a.id AS actividad_id, p.nombre, p.apellidos,
                       a.codigo, a.nombre_asignatura, a.tipo, a.codigo_grupo, a.grupo,
                       a.idioma, a.duracion, a.turno, a.dias, a.horario, a.requiere_horario,
                       a.horario_confirmado, a.origen_horario, a.horario_detallado, a.fuente_horario,
                       b.horas_asignadas
                FROM reparto_docente_borrador b
                JOIN profesores p ON b.profesor_id = p.id
                JOIN actividades a ON b.actividad_id = a.id
                WHERE p.apellidos=%s AND p.nombre=%s {filtro_area}
                ORDER BY b.id ASC
            """, (apellidos, nombre, area_id) if area_id is not None else (apellidos, nombre))
            
            return [
                {
                    "actividad_id": r["actividad_id"],
                    "profesor": _nc(r["nombre"], r["apellidos"]),
                    "codigo": r["codigo"],
                    "nombre_asignatura": r.get("nombre_asignatura"),
                    "tipo": normalizar_tipo_actividad(r["tipo"]),
                    "tipo_actividad": normalizar_tipo_actividad(r["tipo"]),
                    "codigo_grupo": r["codigo_grupo"],
                    "grupo": r["grupo"],
                    "idioma": r["idioma"],
                    "duracion": r["duracion"],
                    "turno": normalizar_turno(r["turno"]),
                    "dias": r["dias"],
                    "horario": r["horario"],
                    "requiere_horario": r.get("requiere_horario", True),
                    "horario_confirmado": r.get("horario_confirmado", False),
                    "origen_horario": r.get("origen_horario", "PENDIENTE"),
                    "horario_detallado": r.get("horario_detallado") or [],
                    "fuente_horario": r.get("fuente_horario"),
                    "horas": float(r["horas_asignadas"]),
                }
                for r in cur.fetchall()
            ]
    
    def upsert_borrador(
        self, profesor_id: int, actividad_id: int, horas: float,
        area_id: Optional[int] = None, version_esperada: Optional[int] = None,
        usuario_id: Optional[int] = None,
    ) -> Optional[int]:
        """Inserta o actualiza una linea del borrador."""
        with conexion_ctx() as conn:
            cur = conn.cursor()
            if area_id is not None:
                self._bloquear_control_area(cur, area_id, version_esperada)
            cur.execute("""
                INSERT INTO reparto_docente_borrador (profesor_id, actividad_id, horas_asignadas)
                VALUES (%s, %s, %s)
                ON CONFLICT (profesor_id, actividad_id)
                DO UPDATE SET horas_asignadas=EXCLUDED.horas_asignadas, creado_en=NOW()
            """, (profesor_id, actividad_id, horas))
            if area_id is not None:
                version = self._avanzar_version(cur, area_id)
                self._registrar_evento(cur, area_id, "BORRADOR_ACTUALIZADO", usuario_id, {
                    "profesor_id": profesor_id, "actividad_id": actividad_id, "horas": float(horas),
                })
                return version
        return None
    
    def delete_borrador_linea(
        self, profesor_id: int, actividad_id: int,
        area_id: Optional[int] = None, version_esperada: Optional[int] = None,
        usuario_id: Optional[int] = None,
    ) -> Optional[int]:
        """Elimina una linea del borrador."""
        with conexion_ctx() as conn:
            cur = conn.cursor()
            if area_id is not None:
                self._bloquear_control_area(cur, area_id, version_esperada)
            cur.execute("""
                DELETE FROM reparto_docente_borrador
                WHERE profesor_id=%s AND actividad_id=%s
            """, (profesor_id, actividad_id))
            if area_id is not None:
                version = self._avanzar_version(cur, area_id)
                self._registrar_evento(cur, area_id, "BORRADOR_ELIMINADO", usuario_id, {
                    "profesor_id": profesor_id, "actividad_id": actividad_id,
                })
                return version
        return None
    
    def clear_borrador_profesor(
        self, profesor_id: int, area_id: int | None = None,
        version_esperada: Optional[int] = None, usuario_id: Optional[int] = None,
    ) -> Optional[int]:
        """Limpia todo el borrador de un profesor."""
        with conexion_ctx() as conn:
            cur = conn.cursor()
            if area_id is None:
                cur.execute("DELETE FROM reparto_docente_borrador WHERE profesor_id=%s", (profesor_id,))
            else:
                self._bloquear_control_area(cur, area_id, version_esperada)
                cur.execute("""
                    DELETE FROM reparto_docente_borrador b
                    USING actividades a
                    WHERE b.actividad_id=a.id AND b.profesor_id=%s AND a.area_id=%s
                """, (profesor_id, area_id))
                version = self._avanzar_version(cur, area_id)
                self._registrar_evento(cur, area_id, "BORRADOR_LIMPIADO", usuario_id, {"profesor_id": profesor_id})
                return version
        return None
    
    def confirmar_borrador(
        self, profesor_id: int, bloque: List[Dict], mapeo_actividades: Dict,
        area_id: Optional[int] = None, version_esperada: Optional[int] = None,
        usuario_id: Optional[int] = None,
    ) -> Optional[int]:
        """Confirma el borrador de un profesor."""
        if not bloque:
            raise ConstraintViolation("El bloque esta vacio.")
        
        with conexion_ctx() as conn:
            cur = conn.cursor()
            if area_id is not None:
                self._bloquear_control_area(cur, area_id, version_esperada)
            for e in bloque:
                actividad_id = e.get("actividad_id")
                clave = (e["codigo"], e["codigo_grupo"], e.get("tipo") or e.get("tipo_actividad"))
                if actividad_id is None:
                    actividad_id = mapeo_actividades.get(clave)
                if actividad_id is None:
                    raise ConstraintViolation(f"Actividad no encontrada: {clave}")
                
                cur.execute("""
                    INSERT INTO reparto_docente (profesor_id, actividad_id, horas_asignadas)
                    VALUES (%s, %s, %s)
                """, (profesor_id, actividad_id, e["horas"]))
            
            actividad_ids = [e.get("actividad_id") for e in bloque if e.get("actividad_id") is not None]
            if actividad_ids:
                cur.execute(
                    "DELETE FROM reparto_docente_borrador WHERE profesor_id=%s AND actividad_id = ANY(%s)",
                    (profesor_id, actividad_ids),
                )
            if area_id is not None:
                cur.execute(
                    """
                    UPDATE ordenacion_revisiones
                    SET estado='RESUELTA', resuelta_en=NOW(), resuelta_por_usuario_id=%s
                    WHERE area_id=%s AND profesor_id=%s AND estado='PENDIENTE'
                    """,
                    (usuario_id, area_id, profesor_id),
                )
                revisiones_resueltas = cur.rowcount
                version = self._avanzar_version(cur, area_id)
                self._registrar_evento(cur, area_id, "TURNO_CONFIRMADO", usuario_id, {
                    "profesor_id": profesor_id,
                    "actividades": actividad_ids,
                    "revisiones_resueltas": revisiones_resueltas,
                })
                if revisiones_resueltas:
                    self._registrar_evento(cur, area_id, "REVISION_RESUELTA", usuario_id, {
                        "profesor_id": profesor_id,
                        "total": revisiones_resueltas,
                    })
                return version
        return None

    def devolver_adjudicacion(
        self, actividad_id: int, profesor_id: int, area_id: int, motivo: str,
        usuario_id: Optional[int], version_esperada: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Devuelve una adjudicación confirmada al borrador del profesor.

        Se bloquea tanto el control del área como la fila confirmada. Así una
        devolución desde dos pantallas no puede duplicar las horas ni borrar
        una confirmación que ya haya cambiado en otra sesión.
        """
        with conexion_ctx() as conn:
            cur = conn.cursor()
            control = self._bloquear_control_area(
                cur, area_id, version_esperada, permitir_cerrada=True,
            )
            cur.execute(
                """
                SELECT rd.id, rd.horas_asignadas, actividad.area_id,
                       actividad.codigo, actividad.nombre_asignatura,
                       profesor.nombre, profesor.apellidos
                FROM reparto_docente AS rd
                JOIN actividades AS actividad ON actividad.id=rd.actividad_id
                JOIN profesores AS profesor ON profesor.id=rd.profesor_id
                WHERE rd.actividad_id=%s AND rd.profesor_id=%s AND actividad.area_id=%s
                FOR UPDATE OF rd, actividad
                """,
                (actividad_id, profesor_id, area_id),
            )
            repartos = cur.fetchall()
            if not repartos:
                raise ConstraintViolation("La adjudicación ya no está confirmada o no pertenece al área indicada.")

            cur.execute(
                """
                SELECT horas_asignadas
                FROM reparto_docente_borrador
                WHERE profesor_id=%s AND actividad_id=%s
                FOR UPDATE
                """,
                (profesor_id, actividad_id),
            )
            if cur.fetchone():
                raise ConstraintViolation(
                    "El profesor ya tiene esta actividad en borrador; resuelve ese borrador antes de devolverla."
                )

            horas_devuelta = round(sum(float(reparto[1]) for reparto in repartos), 2)
            cur.execute(
                "DELETE FROM reparto_docente WHERE id = ANY(%s)",
                ([reparto[0] for reparto in repartos],),
            )
            cur.execute(
                """
                INSERT INTO reparto_docente_borrador (profesor_id, actividad_id, horas_asignadas)
                VALUES (%s, %s, %s)
                """,
                (profesor_id, actividad_id, horas_devuelta),
            )
            cur.execute(
                """
                INSERT INTO ordenacion_revisiones
                    (area_id, profesor_id, actividad_id, horas_devuelta, motivo, devuelta_por_usuario_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (area_id, profesor_id, actividad_id) WHERE estado='PENDIENTE'
                DO UPDATE SET horas_devuelta=EXCLUDED.horas_devuelta,
                              motivo=EXCLUDED.motivo,
                              devuelta_por_usuario_id=EXCLUDED.devuelta_por_usuario_id,
                              creada_en=NOW()
                RETURNING id
                """,
                (area_id, profesor_id, actividad_id, horas_devuelta, motivo, usuario_id),
            )
            revision_id = int(cur.fetchone()[0])

            reabierta = control["estado"] == "CERRADA"
            if reabierta:
                cur.execute(
                    """
                    UPDATE ordenacion_areas_control
                    SET estado='ABIERTA', cerrado_por_usuario_id=NULL, cerrado_en=NULL,
                        actualizado_en=NOW()
                    WHERE area_id=%s
                    """,
                    (area_id,),
                )
            version = self._avanzar_version(cur, area_id)
            self._registrar_evento(cur, area_id, "ADJUDICACION_DEVUELTA", usuario_id, {
                "revision_id": revision_id,
                "actividad_id": actividad_id,
                "profesor_id": profesor_id,
                "horas_devuelta": horas_devuelta,
                "motivo": motivo,
                "reabierta": reabierta,
            })
            return {
                "ok": True,
                "revision_id": revision_id,
                "area_id": area_id,
                "version": version,
                "profesor": _nc(repartos[0][5], repartos[0][6]),
                "actividad": repartos[0][4] or repartos[0][3],
                "horas_devuelta": horas_devuelta,
                "reabierta": reabierta,
            }

    def cerrar_area(
        self, area_id: int, version_esperada: Optional[int], usuario_id: Optional[int],
    ) -> Dict[str, Any]:
        with conexion_ctx() as conn:
            cur = conn.cursor()
            control = self._bloquear_control_area(cur, area_id, version_esperada)
            cur.execute(
                """
                UPDATE ordenacion_areas_control
                SET estado='CERRADA', cerrado_por_usuario_id=%s, cerrado_en=NOW(),
                    version=version+1, actualizado_en=NOW()
                WHERE area_id=%s
                RETURNING version, cerrado_en
                """,
                (usuario_id, area_id),
            )
            version, cerrado_en = cur.fetchone()
            self._registrar_evento(cur, area_id, "ORDENACION_CERRADA", usuario_id, {
                "version_anterior": control["version"],
            })
            return {"area_id": area_id, "version": int(version), "cerrada": True, "cerrado_en": cerrado_en}

    def reabrir_area(
        self, area_id: int, version_esperada: Optional[int], usuario_id: Optional[int], motivo: str,
    ) -> Dict[str, Any]:
        with conexion_ctx() as conn:
            cur = conn.cursor()
            control = self._bloquear_control_area(cur, area_id, version_esperada, permitir_cerrada=True)
            if control["estado"] != "CERRADA":
                raise ConstraintViolation("La ordenación del área ya está abierta.")
            cur.execute(
                """
                UPDATE ordenacion_areas_control
                SET estado='ABIERTA', cerrado_por_usuario_id=NULL, cerrado_en=NULL,
                    version=version+1, actualizado_en=NOW()
                WHERE area_id=%s
                RETURNING version
                """,
                (area_id,),
            )
            version = int(cur.fetchone()[0])
            self._registrar_evento(cur, area_id, "ORDENACION_REABIERTA", usuario_id, {"motivo": motivo})
            return {"area_id": area_id, "version": version, "cerrada": False}
    
    def reset_all(self) -> None:
        """Reinicia toda la ordenacion (borra confirmadas y borradores)."""
        with conexion_ctx() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM planificacion_docente_sesiones")
            cur.execute("DELETE FROM ordenacion_conflictos_propuestas")
            cur.execute("DELETE FROM ordenacion_revisiones")
            cur.execute("DELETE FROM reparto_docente_borrador")
            cur.execute("DELETE FROM reparto_docente")
            cur.execute('UPDATE ordenacion_areas_control SET iniciada=FALSE')
            cur.execute("INSERT INTO ordenacion_eventos(area_id,tipo,detalle) SELECT id,'ORDENACION_REINICIADA','{}'::jsonb FROM areas")
            cur.execute(
                """
                UPDATE ordenacion_areas_control
                SET estado='ABIERTA', cerrado_por_usuario_id=NULL, cerrado_en=NULL,
                    version=version+1, actualizado_en=NOW()
                """
            )

    def reset_por_areas(self, area_ids: List[int]) -> Dict[str, int]:
        """Elimina solo los repartos asociados a las colas de las áreas indicadas.

        ``actividades.area_id`` identifica el área que ordena cada cuota de
        actividad. Las relaciones académicas adicionales de una actividad no
        amplían el alcance: así un reinicio de área no borra una cuota que se
        está ordenando desde otra cola.
        """
        ids_normalizados = sorted({int(area_id) for area_id in area_ids})
        if not ids_normalizados:
            raise ValueError("Selecciona al menos un área para reiniciar la ordenación.")

        with conexion_ctx() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                DELETE FROM planificacion_docente_sesiones AS plan
                USING actividades AS actividad
                WHERE plan.actividad_id=actividad.id
                  AND actividad.area_id = ANY(%s)
                """,
                (ids_normalizados,),
            )
            cur.execute("DELETE FROM ordenacion_revisiones WHERE area_id = ANY(%s)", (ids_normalizados,))
            cur.execute("DELETE FROM ordenacion_conflictos_propuestas WHERE area_id = ANY(%s)", (ids_normalizados,))
            cur.execute(
                """
                DELETE FROM reparto_docente_borrador AS borrador
                USING actividades AS actividad
                WHERE borrador.actividad_id = actividad.id
                  AND actividad.area_id = ANY(%s)
                """,
                (ids_normalizados,),
            )
            borradores_eliminados = cur.rowcount
            cur.execute(
                """
                DELETE FROM reparto_docente AS reparto
                USING actividades AS actividad
                WHERE reparto.actividad_id = actividad.id
                  AND actividad.area_id = ANY(%s)
                """,
                (ids_normalizados,),
            )
            confirmaciones_eliminadas = cur.rowcount
            for area_id in ids_normalizados:
                cur.execute('UPDATE ordenacion_areas_control SET iniciada=FALSE WHERE area_id=%s', (area_id,))
                cur.execute(
                    """
                    UPDATE ordenacion_areas_control
                    SET estado='ABIERTA', cerrado_por_usuario_id=NULL, cerrado_en=NULL,
                        version=version+1, actualizado_en=NOW()
                    WHERE area_id=%s
                    """,
                    (area_id,),
                )
                self._registrar_evento(cur, area_id, "ORDENACION_REINICIADA", None, {})

        return {
            "borradores_eliminados": borradores_eliminados,
            "confirmaciones_eliminadas": confirmaciones_eliminadas,
        }
