"""Generación y consulta de la planificación docente distribuida por semanas."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional
import re
import unicodedata

from domain.ordenacion.planificacion_semanal import (
    extraer_franjas,
    generar_sesiones_recurrentes,
    horas_entre,
    replicar_horario_completo_actividad,
)
from repositories.planificacion_docente_repository import PlanificacionDocenteRepository


def _fecha(valor: object) -> Optional[date]:
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return None


def _tipo_estudio(actividad: Dict[str, Any]) -> str:
    valor = str(actividad.get("tipo_estudio") or "GRADO").upper()
    # Los datos docentes de la UAL codifican los másteres oficiales como MOF.
    # Si se interpretasen como grado se eliminarían sesiones válidas de enero
    # al aplicar un periodo académico equivocado.
    return "MASTER" if "MASTER" in valor or "MÁSTER" in valor or valor.strip() in {"MOF", "MAS", "MST"} else "GRADO"


def _curso(actividad: Dict[str, Any], cursos_disponibles: Iterable[str]) -> Optional[str]:
    disponibles = list(cursos_disponibles)
    valor = str(actividad.get("curso_academico") or "").strip()
    if not valor:
        return disponibles[0] if disponibles else None
    if valor in disponibles:
        return valor

    # Los catálogos UAL usan indistintamente ``2026-27`` y ``2026/2027``.
    # La planificación tiene una única clave por curso, por lo que se resuelve
    # la variante publicada antes de generar sesiones pendientes por error.
    coincidencia = re.fullmatch(r"(\d{4})\s*[-/]\s*(\d{2}|\d{4})", valor)
    if coincidencia:
        inicio, fin = coincidencia.groups()
        fin_completo = fin if len(fin) == 4 else f"{inicio[:2]}{fin}"
        candidatas = [f"{inicio}/{fin}", f"{inicio}/{fin_completo}"]
        for candidata in candidatas:
            if candidata in disponibles:
                return candidata
    return valor


def _periodos_de_actividad(actividad: Dict[str, Any], periodos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Restringe las franjas manuales al cuatrimestre de la actividad."""
    texto = unicodedata.normalize("NFD", str(actividad.get("duracion") or "").lower())
    texto = "".join(char for char in texto if unicodedata.category(char) != "Mn").strip()
    if texto in {"1", "c1", "1c", "1q", "primer cuatrimestre", "primero"}:
        return [periodo for periodo in periodos if periodo["cuatrimestre"] == "PRIMERO"]
    if texto in {"2", "c2", "2c", "2q", "segundo cuatrimestre", "segundo"}:
        return [periodo for periodo in periodos if periodo["cuatrimestre"] == "SEGUNDO"]
    return periodos


