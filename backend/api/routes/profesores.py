"""
API Routes - Profesores.

Endpoints CRUD para gestión de profesores.
"""

from typing import List, Optional, Literal
from datetime import date, datetime
from io import BytesIO
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field

from services import ProfesorService
from repositories import ProfesorRepository, RepartoRepository
from core.exceptions import ProfesorNotFound, DuplicateResourceError, ConstraintViolation
from core.auth import get_current_user, require_admin
from core.ambito_gestion import obtener_ambito_gestor

router = APIRouter(prefix="/api/v1/profesores", tags=["profesores"])


# ═══════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════

class CreateProfesorRequest(BaseModel):
    """Request para crear profesor."""
    usuario_id: Optional[int] = None
    nombre: str
    apellidos: str
    categoria: str
    fecha_ingreso: date
    carga_docente: float
    area_id: Optional[int] = None
    area_ids: List[int] = Field(default_factory=list)
    horas_objetivo_por_area: Optional[dict[int, float]] = None
    es_psi: bool = False
    disponibilidad_cuatrimestre: Literal["PRIMERO", "SEGUNDO", "AMBOS"] = "AMBOS"
    prioridades_asignaturas: List[str] = Field(default_factory=list)


class UpdateProfesorRequest(BaseModel):
    """Request para actualizar profesor."""
    usuario_id: Optional[int] = None
    nombre: Optional[str] = None
    apellidos: Optional[str] = None
    categoria: Optional[str] = None
    fecha_ingreso: Optional[date] = None
    carga_docente: Optional[float] = None
    area_id: Optional[int] = None
    area_ids: Optional[List[int]] = None
    horas_objetivo_por_area: Optional[dict[int, float]] = None
    es_psi: Optional[bool] = None
    disponibilidad_cuatrimestre: Optional[Literal["PRIMERO", "SEGUNDO", "AMBOS"]] = None
    prioridades_asignaturas: Optional[List[str]] = None


class UpdateMiDisponibilidadRequest(BaseModel):
    disponibilidad_cuatrimestre: Literal["PRIMERO", "SEGUNDO", "AMBOS"]


class UpdateMisPrioridadesAsignaturasRequest(BaseModel):
    """Lista de códigos de asignatura, ordenada de mayor a menor prioridad."""
    prioridades_asignaturas: List[str] = Field(default_factory=list)


class CreateProfesorConCuentaRequest(CreateProfesorRequest):
    """Alta manual y atómica de la cuenta y el perfil docente."""
    email: EmailStr
    password: str = Field(min_length=12)
    # La cuenta docente no puede asumir una responsabilidad institucional.
    # Dichas cuentas se crean y asignan desde el área o departamento.
    rol: Literal["profesor", "psi"] = "profesor"


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _areas_de_profesor(profesor: dict) -> set[int]:
    return set(profesor.get("area_ids") or ([profesor["area_id"]] if profesor.get("area_id") else []))


def _areas_solicitadas(body: CreateProfesorRequest | UpdateProfesorRequest) -> set[int]:
    area_ids = getattr(body, "area_ids", None)
    if area_ids is not None:
        return set(area_ids)
    area_id = getattr(body, "area_id", None)
    return {area_id} if area_id else set()

