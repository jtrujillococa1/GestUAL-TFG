"""
API Routes - Ordenación Docente.
"""
from typing import List
from contextlib import contextmanager
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from models.schemas import (
    EstadoOrdenacionSchema,
    OpcionSchema,
    BorradorSchema,
    ConfirmacionResultadoSchema,
    ControlOrdenacionSchema,
    EventoOrdenacionSchema,
    TipoActividad,
)
from services import OrdenacionService
from repositories import ProfesorRepository, AreaRepository, DepartamentoRepository, RepartoRepository
from core.exceptions import (
    NotYourTurn, IncompleteTurn, ViabilityLost, OrdenacionFinished,
    ConcurrentModification, OrdenacionClosed, OrdenacionClosureInvalid,
    ProfesorNotFound, PermissionDenied, ConstraintViolation,
)
from core.auth import get_current_user, require_admin
from core.permissions import can_modify_draft
from core.ambito_gestion import obtener_ambito_gestor

router = APIRouter(prefix="/api/v1", tags=["ordenacion"])


@contextmanager
def _edicion_docente(nombre_completo: str):
    """Evita validar simultáneamente dos borradores del mismo docente en áreas distintas."""
    from db.connection import cursor_ctx
    with cursor_ctx() as cur:
        cur.execute("SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 2026)) AS libre", (nombre_completo,))
        if not cur.fetchone()['libre']:
            raise ConcurrentModification('Este profesor se está editando desde otra área. Actualiza y vuelve a intentarlo.')
        yield


# ═══════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════

class AnadirOpcionRequest(BaseModel):
    area_id: int
    actividad_id: int | None = None
    codigo: str
    codigo_grupo: str
    tipo: TipoActividad
    horas: float = Field(gt=0, multiple_of=0.1, allow_inf_nan=False)
    version_ordenacion: int | None = None


class EliminarOpcionRequest(BaseModel):
    area_id: int
    actividad_id: int | None = None
    codigo: str
    codigo_grupo: str
    tipo: TipoActividad
    version_ordenacion: int | None = None


@router.post('/evaluar-horas/{nombre_completo:path}', summary='Evaluar la cantidad exacta sin modificar el borrador')
def evaluar_horas(nombre_completo: str, body: AnadirOpcionRequest, current_user: dict = Depends(get_current_user)):
    _verificar_acceso_profesor(current_user, nombre_completo, requiere_turno=True, area_id=body.area_id)
    if body.actividad_id is None:
        raise HTTPException(status_code=422, detail='Selecciona una actividad.')
    try:
        opciones = OrdenacionService().get_opciones(nombre_completo, body.area_id, actividad_evaluada=body.actividad_id, horas_evaluadas=body.horas)
        if not opciones:
            raise HTTPException(status_code=409, detail='La opción ya no está disponible. Actualiza el borrador.')
        return opciones[0]
    except (ConstraintViolation, OrdenacionClosed) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post('/areas/{area_id}/iniciar', summary='Validar e iniciar la ordenación del área')
def iniciar_area(area_id: int, current_user: dict = Depends(get_current_user)):
    _verificar_gestion_cierre_area(current_user, area_id)
    from db.connection import cursor_ctx
    from solver.engine import resolver_reparto_en_area
    service = OrdenacionService()
    control = service.reparto_repo.get_control_area(area_id)
    if control.get('iniciada', True):
        raise HTTPException(status_code=409, detail='La ordenación ya está iniciada.')
    profesores = service.profesor_repo.find_for_ordenacion()
    actividades = service.actividad_repo.find_for_ordenacion()
    if not any(a.get('area_id') == area_id for a in actividades):
        raise HTTPException(status_code=422, detail='Añade las actividades y sus cuotas antes de iniciar.')
    resultado = resolver_reparto_en_area(service.reparto_repo.find_all_confirmadas(), profesores, actividades, area_id, usar_cache=False, preferir_heuristico=True, solo_factibilidad=True, tiempo_limite_ms=15000)
    if not resultado.get('viable'):
        raise HTTPException(status_code=422, detail='No se puede iniciar: revisa cargas por área, cuotas, cuatrimestres y solapes. ' + ' '.join(resultado.get('diagnostico') or []))
    with cursor_ctx() as cur:
        cur.execute('INSERT INTO ordenacion_areas_control(area_id) VALUES(%s) ON CONFLICT DO NOTHING', (area_id,))
        cur.execute('UPDATE ordenacion_areas_control SET iniciada=TRUE,version=version+1,actualizado_en=NOW() WHERE area_id=%s AND iniciada=FALSE AND version=%s RETURNING version', (area_id,control['version']))
        fila = cur.fetchone()
        if not fila:
            raise HTTPException(status_code=409, detail='El área cambió. Vuelve a validar el inicio.')
        cur.execute("INSERT INTO ordenacion_eventos(area_id,usuario_id,tipo) VALUES(%s,%s,'ORDENACION_INICIADA')", (area_id,current_user['user_id']))
    return {'ok': True, 'version': fila['version']}


