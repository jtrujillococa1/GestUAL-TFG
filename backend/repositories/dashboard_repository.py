"""
Repository para metricas del dashboard.
"""
from typing import Dict, Any, List
from db.connection import cursor_ctx


class DashboardRepository:
    """Gestiona consultas de metricas para el dashboard."""
    
    def get_metricas(self) -> Dict[str, Any]:
        """Obtiene metricas generales del sistema."""
        with cursor_ctx() as cur:
            # Total profesores (sin PSI)
            cur.execute("SELECT COUNT(*) as total FROM profesores WHERE es_psi = FALSE")
            total_profesores = cur.fetchone()["total"]
            
            # Total PSI
            cur.execute("SELECT COUNT(*) as total FROM profesores WHERE es_psi = TRUE")
            total_psi = cur.fetchone()["total"]
            
            # Total actividades
            cur.execute("SELECT COUNT(*) as total FROM actividades")
            total_actividades = cur.fetchone()["total"]
            
            # Horas totales profesores
            cur.execute("SELECT COALESCE(SUM(carga_docente), 0) as total FROM profesores WHERE es_psi = FALSE")
            horas_totales_profesores = float(cur.fetchone()["total"])
            
            # Horas totales actividades
            cur.execute("SELECT COALESCE(SUM(horas_area), 0) as total FROM actividades")
            horas_totales_actividades = float(cur.fetchone()["total"])
            
            # Horas asignadas
            cur.execute("SELECT COALESCE(SUM(horas_asignadas), 0) as total FROM reparto_docente")
            horas_asignadas = float(cur.fetchone()["total"])
            
            # Profesores completados
            cur.execute("""
                SELECT COUNT(DISTINCT p.id) as total
                FROM profesores p
                LEFT JOIN reparto_docente rd ON rd.profesor_id = p.id
                WHERE p.es_psi = FALSE
                GROUP BY p.id, p.carga_docente
                HAVING COALESCE(SUM(rd.horas_asignadas), 0) >= p.carga_docente - 0.01
            """)
            result = cur.fetchone()
            profesores_completados = result["total"] if result else 0
            
            # Actividades incompletas
            cur.execute("""
                SELECT COUNT(*) as total
                FROM actividades a
                LEFT JOIN reparto_docente rd ON rd.actividad_id = a.id
                GROUP BY a.id, a.horas_area
                HAVING a.horas_area - COALESCE(SUM(rd.horas_asignadas), 0) > 0.01
            """)
            result = cur.fetchone()
            actividades_incompletas = result["total"] if result else 0
            
            # Porcentaje de asignacion
            porcentaje_asignacion = 0.0
            if horas_totales_actividades > 0:
                porcentaje_asignacion = round((horas_asignadas / horas_totales_actividades) * 100, 2)
            
            # Equilibrio de horas
            equilibrio_horas = abs(horas_totales_profesores - horas_totales_actividades) < 0.01
            
            # Ordenacion terminada
            profesores_pendientes = total_profesores - profesores_completados
            ordenacion_terminada = profesores_pendientes == 0
            
            return {
                "total_profesores": total_profesores,
                "total_psi": total_psi,
                "total_actividades": total_actividades,
                "porcentaje_asignacion": porcentaje_asignacion,
                "actividades_incompletas": actividades_incompletas,
                "profesores_completados": profesores_completados,
                "profesores_pendientes": profesores_pendientes,
                "horas_totales_sistema": horas_totales_profesores,
                "horas_asignadas_sistema": horas_asignadas,
                "equilibrio_horas": equilibrio_horas,
                "ordenacion_terminada": ordenacion_terminada,
                "profesor_actual": None,
            }
    
    def get_metricas_departamento(self, departamento_id: int) -> Dict[str, Any]:
        """Obtiene metricas filtradas por departamento."""
        with cursor_ctx() as cur:
            # Profesores del departamento
            cur.execute("""
                SELECT COUNT(*) as total
                FROM profesores p
                JOIN areas a ON a.id = p.area_id
                WHERE a.departamento_id = %s AND p.es_psi = FALSE
            """, (departamento_id,))
            total_profesores = cur.fetchone()["total"]
            
            # PSI del departamento
            cur.execute("""
                SELECT COUNT(*) as total
                FROM profesores p
                JOIN areas a ON a.id = p.area_id
                WHERE a.departamento_id = %s AND p.es_psi = TRUE
            """, (departamento_id,))
            total_psi = cur.fetchone()["total"]
            
            # Actividades del departamento
            cur.execute("""
                SELECT COUNT(*) as total
                FROM actividades act
                JOIN areas a ON a.id = act.area_id
                WHERE a.departamento_id = %s
            """, (departamento_id,))
            total_actividades = cur.fetchone()["total"]
            
            # Horas totales profesores
            cur.execute("""
                SELECT COALESCE(SUM(p.carga_docente), 0) as total
                FROM profesores p
                JOIN areas a ON a.id = p.area_id
                WHERE a.departamento_id = %s AND p.es_psi = FALSE
            """, (departamento_id,))
            horas_totales_profesores = float(cur.fetchone()["total"])
            
            # Horas asignadas
            cur.execute("""
                SELECT COALESCE(SUM(rd.horas_asignadas), 0) as total
                FROM reparto_docente rd
                JOIN profesores p ON p.id = rd.profesor_id
                JOIN areas a ON a.id = p.area_id
                WHERE a.departamento_id = %s
            """, (departamento_id,))
            horas_asignadas = float(cur.fetchone()["total"])
            
            return {
                "departamento_id": departamento_id,
                "total_profesores": total_profesores,
                "total_psi": total_psi,
                "total_actividades": total_actividades,
                "horas_totales_sistema": horas_totales_profesores,
                "horas_asignadas_sistema": horas_asignadas,
            }
    
    def get_metricas_area(self, area_id: int) -> Dict[str, Any]:
        """Obtiene metricas filtradas por area."""
        with cursor_ctx() as cur:
            # Profesores del area
            cur.execute("""
                SELECT COUNT(*) as total
                FROM profesores
                WHERE area_id = %s AND es_psi = FALSE
            """, (area_id,))
            total_profesores = cur.fetchone()["total"]
            
            # Actividades del area
            cur.execute("""
                SELECT COUNT(*) as total
                FROM actividades
                WHERE area_id = %s
            """, (area_id,))
            total_actividades = cur.fetchone()["total"]
            
            # Horas totales profesores
            cur.execute("""
                SELECT COALESCE(SUM(carga_docente), 0) as total
                FROM profesores
                WHERE area_id = %s AND es_psi = FALSE
            """, (area_id,))
            horas_totales_profesores = float(cur.fetchone()["total"])
            
            # Horas asignadas
            cur.execute("""
                SELECT COALESCE(SUM(rd.horas_asignadas), 0) as total
                FROM reparto_docente rd
                JOIN profesores p ON p.id = rd.profesor_id
                WHERE p.area_id = %s
            """, (area_id,))
            horas_asignadas = float(cur.fetchone()["total"])
            
            return {
                "area_id": area_id,
                "total_profesores": total_profesores,
                "total_actividades": total_actividades,
                "horas_totales_sistema": horas_totales_profesores,
                "horas_asignadas_sistema": horas_asignadas,
            }
    
    def get_equilibrio(self) -> Dict[str, Any]:
        """Verifica el equilibrio entre horas de profesores y actividades."""
        with cursor_ctx() as cur:
            # Horas totales profesores
            cur.execute("SELECT COALESCE(SUM(carga_docente), 0) as total FROM profesores WHERE es_psi = FALSE")
            horas_profesores = float(cur.fetchone()["total"])
            
            # Horas totales actividades
            cur.execute("SELECT COALESCE(SUM(horas_area), 0) as total FROM actividades")
            horas_actividades = float(cur.fetchone()["total"])
            
            diferencia = round(horas_profesores - horas_actividades, 2)
            equilibrado = abs(diferencia) < 0.01
            
            return {
                "equilibrado": equilibrado,
                "horas_profesores": horas_profesores,
                "horas_actividades": horas_actividades,
                "diferencia": diferencia,
            }
    
    def get_equilibrio_departamento(self, departamento_id: int) -> Dict[str, Any]:
        """Verifica el equilibrio de un departamento."""
        with cursor_ctx() as cur:
            # Horas profesores del departamento
            cur.execute("""
                SELECT COALESCE(SUM(p.carga_docente), 0) as total
                FROM profesores p
                JOIN areas a ON a.id = p.area_id
                WHERE a.departamento_id = %s AND p.es_psi = FALSE
            """, (departamento_id,))
            horas_profesores = float(cur.fetchone()["total"])
            
            # Horas actividades del departamento
            cur.execute("""
                SELECT COALESCE(SUM(act.horas_area), 0) as total
                FROM actividades act
                JOIN areas a ON a.id = act.area_id
                WHERE a.departamento_id = %s
            """, (departamento_id,))
            horas_actividades = float(cur.fetchone()["total"])
            
            diferencia = round(horas_profesores - horas_actividades, 2)
            equilibrado = abs(diferencia) < 0.01
            
            return {
                "departamento_id": departamento_id,
                "equilibrado": equilibrado,
                "horas_profesores": horas_profesores,
                "horas_actividades": horas_actividades,
                "diferencia": diferencia,
            }
    
    def get_equilibrio_area(self, area_id: int) -> Dict[str, Any]:
        """Verifica el equilibrio de un area."""
        with cursor_ctx() as cur:
            # Horas profesores del area
            cur.execute("""
                SELECT COALESCE(SUM(carga_docente), 0) as total
                FROM profesores
                WHERE area_id = %s AND es_psi = FALSE
            """, (area_id,))
            horas_profesores = float(cur.fetchone()["total"])
            
            # Horas actividades del area
            cur.execute("""
                SELECT COALESCE(SUM(horas_area), 0) as total
                FROM actividades
                WHERE area_id = %s
            """, (area_id,))
            horas_actividades = float(cur.fetchone()["total"])
            
            diferencia = round(horas_profesores - horas_actividades, 2)
            equilibrado = abs(diferencia) < 0.01
            
            return {
                "area_id": area_id,
                "equilibrado": equilibrado,
                "horas_profesores": horas_profesores,
                "horas_actividades": horas_actividades,
                "diferencia": diferencia,
            }
    
    def get_stats_profesores_por_categoria(self) -> List[Dict[str, Any]]:
        """Obtiene estadisticas de profesores agrupadas por categoria."""
        with cursor_ctx() as cur:
            cur.execute("""
                SELECT 
                    p.categoria,
                    COUNT(*) as total_profesores,
                    COALESCE(SUM(p.carga_docente), 0) as total_horas,
                    COALESCE(SUM(rd.horas_asignadas), 0) as horas_asignadas,
                    COUNT(DISTINCT rd.profesor_id) as profesores_con_asignaciones
                FROM profesores p
                LEFT JOIN reparto_docente rd ON rd.profesor_id = p.id
                WHERE p.es_psi = FALSE
                GROUP BY p.categoria
                ORDER BY p.categoria
            """)
            
            return [
                {
                    "categoria": row["categoria"],
                    "total_profesores": row["total_profesores"],
                    "total_horas": float(row["total_horas"]),
                    "horas_asignadas": float(row["horas_asignadas"]),
                    "profesores_con_asignaciones": row["profesores_con_asignaciones"],
                }
                for row in cur.fetchall()
            ]
    
    def get_stats_actividades_por_area(self) -> List[Dict[str, Any]]:
        """Obtiene estadisticas de actividades agrupadas por area."""
        with cursor_ctx() as cur:
            cur.execute("""
                SELECT 
                    COALESCE(a.area_id, 0) as area_id,
                    COALESCE(ar.nombre, 'Sin area') as area_nombre,
                    COUNT(*) as total_actividades,
                    COALESCE(SUM(a.horas_area), 0) as total_horas,
                    COALESCE(SUM(rd.horas_asignadas), 0) as horas_asignadas,
                    COUNT(DISTINCT rd.actividad_id) as actividades_con_asignaciones
                FROM actividades a
                LEFT JOIN areas ar ON ar.id = a.area_id
                LEFT JOIN reparto_docente rd ON rd.actividad_id = a.id
                GROUP BY a.area_id, ar.nombre
                ORDER BY ar.nombre NULLS LAST
            """)
            
            return [
                {
                    "area_id": row["area_id"],
                    "area_nombre": row["area_nombre"],
                    "total_actividades": row["total_actividades"],
                    "total_horas": float(row["total_horas"]),
                    "horas_asignadas": float(row["horas_asignadas"]),
                    "actividades_con_asignaciones": row["actividades_con_asignaciones"],
                }
                for row in cur.fetchall()
            ]