def _verificar_acceso_profesor(current_user: dict, profesor_id: int, operacion: str):
    """
    Verifica acceso según rol:
    - ADMIN: Acceso total
    - RESPONSABLE_DEPARTAMENTO: Solo profesores de su departamento
    - RESPONSABLE_AREA: Solo profesores de su área
    - PROFESOR/PSI: Solo lectura de su área
    """
    rol = current_user["rol"]
    
    # ADMIN puede todo
    if rol == "admin":
        return True
    
    # Obtener profesor objetivo
    repo = ProfesorRepository()
    profesor_target = repo.find_by_id(profesor_id)
    
    if not profesor_target:
        raise HTTPException(status_code=404, detail="Profesor no encontrado")
    if rol in {'responsable_area', 'responsable_departamento'} and operacion != 'read':
        ambito = obtener_ambito_gestor(current_user['user_id'], rol)
        if not _areas_de_profesor(profesor_target).issubset(ambito['areas']):
            raise HTTPException(status_code=403, detail='Este perfil es compartido. Su modificación requiere un gestor con acceso a todas sus áreas.')
    
    # RESPONSABLE_DEPARTAMENTO
    if rol == "responsable_departamento":
        ambito = obtener_ambito_gestor(current_user["user_id"], rol)
        if not ambito["departamentos"].intersection(profesor_target.get("departamento_ids") or []):
            raise HTTPException(status_code=403, detail="Solo puedes gestionar profesores de tu departamento")
        
        # Puede crear, editar, eliminar
        if operacion in ["create", "update", "delete", "read"]:
            return True
        
        raise HTTPException(status_code=403, detail="Operación no permitida")
    
    # RESPONSABLE_AREA
    if rol == "responsable_area":
        ambito = obtener_ambito_gestor(current_user["user_id"], rol)
        if not ambito["areas"].intersection(_areas_de_profesor(profesor_target)):
            raise HTTPException(status_code=403, detail="Solo puedes gestionar profesores de tu área")
        
        # Puede crear, editar, eliminar
        if operacion in ["create", "update", "delete", "read"]:
            return True
        
        raise HTTPException(status_code=403, detail="Operación no permitida")
    
    # PROFESOR/PSI: solo lectura de su área
    if rol in ["profesor", "psi"]:
        usuario_autenticado = repo.find_by_usuario_id(current_user["user_id"])
        if not usuario_autenticado:
            raise HTTPException(status_code=403, detail="No tienes perfil de profesor")
        if operacion != "read":
            raise HTTPException(status_code=403, detail="No tienes permisos para modificar profesores")
        
        # Solo pueden ver profesores de su área
        if not _areas_de_profesor(usuario_autenticado).intersection(_areas_de_profesor(profesor_target)):
            raise HTTPException(status_code=403, detail="Solo puedes ver profesores de tu área")
        
        return True
    
    raise HTTPException(status_code=403, detail="Acceso denegado")


def _filtrar_profesores_por_acceso(current_user: dict, profesores: List[dict]) -> List[dict]:
    """
    Filtra la lista de profesores según el acceso del usuario.
    """
    rol = current_user["rol"]
    
    # ADMIN ve todos
    if rol == "admin":
        return profesores
    
    # RESPONSABLE_DEPARTAMENTO: solo su departamento
    if rol == "responsable_departamento":
        ambito = obtener_ambito_gestor(current_user["user_id"], rol)
        return [p for p in profesores if ambito["departamentos"].intersection(p.get("departamento_ids") or [])]
    if rol == "responsable_area":
        ambito = obtener_ambito_gestor(current_user["user_id"], rol)
        return [p for p in profesores if ambito["areas"].intersection(_areas_de_profesor(p))]
    
    # PROFESOR, PSI: solo su área docente.
    repo = ProfesorRepository()
    usuario_autenticado = repo.find_by_usuario_id(current_user["user_id"])
    if not usuario_autenticado:
        return []
    areas = _areas_de_profesor(usuario_autenticado)
    return [p for p in profesores if areas.intersection(_areas_de_profesor(p))]


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/", summary="Listar profesores")
def get_profesores(
    incluir_psi: bool = True,
    current_user: dict = Depends(get_current_user)  # ✅ Todos autenticados
):
    """
    Obtiene profesores según permisos del usuario.
    
    **Roles permitidos:**
    - ADMIN: Todos los profesores
    - RESPONSABLE_DEPARTAMENTO: Profesores de su departamento
    - RESPONSABLE_AREA: Profesores de su área
    - PROFESOR/PSI: Profesores de su área (solo lectura)
    """
    service = ProfesorService()
    profesores = service.get_all(incluir_psi=incluir_psi)
    
    # Filtrar según acceso
    visibles = _filtrar_profesores_por_acceso(current_user, profesores)
    ids_visibles = {int(profesor["id"]) for profesor in visibles}
    horas_confirmadas: dict[int, float] = {}
    for reparto in RepartoRepository().find_all_confirmadas():
        profesor_id = int(reparto["profesor_id"])
        if profesor_id in ids_visibles:
            horas_confirmadas[profesor_id] = horas_confirmadas.get(profesor_id, 0.0) + float(reparto["horas"])
    return [
        {**profesor, "horas_confirmadas": round(horas_confirmadas.get(int(profesor["id"]), 0.0), 1)}
        for profesor in visibles
    ]