class CierreAreaRequest(BaseModel):
    version_ordenacion: int | None = None


class ReaperturaAreaRequest(CierreAreaRequest):
    motivo: str


class DevolverAdjudicacionRequest(BaseModel):
    """Datos mínimos para corregir una adjudicación ya confirmada."""
    profesor_id: int
    area_id: int
    motivo: str
    version_ordenacion: int | None = None


class DecidirConflictoRequest(BaseModel):
    aprobar: bool
    motivo: str | None = None


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _obtener_ambito_ordenacion(current_user: dict) -> dict:
    """Devuelve el ámbito real de gestión de ordenación del usuario autenticado."""
    rol = current_user["rol"]
    if rol == "admin":
        return {"global": True, "areas": set(), "departamentos": set(), "profesores": set()}

    if rol == "responsable_departamento":
        ambito = obtener_ambito_gestor(current_user["user_id"], rol)
        return {"global": False, "areas": ambito["areas"], "departamentos": ambito["departamentos"], "profesores": set()}

    if rol == "responsable_area":
        ambito = obtener_ambito_gestor(current_user["user_id"], rol)
        return {"global": False, "areas": ambito["areas"], "departamentos": ambito["departamentos"], "profesores": set()}

    if rol == "profesor":
        profesor = ProfesorRepository().find_by_usuario_id(current_user["user_id"])
        if not profesor:
            raise HTTPException(status_code=403, detail="No tienes un perfil de profesor asociado")
        return {"global": False, "areas": set(), "departamentos": set(), "profesores": {profesor["id"]}}

    # PSI no participa en la ordenación.
    return {"global": False, "areas": set(), "departamentos": set(), "profesores": set()}


def _profesor_pertenece_al_ambito(profesor: dict, ambito: dict) -> bool:
    if ambito["global"]:
        return True
    if profesor["id"] in ambito["profesores"]:
        return True
    if set(profesor.get("area_ids") or ([profesor["area_id"]] if profesor.get("area_id") else [])).intersection(ambito["areas"]):
        return True
    return profesor.get("departamento_id") in ambito["departamentos"]


def _verificar_acceso_profesor(
    current_user: dict, nombre_completo: str, requiere_turno: bool = False,
    area_id: int | None = None,
) -> dict:
    """Autoriza el acceso al profesor y, al modificar, exige que sea el turno actual."""
    if current_user["rol"] == "psi":
        raise HTTPException(status_code=403, detail="PSI no puede participar en la ordenación")

    repo_prof = ProfesorRepository()
    profesor_target = repo_prof.find_by_nombre_completo(nombre_completo)
    if not profesor_target:
        raise HTTPException(status_code=404, detail="Profesor no encontrado")
    if profesor_target.get('es_psi') and current_user['rol'] not in ('admin', 'responsable_area', 'responsable_departamento'):
        raise HTTPException(status_code=403, detail='La elección del profesorado PSI debe gestionarla un responsable.')

    ambito = _obtener_ambito_ordenacion(current_user)
    pertenece_al_ambito = _profesor_pertenece_al_ambito(profesor_target, ambito)
    if not pertenece_al_ambito:
        raise HTTPException(status_code=403, detail="El profesor no pertenece a tu ámbito de ordenación")

    if area_id is not None:
        cargas_area = profesor_target.get("horas_objetivo_por_area") or {}
        horas_en_area = cargas_area.get(area_id, cargas_area.get(str(area_id), 0))
        if area_id not in set(profesor_target.get("area_ids") or []) or float(horas_en_area) <= 0:
            raise HTTPException(status_code=403, detail="El profesor no tiene turno docente en esa área")
        if not ambito["global"] and area_id not in ambito["areas"] and profesor_target["id"] not in ambito["profesores"]:
            raise HTTPException(status_code=403, detail="El área no pertenece a tu ámbito de ordenación")

    if requiere_turno:
        profesor_actual = OrdenacionService().get_profesor_actual(area_id)
        try:
            can_modify_draft(
                current_user["rol"], current_user["user_id"], profesor_target.get("usuario_id"),
                nombre_completo, profesor_actual, pertenece_al_ambito,
            )
        except (PermissionDenied, NotYourTurn) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    return profesor_target