class PlanificacionDocenteService:
    def __init__(self) -> None:
        self.repo = PlanificacionDocenteRepository()

    def _sesiones_de_horario_oficial(
        self,
        actividad: Dict[str, Any],
        periodos: List[Dict[str, Any]],
        no_lectivas: set[date],
    ) -> List[Dict[str, Any]]:
        """Usa fechas oficiales si existen; si no, expande la franja semanal."""
        detalle = actividad.get("horario_detallado") or []
        tiene_fechas = any(isinstance(sesion, dict) and sesion.get('fecha') for sesion in detalle)
        fechas_oficiales = actividad.get("origen_horario") == "UAL_OFICIAL"
        fechadas: List[Dict[str, Any]] = []
        rangos = [(periodo["fecha_inicio"], periodo["fecha_fin"]) for periodo in periodos]
        for sesion in detalle:
            if not isinstance(sesion, dict):
                continue
            fecha_sesion = _fecha(sesion.get("fecha"))
            inicio, fin = sesion.get("inicio"), sesion.get("fin")
            if not fecha_sesion or not inicio or not fin:
                continue
            if fecha_sesion.weekday() > 4 or fecha_sesion in no_lectivas:
                continue
            # Una fecha explícita publicada por UAL prevalece sobre el rango
            # genérico. No ampliar recurrencias ni referencias de otros años.
            if not fechas_oficiales and rangos and not any(inicio_periodo <= fecha_sesion <= fin_periodo for inicio_periodo, fin_periodo in rangos):
                continue
            try:
                horas = horas_entre(str(inicio), str(fin))
            except ValueError:
                continue
            if horas > 0:
                fechadas.append({
                    "fecha": fecha_sesion, "inicio": str(inicio)[:5],
                    "fin": str(fin)[:5], "horas": horas,
                })
        if tiene_fechas:
            # Un calendario fechado define sus semanas. Si todas las sesiones
            # caen en festivo o fuera del periodo, no inventar recurrencias.
            unicas = {(item['fecha'], item['inicio'], item['fin']): item for item in fechadas}
            return sorted(unicas.values(), key=lambda item: (item["fecha"], item["inicio"], item["fin"]))

        franjas = extraer_franjas(actividad.get("horario"), actividad.get("dias"))
        recurrentes: List[Dict[str, Any]] = []
        for periodo in periodos:
            recurrentes.extend(generar_sesiones_recurrentes(
                periodo["fecha_inicio"], periodo["fecha_fin"], franjas, no_lectivas,
            ))
        # Las franjas anuales pueden cruzar periodos; una sesión nunca debe repetirse.
        unicas = {(item["fecha"], item["inicio"], item["fin"]): item for item in recurrentes}
        return sorted(unicas.values(), key=lambda item: (item["fecha"], item["inicio"], item["fin"]))

    @staticmethod
    def _incidencias_sin_horario(
        adjudicaciones: List[Dict[str, Any]],
        horas_actividad: float,
        observacion: str,
    ) -> List[Dict[str, Any]]:
        """Registra una incidencia por docente sin confundirla con su cuota."""
        return [
            {
                "reparto_id": item["reparto_id"],
                "profesor_id": item["profesor_id"],
                # Estas son las horas globales que no se pueden representar
                # todavía. La cuota del docente se conserva separada.
                "horas": horas_actividad,
                "horas_adjudicadas": float(item["horas_asignadas"]),
                "es_horario_referencia": True,
                "orden_adjudicacion": orden,
                "orden_sesion": 1,
                "estado": "PENDIENTE_HORARIO",
                "observacion": observacion,
            }
            for orden, item in enumerate(adjudicaciones, start=1)
        ]

    def regenerar_actividad(self, actividad_id: int) -> Dict[str, Any]:
        """Regenera el calendario de la actividad lógica completa.

        ``actividades`` conserva una fila por cuota de área para que el solver
        no duplique carga en actividades compartidas. Todas esas cuotas son,
        sin embargo, un único grupo con un único horario oficial; se proyecta
        una sola vez a cada profesor que tenga una adjudicación en él.
        """
        familia = self.repo.get_actividades_logicas(actividad_id)
        if not familia:
            return {"actividad_id": actividad_id, "sesiones": 0, "mensaje": "Actividad eliminada."}
        actividad = familia[0]
        actividad_ids = [item["id"] for item in familia]
        repartos = self.repo.get_repartos_actividades(actividad_ids)
        self.repo.borrar_plan_actividades(actividad_ids)
        if not repartos:
            return {
                "actividad_id": actividad["id"], "actividad_ids": actividad_ids,
                "sesiones": 0, "mensaje": "No hay adjudicaciones confirmadas.",
            }

        curso = _curso(actividad, self.repo.get_cursos_con_calendario())
        horas_actividad = round(float(actividad["horas_actividad"]), 2)
        if not curso:
            sesiones = self._incidencias_sin_horario(
                repartos, horas_actividad,
                "No hay un curso académico configurado para mostrar el horario de esta actividad.",
            )
        elif not actividad.get("requiere_horario", True):
            sesiones = self._incidencias_sin_horario(
                repartos, horas_actividad,
                "Actividad sin horario fijo: no se puede mostrar su horario semanal completo.",
            )
        else:
            periodos = _periodos_de_actividad(
                actividad, self.repo.get_periodos(curso, _tipo_estudio(actividad)),
            )
            no_lectivas = {
                excepcion["fecha"] for excepcion in self.repo.get_excepciones(curso)
                if excepcion.get("bloquea_docencia")
            }
            candidatas = self._sesiones_de_horario_oficial(actividad, periodos, no_lectivas)
            if not periodos or not candidatas:
                sesiones = self._incidencias_sin_horario(
                    repartos, horas_actividad,
                    "No hay sesiones lectivas válidas para mostrar el horario completo de esta actividad.",
                )
            else:
                sesiones = replicar_horario_completo_actividad(
                    candidatas,
                    [
                        {
                            "reparto_id": reparto["reparto_id"],
                            "profesor_id": reparto["profesor_id"],
                            "horas": float(reparto["horas_asignadas"]),
                        }
                        for reparto in repartos
                    ],
                    horas_actividad,
                )

        total = self.repo.guardar_plan(actividad["id"], curso or "SIN_CURSO", sesiones)
        return {
            "actividad_id": actividad["id"], "actividad_ids": actividad_ids,
            "curso_academico": curso, "sesiones": total,
        }

    def regenerar_actividades(self, actividad_ids: Iterable[int]) -> Dict[str, Any]:
        resultados = []
        procesadas: set[int] = set()
        for actividad_id in sorted(set(actividad_ids)):
            if actividad_id in procesadas:
                continue
            resultado = self.regenerar_actividad(int(actividad_id))
            procesadas.update(resultado.get("actividad_ids", [actividad_id]))
            resultados.append(resultado)
        return {"actividades": len(resultados), "sesiones": sum(resultado["sesiones"] for resultado in resultados), "resultados": resultados}

    def regenerar_todas_confirmadas(self) -> Dict[str, Any]:
        # No se usa una lectura de la planificación: se parte siempre de las
        # adjudicaciones, que son la fuente de verdad.
        from repositories.reparto_repository import RepartoRepository
        ids = [item["actividad_id"] for item in RepartoRepository().find_all_confirmadas()]
        return self.regenerar_actividades(ids)

    def calendario_profesor(
        self, profesor_id: int, curso_academico: Optional[str] = None,
        semana: Optional[date] = None,
    ) -> Dict[str, Any]:
        cursos = self.repo.get_cursos_profesor(profesor_id) or self.repo.get_cursos_con_calendario()
        curso = curso_academico or (cursos[0] if cursos else None)
        if not curso:
            raise ValueError("No hay calendario académico disponible.")
        # FastAPI ya entrega ``date`` en la API; la normalización adicional
        # mantiene el servicio reutilizable desde tareas administrativas.
        referencia = _fecha(semana) or self.repo.get_primer_dia_planificado(profesor_id, curso)
        if referencia is None:
            periodos = self.repo.get_periodos(curso, "GRADO")
            referencia = periodos[0]["fecha_inicio"] if periodos else date.today()
        inicio = referencia - timedelta(days=referencia.weekday())
        fin = inicio + timedelta(days=6)
        return {
            "curso_academico": curso,
            "cursos_disponibles": cursos,
            "semana_inicio": inicio,
            "semana_fin": fin,
            "sesiones": self.repo.get_sesiones_profesor(profesor_id, curso, inicio, fin),
            "incidencias": self.repo.get_incidencias_profesor(profesor_id, curso),
            "dias_no_lectivos": self.repo.get_excepciones_semana(curso, inicio, fin),
        }