@router.get("/exportar", summary="Exportar directorio de profesores")
def exportar_directorio_profesores(
    formato: Literal["xlsx", "pdf"] = "xlsx",
    incluir_psi: bool = True,
    current_user: dict = Depends(get_current_user),
):
    """Exporta los perfiles docentes visibles, con sus cargas confirmadas."""
    profesores = _filtrar_profesores_por_acceso(
        current_user, ProfesorService().get_all(incluir_psi=incluir_psi),
    )
    horas_confirmadas: dict[int, float] = {}
    for reparto in RepartoRepository().find_all_confirmadas():
        profesor_id = int(reparto["profesor_id"])
        horas_confirmadas[profesor_id] = horas_confirmadas.get(profesor_id, 0.0) + float(reparto["horas"])

    filas: list[list[object]] = []
    for profesor in profesores:
        carga = float(profesor.get("carga_docente", 0))
        confirmadas = round(horas_confirmadas.get(int(profesor["id"]), 0.0), 1)
        restantes = round(carga - confirmadas, 1)
        estado = "Completo" if abs(restantes) < 0.01 else "Excedido" if restantes < 0 else "Incompleto"
        areas = ", ".join(
            f"{area.get('codigo', '')} - {area.get('nombre', '')}".strip(" -")
            for area in profesor.get("areas", [])
        ) or "Sin área"
        carga_por_area = ", ".join(
            f"{area.get('codigo', area.get('id'))}: {float(area.get('horas_objetivo', 0)):.1f} h"
            for area in profesor.get("areas", [])
        ) or "Sin carga por área"
        filas.append([
            f"{profesor.get('apellidos', '')}, {profesor.get('nombre', '')}".strip(", "),
            profesor.get("categoria") or "", areas, carga, confirmadas, restantes,
            profesor.get("fecha_ingreso"), carga_por_area,
            "PSI" if profesor.get("es_psi") else "Profesor/a", estado,
            {
                "PRIMERO": "Solo 1.º cuatrimestre",
                "SEGUNDO": "Solo 2.º cuatrimestre",
                "AMBOS": "Ambos cuatrimestres",
            }.get(profesor.get("disponibilidad_cuatrimestre"), "Ambos cuatrimestres"),
        ])

    try:
        from services.exportacion_adjudicaciones import generar_excel_tabular, generar_pdf_tabular
        if formato == "xlsx":
            contenido = generar_excel_tabular(
                "Directorio de profesorado", "Profesores",
                ["Profesor/a", "Categoría", "Área(s)", "Carga docente", "Horas confirmadas", "Horas restantes", "Fecha de ingreso", "Carga por área", "Perfil", "Estado", "Disponibilidad"],
                filas, [30, 18, 38, 18, 20, 18, 19, 40, 14, 14, 24],
                [("Profesores", len(filas)), ("Carga docente total", sum(float(fila[3]) for fila in filas)), ("Horas confirmadas", sum(float(fila[4]) for fila in filas))],
                {3: '0.0 "h"', 4: '0.0 "h"', 5: '0.0 "h"'},
            )
        else:
            filas_pdf = [[fila[0], fila[1], fila[2], fila[3], fila[4], fila[5], fila[6], fila[9], fila[10]] for fila in filas]
            contenido = generar_pdf_tabular(
                "Directorio de profesorado",
                ["Profesor/a", "Categoría", "Área(s)", "Carga docente", "H. confirmadas", "H. restantes", "Fecha ingreso", "Estado", "Disponibilidad"],
                filas_pdf, [2.8, 1.5, 2.9, 1.2, 1.3, 1.3, 1.5, 1.2, 2.1],
                f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}. {len(filas)} profesor(es) visibles.",
                {3, 4, 5},
            )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="El módulo de exportación no está instalado todavía.") from exc

    fecha = datetime.now().strftime("%Y-%m-%d")
    extension = "xlsx" if formato == "xlsx" else "pdf"
    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if formato == "xlsx" else "application/pdf"
    return StreamingResponse(
        BytesIO(contenido), media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="directorio_profesores_{fecha}.{extension}"', "Cache-Control": "no-store"},
    )


