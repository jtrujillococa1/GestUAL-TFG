"""Consulta de la planificación docente semanal derivada de adjudicaciones."""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.routes.ordenacion import _obtener_ambito_ordenacion, _profesor_pertenece_al_ambito
from core.auth import get_current_user
from repositories import ProfesorRepository
from services.planificacion_docente_service import PlanificacionDocenteService


router = APIRouter(prefix="/api/v1/planificacion-docente", tags=["planificación docente"])


class RegenerarPlanificacionRequest(BaseModel):
    actividad_id: Optional[int] = Field(default=None, gt=0)


def _profesor_visible(current_user: dict, profesor: dict) -> bool:
    if current_user["rol"] == "admin":
        return True
    ambito = _obtener_ambito_ordenacion(current_user)
    return _profesor_pertenece_al_ambito(profesor, ambito)


def _obtener_profesor_visible(profesor_id: int, current_user: dict) -> dict:
    profesor = ProfesorRepository().find_by_id(profesor_id)
    if not profesor:
        raise HTTPException(status_code=404, detail="Profesor no encontrado.")
    if not _profesor_visible(current_user, profesor):
        raise HTTPException(status_code=403, detail="No puedes consultar la planificación de este profesor.")
    return profesor


@router.get("/profesores", summary="Profesorado visible para planificación")
def get_profesores_planificacion(current_user: dict = Depends(get_current_user)):
    """Lista el profesorado que el usuario puede consultar en el calendario."""
    profesores = [
        profesor for profesor in ProfesorRepository().find_all()
        if _profesor_visible(current_user, profesor)
    ]
    return [
        {
            "id": profesor["id"],
            "nombre": profesor["nombre"],
            "apellidos": profesor["apellidos"],
            "categoria": profesor["categoria"],
            "area_ids": profesor.get("area_ids") or [],
            "areas": profesor.get("areas") or [],
        }
        for profesor in profesores
    ]


@router.get("/mi-calendario", summary="Planificación semanal propia")
def get_mi_calendario(
    curso_academico: Optional[str] = None,
    semana: Optional[date] = None,
    current_user: dict = Depends(get_current_user),
):
    profesor = ProfesorRepository().find_by_usuario_id(current_user["user_id"])
    if not profesor:
        raise HTTPException(status_code=403, detail="No tienes un perfil de profesor asociado.")
    try:
        datos = PlanificacionDocenteService().calendario_profesor(
            profesor["id"], curso_academico, semana,
        )
        return {"profesor": _resumen_profesor(profesor), "es_propio": True, **datos}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/profesores/{profesor_id}", summary="Planificación semanal de un profesor")
def get_calendario_profesor(
    profesor_id: int,
    curso_academico: Optional[str] = None,
    semana: Optional[date] = None,
    current_user: dict = Depends(get_current_user),
):
    profesor = _obtener_profesor_visible(profesor_id, current_user)
    try:
        datos = PlanificacionDocenteService().calendario_profesor(
            profesor_id, curso_academico, semana,
        )
        propio = profesor.get("usuario_id") == current_user["user_id"]
        return {"profesor": _resumen_profesor(profesor), "es_propio": propio, **datos}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/regenerar", summary="Regenerar planificación derivada")
def post_regenerar_planificacion(
    body: RegenerarPlanificacionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Recrea sesiones a partir de adjudicaciones; reservado a administración."""
    if current_user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Solo administración puede regenerar toda la planificación.")
    service = PlanificacionDocenteService()
    try:
        if body.actividad_id:
            return service.regenerar_actividad(body.actividad_id)
        return service.regenerar_todas_confirmadas()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No se ha podido regenerar la planificación: {exc}") from exc


@router.get("/calendario-academico", summary="Periodos y días no lectivos configurados")
def get_calendario_academico(
    curso_academico: str,
    current_user: dict = Depends(get_current_user),
):
    # La consulta es útil para explicar por qué no se imparte una clase una
    # semana concreta; todos los usuarios autenticados pueden verla.
    repo = PlanificacionDocenteService().repo
    return {
        "curso_academico": curso_academico,
        "periodos_grado": repo.get_periodos(curso_academico, "GRADO"),
        "periodos_master": repo.get_periodos(curso_academico, "MASTER"),
        "excepciones": repo.get_excepciones(curso_academico),
    }


def _resumen_profesor(profesor: dict) -> dict:
    return {
        "id": profesor["id"],
        "nombre": profesor["nombre"],
        "apellidos": profesor["apellidos"],
        "categoria": profesor["categoria"],
        "areas": profesor.get("areas") or [],
    }