def _areas_con_turnos_visibles(current_user: dict) -> list[dict]:
    """Áreas cuyas colas puede consultar el usuario autenticado."""
    ambito = _obtener_ambito_ordenacion(current_user)
    areas = AreaRepository().find_all()
    if ambito["global"]:
        return areas
    if current_user["rol"] == "profesor":
        profesor = ProfesorRepository().find_by_usuario_id(current_user["user_id"])
        cargas = profesor.get("horas_objetivo_por_area") if profesor else {}
        return [
            area for area in areas
            if profesor and float((cargas or {}).get(area["id"], (cargas or {}).get(str(area["id"]), 0))) > 0
        ]
    return [area for area in areas if area["id"] in ambito["areas"]]


def _filtrar_profesores_por_ambito(profesores: list, ambito: dict) -> list:
    return [
        profesor for profesor in profesores
        if ambito["global"]
        or profesor.id in ambito["profesores"]
        or set(profesor.area_ids or ([profesor.area_id] if profesor.area_id else [])).intersection(ambito["areas"])
    ]


def _verificar_gestion_cierre_area(current_user: dict, area_id: int) -> None:
    """Solo un gestor del ámbito puede cerrar o reabrir una ordenación."""
    if current_user["rol"] not in {"admin", "responsable_area", "responsable_departamento"}:
        raise HTTPException(status_code=403, detail="Solo un responsable o administrador puede cerrar una ordenación.")
    ambito = _obtener_ambito_ordenacion(current_user)
    if not ambito["global"] and area_id not in ambito["areas"]:
        raise HTTPException(status_code=403, detail="El área no pertenece a tu ámbito de gestión.")


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/estado", response_model=EstadoOrdenacionSchema, summary="Estado de la ordenación")
def get_estado(
    current_user: dict = Depends(get_current_user)
):
    """
    Obtiene el estado general de la ordenación.
    
    **Roles permitidos:** TODOS (autenticados)
    """
    service = OrdenacionService()
    try:
        estado = service.get_estado()
        ambito = _obtener_ambito_ordenacion(current_user)
        return {
            "profesor_actual": estado.profesor_actual,
            "ordenacion_terminada": estado.ordenacion_terminada,
            "profesores_completados": _filtrar_profesores_por_ambito(estado.profesores_completados, ambito),
            "profesores_pendientes": _filtrar_profesores_por_ambito(estado.profesores_pendientes, ambito),
            "incidencia": estado.incidencia,
            "version": estado.version,
            "cerrada": estado.cerrada,
            "cerrado_en": estado.cerrado_en,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estado: {str(e)}")


@router.get("/profesor-actual", summary="Profesor actual")
def get_profesor_actual(
    area_id: int | None = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Obtiene el profesor que está en su turno actualmente.
    
    **Roles permitidos:** TODOS (autenticados)
    
    **Retorna:**
    - profesor_actual: string con nombre completo "Apellidos, Nombre" o null
    - ordenacion_terminada: boolean
    """
    service = OrdenacionService()
    try:
        profesor_actual = service.get_profesor_actual(area_id)
        puede_gestionar_turno = False
        if profesor_actual:
            try:
                _verificar_acceso_profesor(current_user, profesor_actual, requiere_turno=True, area_id=area_id)
                puede_gestionar_turno = True
            except HTTPException:
                pass

        return {
            "profesor_actual": profesor_actual,  # String: "García, Juan" o None
            "ordenacion_terminada": profesor_actual is None,
            "puede_gestionar_turno": puede_gestionar_turno,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener profesor actual: {str(e)}")


@router.get("/turnos-activos", summary="Turnos activos por área")
def get_turnos_activos(current_user: dict = Depends(get_current_user)):
    """Devuelve una cola independiente por área dentro del ámbito del usuario."""
    service = OrdenacionService()
    areas_visibles = _areas_con_turnos_visibles(current_user)
    estados = service.get_estados_por_area([area["id"] for area in areas_visibles])
    turnos = []
    for area in areas_visibles:
        estado = estados[area["id"]]
        puede_gestionar = False
        if estado.profesor_actual:
            try:
                _verificar_acceso_profesor(
                    current_user, estado.profesor_actual, requiere_turno=True, area_id=area["id"],
                )
                puede_gestionar = True
            except HTTPException:
                pass
        turnos.append({
            "area": area,
            "en_preparacion": getattr(estado, 'en_preparacion', False),
            "profesor_actual": estado.profesor_actual,
            "ordenacion_terminada": estado.ordenacion_terminada,
            "version": estado.version,
            "cerrada": estado.cerrada,
            "cerrado_en": estado.cerrado_en,
            "puede_gestionar_turno": puede_gestionar,
            "profesores_pendientes": estado.profesores_pendientes,
            "profesores_completados": estado.profesores_completados,
        })
    return turnos


@router.get("/opciones/{nombre_completo:path}", response_model=List[OpcionSchema], summary="Opciones viables")
def get_opciones(
    nombre_completo: str,
    area_id: int,
    offset: int = Query(0, ge=0, description="Número de actividades ya cargadas"),
    limit: int = Query(8, ge=1, le=50, description="Máximo de actividades por bloque"),
    current_user: dict = Depends(get_current_user)
):
    """
    Obtiene las opciones viables para un profesor.
    
    **Parámetros:**
    - nombre_completo: Nombre completo en formato "Apellidos, Nombre"
    """
    # Validación adicional para debugging
    if not nombre_completo or nombre_completo == "[object Object]":
        raise HTTPException(
            status_code=400,
            detail="nombre_completo inválido. Debe ser un string en formato 'Apellidos, Nombre'"
        )
    
    _verificar_acceso_profesor(current_user, nombre_completo, requiere_turno=True, area_id=area_id)
    
    service = OrdenacionService()
    try:
        opciones = service.get_opciones(nombre_completo, area_id, offset=offset, limit=limit)
        if not opciones:
            return []  # Devolver lista vacía en lugar de error
        return opciones
    except NotYourTurn as e:
        raise HTTPException(status_code=403, detail=str(e))
    except OrdenacionClosed as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener opciones: {str(e)}")


@router.get("/borrador/{nombre_completo:path}", response_model=BorradorSchema, summary="Borrador actual")
def get_borrador(
    nombre_completo: str,
    area_id: int | None = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Obtiene el borrador actual de un profesor.
    
    **Parámetros:**
    - nombre_completo: Nombre completo en formato "Apellidos, Nombre"
    """
    if not nombre_completo or nombre_completo == "[object Object]":
        raise HTTPException(
            status_code=400,
            detail="nombre_completo inválido. Debe ser un string en formato 'Apellidos, Nombre'"
        )
    
    _verificar_acceso_profesor(current_user, nombre_completo, area_id=area_id)
    
    service = OrdenacionService()
    try:
        return service.get_borrador(nombre_completo, area_id)
    except ProfesorNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener borrador: {str(e)}")


@router.post("/borrador/{nombre_completo:path}/anadir", summary="Añadir opción al borrador")
def post_anadir_opcion(
    nombre_completo: str,
    body: AnadirOpcionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Añade una opción al borrador."""
    _verificar_acceso_profesor(current_user, nombre_completo, requiere_turno=True, area_id=body.area_id)
    
    service = OrdenacionService()
    try:
        with _edicion_docente(nombre_completo):
            return service.add_to_borrador(
                nombre_completo, body.codigo, body.codigo_grupo, body.tipo.value, body.horas,
                body.actividad_id, body.area_id, body.version_ordenacion, current_user["user_id"],
            )
    except (NotYourTurn, ViabilityLost) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (ConcurrentModification, OrdenacionClosed) as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al añadir opción: {str(e)}")


@router.post("/borrador/{nombre_completo:path}/eliminar", summary="Eliminar opción del borrador")
def post_eliminar_opcion(
    nombre_completo: str,
    body: EliminarOpcionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Elimina una opción del borrador."""
    _verificar_acceso_profesor(current_user, nombre_completo, requiere_turno=True, area_id=body.area_id)
    
    service = OrdenacionService()
    try:
        return service.remove_from_borrador(
            nombre_completo, body.codigo, body.codigo_grupo, body.tipo.value, body.actividad_id,
            body.area_id, body.version_ordenacion, current_user["user_id"],
        )
    except NotYourTurn as e:
        raise HTTPException(status_code=403, detail=str(e))
    except (ConcurrentModification, OrdenacionClosed) as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar opción: {str(e)}")


@router.delete("/borrador/{nombre_completo:path}", summary="Limpiar borrador")
def delete_borrador(
    nombre_completo: str,
    area_id: int,
    version_ordenacion: int | None = None,
    current_user: dict = Depends(get_current_user)
):
    """Limpia completamente el borrador de un profesor."""
    _verificar_acceso_profesor(current_user, nombre_completo, requiere_turno=True, area_id=area_id)
    
    service = OrdenacionService()
    try:
        return service.clear_borrador(nombre_completo, area_id, version_ordenacion, current_user["user_id"])
    except NotYourTurn as e:
        raise HTTPException(status_code=403, detail=str(e))
    except (ConcurrentModification, OrdenacionClosed) as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al limpiar borrador: {str(e)}")


@router.post("/confirmar-turno", response_model=ConfirmacionResultadoSchema, summary="Confirmar turno")
def post_confirmar_turno(
    area_id: int,
    version_ordenacion: int | None = None,
    current_user: dict = Depends(get_current_user)
):
    """Confirma el turno del profesor actual."""
    if current_user["rol"] == "psi":
        raise HTTPException(status_code=403, detail="PSI no puede confirmar turnos")
    
    service = OrdenacionService()
    try:
        profesor_actual = service.get_profesor_actual(area_id)
        
        if not profesor_actual:
            raise HTTPException(status_code=400, detail="No hay turnos pendientes")
        
        _verificar_acceso_profesor(current_user, profesor_actual, requiere_turno=True, area_id=area_id)
        
        with _edicion_docente(profesor_actual):
            return service.confirmar_turno(area_id, version_ordenacion, current_user["user_id"])
    except OrdenacionFinished as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except (IncompleteTurn, ViabilityLost) as e:
        raise HTTPException(status_code=422, detail=str(e))
    except (ConcurrentModification, OrdenacionClosed) as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al confirmar turno: {str(e)}")


@router.post(
    "/adjudicaciones/{actividad_id}/devolver",
    summary="Devolver una adjudicación concreta para revisión",
)
def post_devolver_adjudicacion(
    actividad_id: int,
    body: DevolverAdjudicacionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Mueve una única adjudicación confirmada a revisión prioritaria.

    Solo administración o responsables del ámbito del área pueden iniciar la
    devolución. La actividad vuelve al borrador del profesor afectado, no se
    eliminan otras confirmaciones y queda un evento con el motivo.
    """
    motivo = body.motivo.strip()
    if len(motivo) < 3:
        raise HTTPException(status_code=422, detail="Indica un motivo de al menos 3 caracteres.")
    _verificar_gestion_cierre_area(current_user, body.area_id)
    try:
        return OrdenacionService().devolver_adjudicacion(
            actividad_id=actividad_id,
            profesor_id=body.profesor_id,
            area_id=body.area_id,
            motivo=motivo,
            usuario_id=current_user["user_id"],
            version_ordenacion=body.version_ordenacion,
        )
    except ConcurrentModification as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ConstraintViolation as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al devolver la adjudicación: {str(e)}")


@router.get("/areas/{area_id}/conflictos", summary="Consultar propuestas de resolución de conflictos")
def get_conflictos_area(
    area_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Muestra planes pendientes e historial de decisiones del área."""
    _verificar_gestion_cierre_area(current_user, area_id)
    return OrdenacionService().get_propuestas_conflicto(area_id)


@router.post("/areas/{area_id}/conflictos/propuestas", summary="Proponer un intercambio para un turno bloqueado")
def post_propuesta_conflicto(
    area_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Calcula, sin aplicarla, la alternativa mínima para el turno actual.

    Solo se crea si ese turno no conserva ninguna opción viable. La propuesta
    queda pendiente de aprobación explícita en el apartado Conflictos.
    """
    _verificar_gestion_cierre_area(current_user, area_id)
    try:
        return OrdenacionService().crear_propuesta_conflicto(area_id, current_user["user_id"])
    except ConstraintViolation as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except ViabilityLost as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except (ConcurrentModification, OrdenacionClosed) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al calcular la propuesta: {str(e)}") from e


@router.post("/areas/{area_id}/conflictos/{propuesta_id}/decision", summary="Aprobar o rechazar una propuesta de conflicto")
def post_decision_conflicto(
    area_id: int,
    propuesta_id: int,
    body: DecidirConflictoRequest,
    current_user: dict = Depends(get_current_user),
):
    _verificar_gestion_cierre_area(current_user, area_id)
    motivo = (body.motivo or "").strip()
    if not body.aprobar and len(motivo) < 3:
        raise HTTPException(status_code=422, detail="Indica el motivo del rechazo (al menos 3 caracteres).")
    try:
        return OrdenacionService().decidir_propuesta_conflicto(
            propuesta_id, area_id, body.aprobar, current_user["user_id"], motivo or None,
        )
    except ConstraintViolation as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except (ConcurrentModification, OrdenacionClosed) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al decidir la propuesta: {str(e)}") from e


@router.get("/areas/{area_id}/cierre", response_model=ControlOrdenacionSchema, summary="Validar cierre de área")
def get_validacion_cierre_area(
    area_id: int,
    current_user: dict = Depends(get_current_user),
):
    _verificar_gestion_cierre_area(current_user, area_id)
    resultado = OrdenacionService().validar_cierre_area(area_id)
    return {
        "area_id": area_id,
        "version": resultado["version"],
        "cerrada": resultado["cerrada"],
        "advertencias": resultado["advertencias"] + resultado["errores"],
    }


@router.post("/areas/{area_id}/cerrar", response_model=ControlOrdenacionSchema, summary="Cerrar ordenación de área")
def post_cerrar_area(
    area_id: int,
    body: CierreAreaRequest,
    current_user: dict = Depends(get_current_user),
):
    _verificar_gestion_cierre_area(current_user, area_id)
    try:
        resultado = OrdenacionService().cerrar_area(area_id, body.version_ordenacion, current_user["user_id"])
        return resultado
    except OrdenacionClosureInvalid as e:
        raise HTTPException(status_code=422, detail=e.message) from e
    except (ConcurrentModification, OrdenacionClosed) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/areas/{area_id}/reabrir", response_model=ControlOrdenacionSchema, summary="Reabrir ordenación de área")
def post_reabrir_area(
    area_id: int,
    body: ReaperturaAreaRequest,
    current_user: dict = Depends(get_current_user),
):
    _verificar_gestion_cierre_area(current_user, area_id)
    motivo = body.motivo.strip()
    if len(motivo) < 3:
        raise HTTPException(status_code=422, detail="Indica el motivo de la reapertura.")
    try:
        return OrdenacionService().reabrir_area(area_id, body.version_ordenacion, current_user["user_id"], motivo)
    except (ConcurrentModification, OrdenacionClosed, ConstraintViolation) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/areas/{area_id}/eventos", response_model=List[EventoOrdenacionSchema], summary="Historial de ordenación")
def get_eventos_area(
    area_id: int,
    current_user: dict = Depends(get_current_user),
):
    _verificar_gestion_cierre_area(current_user, area_id)
    return RepartoRepository().get_eventos_area(area_id)


@router.post("/reset-ordenacion", summary="Resetear ordenación")
def post_reset_ordenacion(
    current_user: dict = Depends(require_admin)
):
    """
    Resetea completamente la ordenación docente.
    
    **Roles permitidos:** ADMIN
    """
    service = OrdenacionService()
    try:
        return service.reset_ordenacion()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al resetear ordenación: {str(e)}")