@router.post("/con-cuenta", status_code=status.HTTP_201_CREATED, summary="Crear profesor con cuenta")
def create_profesor_con_cuenta(
    body: CreateProfesorConCuentaRequest,
    current_user: dict = Depends(get_current_user),
):
    """Crea una cuenta y su perfil docente en una única transacción.

    Es el flujo manual del administrador: nunca exige conocer identificadores
    internos y no deja una cuenta huérfana si no se puede crear el profesor.
    """
    if body.categoria.strip().upper() == 'PSI':
        body.es_psi = True
        body.rol = 'psi'
    if body.es_psi != (body.rol == "psi"):
        raise HTTPException(
            status_code=400,
            detail="El rol y la marca PSI deben ser coherentes.",
        )

    from db.connection import conexion_ctx
    from core.auth import get_password_hash
    from repositories import MapeoRepository
    from solver.cache import solver_cache

    areas = list(dict.fromkeys(body.area_ids or ([body.area_id] if body.area_id else [])))
    if not areas:
        raise HTTPException(status_code=400, detail="Selecciona al menos un área para el profesor.")
    if current_user['rol'] not in {'admin', 'responsable_area', 'responsable_departamento'}:
        raise HTTPException(status_code=403, detail='Solo los gestores pueden crear cuentas docentes.')
    if current_user['rol'] != 'admin':
        ambito = obtener_ambito_gestor(current_user['user_id'], current_user['rol'])
        if not set(areas).issubset(ambito['areas']):
            raise HTTPException(status_code=403, detail='Todas las áreas del profesor deben pertenecer a tu ámbito. Para un perfil compartido, contacta con un gestor de todas sus áreas.')
    cargas = body.horas_objetivo_por_area or {}
    if not cargas:
        base = round(float(body.carga_docente) / len(areas), 1)
        cargas = {area_id: base for area_id in areas}
        cargas[areas[0]] = round(float(body.carga_docente) - base * (len(areas) - 1), 1)
    if set(cargas) != set(areas) or any(float(horas) < 0 for horas in cargas.values()):
        raise HTTPException(status_code=400, detail="Indica una carga no negativa para cada área del profesor.")
    if abs(sum(float(horas) for horas in cargas.values()) - float(body.carga_docente)) > 0.01:
        raise HTTPException(status_code=400, detail="La suma de cargas por área debe coincidir con la carga docente total.")

    try:
        with conexion_ctx() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM usuarios WHERE email=%s", (str(body.email),))
            if cur.fetchone():
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya existe un usuario con email '{body.email}'.",
                )

            cur.execute(
                "SELECT id FROM profesores WHERE nombre=%s AND apellidos=%s",
                (body.nombre, body.apellidos),
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya existe un profesor llamado '{body.apellidos}, {body.nombre}'.",
                )

            cur.execute(
                """
                INSERT INTO usuarios (nombre, apellidos, email, password_hash, rol, activo)
                VALUES (%s, %s, %s, %s, %s, TRUE)
                RETURNING id
                """,
                (
                    body.nombre,
                    body.apellidos,
                    str(body.email),
                    get_password_hash(body.password),
                    body.rol,
                ),
            )
            usuario_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO profesores (
                    usuario_id, nombre, apellidos, categoria, fecha_ingreso,
                    carga_docente, area_id, es_psi, disponibilidad_cuatrimestre
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    usuario_id,
                    body.nombre,
                    body.apellidos,
                    body.categoria,
                    body.fecha_ingreso,
                    body.carga_docente,
                    areas[0],
                    body.es_psi,
                    body.disponibilidad_cuatrimestre,
                ),
            )
            profesor_id = cur.fetchone()[0]
            cur.executemany(
                "INSERT INTO profesor_areas (profesor_id, area_id, horas_objetivo) VALUES (%s, %s, %s)",
                [(profesor_id, area_id, cargas[area_id]) for area_id in areas],
            )
            ProfesorRepository._guardar_prioridades_asignaturas(
                cur, profesor_id, body.prioridades_asignaturas, areas,
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="No se pudo crear la cuenta y el perfil docente. Revisa categoría y área.",
        ) from exc

    solver_cache.clear()
    MapeoRepository().clear_cache()
    return ProfesorRepository().find_by_id(profesor_id)


@router.get("/mi", summary="Obtener mi perfil docente")
def get_mi_profesor(
    current_user: dict = Depends(get_current_user),
):
    """Devuelve únicamente el perfil docente asociado a la cuenta actual.

    Un administrador que no tenga perfil docente recibe ``null``, igual que
    ocurría cuando el cliente buscaba su ``usuario_id`` dentro del directorio
    completo. Evita descargar todos los profesores al iniciar sesión o abrir
    el perfil propio.
    """
    return ProfesorRepository().find_by_usuario_id(current_user["user_id"])


@router.put("/mi/disponibilidad", summary="Actualizar mi disponibilidad por cuatrimestre")
def actualizar_mi_disponibilidad(
    body: UpdateMiDisponibilidadRequest,
    current_user: dict = Depends(get_current_user),
):
    """Permite que cada docente indique el cuatrimestre en que puede impartir."""
    profesor = ProfesorRepository().find_by_usuario_id(current_user["user_id"])
    if not profesor:
        raise HTTPException(status_code=403, detail="Tu cuenta no tiene un perfil docente asociado.")
    return ProfesorService().update(
        profesor["id"], disponibilidad_cuatrimestre=body.disponibilidad_cuatrimestre,
    )


@router.put("/mi/prioridades-asignaturas", summary="Actualizar mis prioridades de asignaturas")
def actualizar_mis_prioridades_asignaturas(
    body: UpdateMisPrioridadesAsignaturasRequest,
    current_user: dict = Depends(get_current_user),
):
    """Cada docente puede ordenar únicamente las asignaturas de sus áreas."""
    profesor = ProfesorRepository().find_by_usuario_id(current_user["user_id"])
    if not profesor:
        raise HTTPException(status_code=403, detail="Tu cuenta no tiene un perfil docente asociado.")
    try:
        return ProfesorService().update(
            profesor["id"], prioridades_asignaturas=body.prioridades_asignaturas,
        )
    except ConstraintViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{profesor_id}", summary="Obtener profesor por ID")
def get_profesor(
    profesor_id: int,
    current_user: dict = Depends(get_current_user)  # ✅ Verificar acceso
):
    """
    Obtiene un profesor específico.
    
    **Roles permitidos:**
    - ADMIN: Cualquier profesor
    - RESPONSABLE_DEPARTAMENTO: Profesores de su departamento
    - RESPONSABLE_AREA: Profesores de su área
    - PROFESOR/PSI: Profesores de su área
    """
    _verificar_acceso_profesor(current_user, profesor_id, "read")
    
    service = ProfesorService()
    try:
        return service.get_by_id(profesor_id)
    except ProfesorNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/", status_code=status.HTTP_201_CREATED, summary="Crear profesor")
def create_profesor(
    body: CreateProfesorRequest,
    current_user: dict = Depends(get_current_user)  # ✅ Verificar permisos
):
    """
    Crea un nuevo profesor.
    
    **Roles permitidos:**
    - ADMIN: Puede crear en cualquier área/departamento
    - RESPONSABLE_DEPARTAMENTO: Solo en su departamento
    - RESPONSABLE_AREA: Solo en su área
    - PROFESOR/PSI: No permitido
    """
    rol = current_user["rol"]
    
    # PROFESOR/PSI no pueden crear
    if rol in ["profesor", "psi"]:
        raise HTTPException(status_code=403, detail="No tienes permisos para crear profesores")
    
    # Si no es ADMIN, verificar que crea en su ámbito
    if rol != "admin":
        from repositories import AreaRepository
        areas_solicitadas = _areas_solicitadas(body)
        if not areas_solicitadas:
            raise HTTPException(status_code=400, detail="Selecciona al menos un área para el profesor")
        area_repo = AreaRepository()
        if rol == "responsable_departamento":
            ambito = obtener_ambito_gestor(current_user["user_id"], rol)
            if any((not (area := area_repo.find_by_id(area_id))) or area["departamento_id"] not in ambito["departamentos"] for area_id in areas_solicitadas):
                raise HTTPException(status_code=403, detail="Solo puedes crear profesores en áreas de tu departamento")
        elif rol == "responsable_area":
            ambito = obtener_ambito_gestor(current_user["user_id"], rol)
            if not areas_solicitadas.issubset(ambito["areas"]):
                raise HTTPException(status_code=403, detail="Solo puedes crear profesores en tus áreas")
    
    service = ProfesorService()
    try:
        return service.create(
            usuario_id=body.usuario_id,
            nombre=body.nombre,
            apellidos=body.apellidos,
            categoria=body.categoria,
            fecha_ingreso=body.fecha_ingreso,
            carga_docente=body.carga_docente,
            area_id=body.area_id,
            area_ids=body.area_ids,
            horas_objetivo_por_area=body.horas_objetivo_por_area,
            es_psi=body.es_psi,
            disponibilidad_cuatrimestre=body.disponibilidad_cuatrimestre,
            prioridades_asignaturas=body.prioridades_asignaturas,
        )
    except DuplicateResourceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConstraintViolation as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{profesor_id}", summary="Actualizar profesor")
def update_profesor(
    profesor_id: int,
    body: UpdateProfesorRequest,
    current_user: dict = Depends(get_current_user)  # ✅ Verificar permisos
):
    """
    Actualiza un profesor existente.
    
    **Roles permitidos:**
    - ADMIN: Cualquier profesor
    - RESPONSABLE_DEPARTAMENTO: Profesores de su departamento
    - RESPONSABLE_AREA: Profesores de su área
    - PROFESOR/PSI: No permitido
    """
    _verificar_acceso_profesor(current_user, profesor_id, "update")
    if current_user['rol'] != 'admin':
        ambito = obtener_ambito_gestor(current_user['user_id'], current_user['rol'])
        nuevas = _areas_solicitadas(body)
        if not nuevas.issubset(ambito['areas']) or (body.area_id is not None and body.area_id not in ambito['areas']):
            raise HTTPException(status_code=403, detail='No puedes asignar áreas fuera de tu ámbito.')
        if body.usuario_id is not None:
            raise HTTPException(status_code=403, detail='Solo administración puede cambiar la cuenta asociada a un perfil existente.')
    
    service = ProfesorService()
    try:
        return service.update(
            profesor_id=profesor_id,
            usuario_id=body.usuario_id,
            nombre=body.nombre,
            apellidos=body.apellidos,
            categoria=body.categoria,
            fecha_ingreso=body.fecha_ingreso,
            carga_docente=body.carga_docente,
            area_id=body.area_id,
            area_ids=body.area_ids,
            horas_objetivo_por_area=body.horas_objetivo_por_area,
            es_psi=body.es_psi,
            disponibilidad_cuatrimestre=body.disponibilidad_cuatrimestre,
            prioridades_asignaturas=body.prioridades_asignaturas,
        )
    except ProfesorNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConstraintViolation as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{profesor_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar profesor")
def delete_profesor(
    profesor_id: int,
    current_user: dict = Depends(get_current_user)  # ✅ Verificar permisos
):
    """
    Elimina un profesor.
    
    **Roles permitidos:**
    - ADMIN: Cualquier profesor
    - RESPONSABLE_DEPARTAMENTO: Profesores de su departamento
    - RESPONSABLE_AREA: Profesores de su área
    - PROFESOR/PSI: No permitido
    """
    _verificar_acceso_profesor(current_user, profesor_id, "delete")
    
    service = ProfesorService()
    try:
        service.delete(profesor_id)
    except ProfesorNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConstraintViolation as e:
        raise HTTPException(status_code=400, detail=str(e))
