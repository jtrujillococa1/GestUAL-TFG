"""
API Routes - Actividades.

Endpoints CRUD para gestión de actividades docentes.
"""

from datetime import date, datetime
from io import BytesIO
from typing import List, Literal, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from services import ActividadService
from repositories import (
    ActividadRepository, ProfesorRepository, RepartoRepository,
    AreaRepository, DepartamentoRepository,
)
from core.exceptions import ActividadNotFound, DuplicateResourceError, ConstraintViolation
from core.auth import get_current_user
from core.ambito_gestion import obtener_ambito_gestor
from core.horario import validar_franjas_horarias, validar_sesion_horaria

router = APIRouter(prefix="/api/v1/actividades", tags=["actividades"])

_CAMPOS_ACADEMICOS = (
    "nombre_asignatura", "tipo_estudio", "codigo_plan", "nombre_plan",
    "codigo_centro", "nombre_centro", "ciclo", "curso", "caracter",
    "actividad_oficial_id", "nombre_actividad", "codigo_grupo_oficial",
    "curso_academico", "horario_confirmado", "origen_horario",
    "horario_detallado", "fuente_horario",
)


def _metadata_academica(body: BaseModel, incluir_nulos: bool = False) -> dict:
    """Extrae metadatos del CSV sin mezclarlo con la lógica de ordenación."""
    metadata = {}
    for campo in _CAMPOS_ACADEMICOS:
        valor = getattr(body, campo)
        if not incluir_nulos and valor is None:
            continue
        if campo == "horario_detallado":
            valor = [sesion.model_dump(mode="json") for sesion in valor]
        metadata[campo] = valor
    return metadata


def _validar_franjas_horarias(horario: str) -> None:
    """Alias privado para conservar el contrato interno de la ruta."""
    validar_franjas_horarias(horario)


def _areas_de_actividad(actividad: dict) -> set[int]:
    """Áreas académicas visibles de la actividad (incluye su cuota principal)."""
    return set(
        actividad.get("area_ids")
        or ([actividad["area_id"]] if actividad.get("area_id") else [])
    )


# ═══════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════

class CuotaAreaRequest(BaseModel):
    """Parte de una actividad compartida que se ordena desde un área."""
    area_id: int = Field(gt=0)
    horas: float = Field(gt=0)


class HorarioDetalladoRequest(BaseModel):
    """Sesión trazable de un horario oficial o capturado manualmente."""
    fecha: Optional[date] = None
    dia: str = Field(min_length=3, max_length=12)
    inicio: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    fin: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")

    @model_validator(mode="after")
    def validar_sesion(self):
        validar_sesion_horaria(self.inicio, self.fin)
        return self


class CreateActividadRequest(BaseModel):
    """Request para crear actividad."""
    codigo: str
    tipo: str
    codigo_grupo: str
    grupo: str
    idioma: Optional[str] = None
    duracion: str
    turno: str
    requiere_horario: bool = True
    dias: Optional[str] = Field(default=None, max_length=100)
    horario: Optional[str] = Field(default=None, max_length=500)
    horario_confirmado: bool = False
    origen_horario: str = "PENDIENTE"
    horario_detallado: List[HorarioDetalladoRequest] = Field(default_factory=list)
    fuente_horario: Optional[str] = Field(default=None, max_length=500)
    horas_asignatura: float
    horas_actividad: float
    horas_area: float
    area_id: Optional[int] = None
    # Una fila de actividad representa la cuota de un área. Cuando el mismo
    # grupo se oferta desde varias áreas se crean sus cuotas en una única
    # operación, conservando idénticos grupo y horario.
    area_ids: List[int] = Field(default_factory=list)
    cuotas_por_area: List[CuotaAreaRequest] = Field(default_factory=list)
    nombre_asignatura: Optional[str] = None
    tipo_estudio: Optional[str] = None
    codigo_plan: Optional[str] = None
    nombre_plan: Optional[str] = None
    codigo_centro: Optional[str] = None
    nombre_centro: Optional[str] = None
    ciclo: Optional[str] = None
    curso: Optional[str] = None
    caracter: Optional[str] = None
    actividad_oficial_id: Optional[str] = None
    nombre_actividad: Optional[str] = None
    codigo_grupo_oficial: Optional[str] = None
    curso_academico: Optional[str] = None

    @model_validator(mode="after")
    def validar_horario_y_areas(self):
        if self.requiere_horario:
            self.dias = (self.dias or "").strip()
            self.horario = (self.horario or "").strip()
            if not self.dias or not self.horario:
                raise ValueError("Indica al menos una sesión o marca que la actividad no tiene horario fijo.")
            _validar_franjas_horarias(self.horario)
        else:
            self.dias = None
            self.horario = None
            self.horario_confirmado = False
            self.origen_horario = "NO_APLICA"

        if self.cuotas_por_area:
            if len({cuota.area_id for cuota in self.cuotas_por_area}) != len(self.cuotas_por_area):
                raise ValueError("No repitas un área en las cuotas de la actividad.")
            if abs(sum(cuota.horas for cuota in self.cuotas_por_area) - self.horas_actividad) > 0.01:
                raise ValueError("La suma de las cuotas por área debe coincidir con las horas de actividad.")
            self.area_ids = [cuota.area_id for cuota in self.cuotas_por_area]

        areas = self.area_ids or ([self.area_id] if self.area_id else [])
        areas = list(dict.fromkeys(areas))
        if not areas or any(area_id < 1 for area_id in areas):
            raise ValueError("Selecciona al menos un área para la actividad.")
        self.area_ids = areas
        self.area_id = areas[0]
        return self


class UpdateActividadRequest(BaseModel):
    """Request para actualizar actividad."""
    codigo: Optional[str] = None
    tipo: Optional[str] = None
    codigo_grupo: Optional[str] = None
    grupo: Optional[str] = None
    idioma: Optional[str] = None
    duracion: Optional[str] = None
    turno: Optional[str] = None
    requiere_horario: Optional[bool] = None
    dias: Optional[str] = None
    horario: Optional[str] = None
    horario_confirmado: Optional[bool] = None
    origen_horario: Optional[str] = None
    horario_detallado: Optional[List[HorarioDetalladoRequest]] = None
    fuente_horario: Optional[str] = Field(default=None, max_length=500)
    horas_asignatura: Optional[float] = None
    horas_actividad: Optional[float] = None
    horas_area: Optional[float] = None
    area_id: Optional[int] = None
    area_ids: Optional[List[int]] = None
    nombre_asignatura: Optional[str] = None
    tipo_estudio: Optional[str] = None
    codigo_plan: Optional[str] = None
    nombre_plan: Optional[str] = None
    codigo_centro: Optional[str] = None
    nombre_centro: Optional[str] = None
    ciclo: Optional[str] = None
    curso: Optional[str] = None
    caracter: Optional[str] = None
    actividad_oficial_id: Optional[str] = None
    nombre_actividad: Optional[str] = None
    codigo_grupo_oficial: Optional[str] = None
    curso_academico: Optional[str] = None

    @model_validator(mode="after")
    def validar_campos_horario_presentes(self):
        if self.requiere_horario is False:
            return self
        if "dias" in self.model_fields_set and not (self.dias or "").strip():
            raise ValueError("Indica al menos un día o marca que la actividad no tiene horario fijo.")
        if "horario" in self.model_fields_set:
            horario = (self.horario or "").strip()
            if not horario:
                raise ValueError("Toda actividad debe incluir al menos una franja horaria.")
            _validar_franjas_horarias(horario)
        if self.area_ids is not None:
            self.area_ids = list(dict.fromkeys(self.area_ids))
            if not self.area_ids or any(area_id < 1 for area_id in self.area_ids):
                raise ValueError("Selecciona al menos un área para la actividad.")
        return self


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _verificar_acceso_actividad(current_user: dict, actividad_id: int, operacion: str):
    """
    Verifica acceso según rol:
    - ADMIN: Acceso total
    - RESPONSABLE_DEPARTAMENTO: Solo actividades de áreas de su departamento
    - RESPONSABLE_AREA: Solo actividades de su área
    - PROFESOR/PSI: Solo lectura de su área
    """
    rol = current_user["rol"]
    
    # ADMIN puede todo
    if rol == "admin":
        return True
    
    # Obtener actividad objetivo
    repo = ActividadRepository()
    actividad_target = repo.find_by_id(actividad_id)
    
    if not actividad_target:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    if rol in {'responsable_area', 'responsable_departamento'} and operacion != 'read':
        ambito = obtener_ambito_gestor(current_user['user_id'], rol)
        if not _areas_de_actividad(actividad_target).issubset(ambito['areas']):
            raise HTTPException(status_code=403, detail='Actividad compartida: para modificar sus datos comunes se necesita acceso a todas sus áreas.')
    
    # RESPONSABLE_DEPARTAMENTO
    if rol == "responsable_departamento":
        ambito = obtener_ambito_gestor(current_user["user_id"], rol)
        if not _areas_de_actividad(actividad_target).intersection(ambito["areas"]):
            raise HTTPException(status_code=403, detail="Solo puedes gestionar actividades de tu departamento")
        
        if operacion in ["create", "update", "delete"]:
            return True
        
        raise HTTPException(status_code=403, detail="Operación no permitida")
    
    # RESPONSABLE_AREA
    if rol == "responsable_area":
        ambito = obtener_ambito_gestor(current_user["user_id"], rol)
        if not _areas_de_actividad(actividad_target).intersection(ambito["areas"]):
            raise HTTPException(status_code=403, detail="Solo puedes gestionar actividades de tu área")
        
        if operacion in ["create", "update", "delete"]:
            return True
        
        raise HTTPException(status_code=403, detail="Operación no permitida")
    
    # PROFESOR/PSI: solo lectura de su área
    if rol in ["profesor", "psi"]:
        usuario_autenticado = ProfesorRepository().find_by_usuario_id(current_user["user_id"])
        if not usuario_autenticado:
            raise HTTPException(status_code=403, detail="No tienes perfil de profesor")
        areas_usuario = set(usuario_autenticado.get("area_ids") or ([usuario_autenticado["area_id"]] if usuario_autenticado.get("area_id") else []))
        if operacion != "read":
            raise HTTPException(status_code=403, detail="No tienes permisos para modificar actividades")
        
        if not _areas_de_actividad(actividad_target).intersection(areas_usuario):
            raise HTTPException(status_code=403, detail="Solo puedes ver actividades de tu área")
        
        return True
    
    raise HTTPException(status_code=403, detail="Acceso denegado")


def _filtrar_actividades_por_acceso(current_user: dict, actividades: List[dict]) -> List[dict]:
    """Filtra actividades según acceso del usuario."""
    rol = current_user["rol"]
    
    # ADMIN ve todas
    if rol == "admin":
        return actividades
    
    # RESPONSABLE_DEPARTAMENTO: actividades de áreas de su departamento
    if rol == "responsable_departamento":
        ambito = obtener_ambito_gestor(current_user["user_id"], rol)
        return [a for a in actividades if _areas_de_actividad(a).intersection(ambito["areas"])]
    if rol == "responsable_area":
        ambito = obtener_ambito_gestor(current_user["user_id"], rol)
        return [a for a in actividades if _areas_de_actividad(a).intersection(ambito["areas"])]
    
    # PROFESOR, PSI: solo su área docente.
    usuario_autenticado = ProfesorRepository().find_by_usuario_id(current_user["user_id"])
    if not usuario_autenticado:
        return []
    areas_usuario = set(usuario_autenticado.get("area_ids") or ([usuario_autenticado["area_id"]] if usuario_autenticado.get("area_id") else []))
    return [a for a in actividades if _areas_de_actividad(a).intersection(areas_usuario)]


def _filas_exportacion_adjudicaciones(
    actividades: List[dict], lineas: List[dict], profesor_id: Optional[int] = None,
) -> List[dict]:
    """Construye filas planas de exportación solo desde confirmaciones visibles."""
    por_actividad: dict[int, list[dict]] = {}
    for linea in lineas:
        if profesor_id is None or linea["profesor_id"] == profesor_id:
            por_actividad.setdefault(linea["actividad_id"], []).append(linea)

    areas = {area["id"]: area for area in AreaRepository().find_all()}
    departamentos = {departamento["id"]: departamento for departamento in DepartamentoRepository().find_all()}
    filas: List[dict] = []
    for actividad in actividades:
        area = areas.get(actividad.get("area_id"), {})
        departamento = departamentos.get(area.get("departamento_id"), {})
        horario = (
            "Sin horario fijo"
            if not actividad.get("requiere_horario", True)
            else " · ".join(part for part in [actividad.get("dias"), actividad.get("horario")] if part)
                or "Horario pendiente"
        )
        for linea in por_actividad.get(actividad["id"], []):
            filas.append({
                "departamento": departamento.get("nombre") or departamento.get("codigo") or "Sin departamento",
                "area": area.get("nombre") or actividad.get("area_nombre") or actividad.get("area_codigo") or "Sin área",
                "asignatura": actividad.get("nombre_asignatura") or actividad.get("codigo"),
                "codigo": actividad.get("codigo"),
                "grupo": actividad.get("grupo") or actividad.get("codigo_grupo"),
                "tipo": actividad.get("tipo"),
                "cuatrimestre": actividad.get("duracion"),
                "horario": horario,
                "profesor": f"{linea['apellidos']}, {linea['nombre']}",
                "horas_confirmadas": float(linea["horas_asignadas"]),
            })
    return sorted(filas, key=lambda fila: (fila["departamento"], fila["area"], fila["asignatura"], fila["grupo"], fila["profesor"]))


def _verificar_acceso_creacion_en_area(current_user: dict, area_id: int) -> None:
    """Valida que una alta de actividad queda dentro del ámbito del gestor."""
    rol = current_user["rol"]
    if rol in ["profesor", "psi"]:
        raise HTTPException(status_code=403, detail="No tienes permisos para crear actividades")

    from repositories import AreaRepository
    area = AreaRepository().find_by_id(area_id)
    if not area:
        raise HTTPException(status_code=404, detail=f"Área {area_id} no encontrada")
    if rol == "admin":
        return

    if rol == "responsable_departamento" and area["id"] not in obtener_ambito_gestor(current_user["user_id"], rol)["areas"]:
        raise HTTPException(status_code=403, detail="Solo puedes crear actividades en áreas de tu departamento")
    if rol == "responsable_area" and area_id not in obtener_ambito_gestor(current_user["user_id"], rol)["areas"]:
        raise HTTPException(status_code=403, detail="Solo puedes crear actividades en tu área")


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/", summary="Listar actividades")
def get_actividades(
    current_user: dict = Depends(get_current_user)  # ✅ Todos autenticados
):
    """
    Obtiene actividades según permisos del usuario.
    
    **Roles permitidos:**
    - ADMIN: Todas las actividades
    - RESPONSABLE_DEPARTAMENTO: Actividades de su departamento
    - RESPONSABLE_AREA: Actividades de su área
    - PROFESOR/PSI: Actividades de su área
    """
    service = ActividadService()
    actividades = service.get_all()
    
    # Filtrar según acceso
    return _filtrar_actividades_por_acceso(current_user, actividades)


@router.get("/exportar", summary="Exportar directorio de actividades")
def exportar_directorio_actividades(
    formato: Literal["xlsx", "pdf"] = "xlsx",
    current_user: dict = Depends(get_current_user),
):
    """Exporta el catálogo visible en Excel o PDF, nunca datos fuera del ámbito."""
    actividades = _filtrar_actividades_por_acceso(current_user, ActividadService().get_all())
    etiquetas_tipo = {"GD": "Teoría", "GT": "Prácticas", "GL": "Laboratorio", "GA": "Seminario"}
    filas_excel: list[list[object]] = []
    filas_pdf: list[list[object]] = []
    for actividad in actividades:
        areas = ", ".join(
            f"{area.get('codigo', '')} - {area.get('nombre', '')}".strip(" -")
            for area in actividad.get("areas", [])
        ) or actividad.get("area_codigo") or "Sin área"
        horario = (
            "Sin horario fijo"
            if not actividad.get("requiere_horario", True)
            else " · ".join(parte for parte in [actividad.get("dias"), actividad.get("horario")] if parte)
                or "Horario pendiente"
        )
        estado = "Asignada" if float(actividad.get("horas_pendientes", 0)) <= 0.01 else "Pendiente"
        comun = [
            actividad.get("nombre_asignatura") or actividad.get("codigo"), actividad.get("codigo"),
            actividad.get("grupo") or actividad.get("codigo_grupo"),
            etiquetas_tipo.get(actividad.get("tipo"), actividad.get("tipo")), areas,
            actividad.get("idioma") or "", f"{actividad.get('duracion') or ''} · {actividad.get('turno') or ''}".strip(" ·"),
            horario, float(actividad.get("horas_actividad", 0)), float(actividad.get("horas_area", 0)),
            float(actividad.get("horas_asignadas", 0)), float(actividad.get("horas_pendientes", 0)), estado,
        ]
        filas_excel.append(comun)
        filas_pdf.append([
            comun[0], comun[1], comun[2], comun[3], comun[4], comun[6], comun[7], comun[8], comun[10], comun[12],
        ])

    try:
        from services.exportacion_adjudicaciones import generar_excel_tabular, generar_pdf_tabular
        if formato == "xlsx":
            contenido = generar_excel_tabular(
                "Directorio de actividades docentes", "Actividades",
                ["Asignatura", "Código", "Grupo", "Tipo", "Área(s)", "Idioma", "Periodo y turno", "Horario", "Horas actividad", "Horas área", "Horas confirmadas", "Horas pendientes", "Estado"],
                filas_excel, [38, 16, 16, 16, 35, 14, 20, 38, 18, 15, 20, 18, 14],
                [("Actividades", len(filas_excel)), ("Horas de actividad", sum(float(fila[8]) for fila in filas_excel)), ("Horas pendientes", sum(float(fila[11]) for fila in filas_excel))],
                {8: '0.0 "h"', 9: '0.0 "h"', 10: '0.0 "h"', 11: '0.0 "h"'},
            )
        else:
            contenido = generar_pdf_tabular(
                "Directorio de actividades docentes",
                ["Asignatura", "Código", "Grupo", "Tipo", "Área(s)", "Periodo y turno", "Horario", "H. actividad", "H. confirmadas", "Estado"],
                filas_pdf, [3.8, 1.5, 1.4, 1.5, 3.0, 2.0, 3.5, 1.5, 1.7, 1.3],
                f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}. {len(filas_excel)} actividad(es) visibles.",
                {7, 8},
            )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="El módulo de exportación no está instalado todavía.") from exc

    fecha = datetime.now().strftime("%Y-%m-%d")
    extension = "xlsx" if formato == "xlsx" else "pdf"
    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if formato == "xlsx" else "application/pdf"
    return StreamingResponse(
        BytesIO(contenido), media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="directorio_actividades_{fecha}.{extension}"', "Cache-Control": "no-store"},
    )


@router.get("/adjudicaciones/exportar", summary="Exportar adjudicaciones confirmadas")
def exportar_adjudicaciones_confirmadas(
    formato: Literal["xlsx", "pdf"] = "xlsx",
    current_user: dict = Depends(get_current_user),
):
    """Descarga las adjudicaciones confirmadas del ámbito visible.

    Se exporta exactamente la misma visibilidad de la página de
    adjudicaciones. El personal docente obtiene exclusivamente sus propias
    líneas; responsables y administración, las del área o departamento al que
    tienen acceso. Los borradores nunca se incluyen.
    """
    actividades = _filtrar_actividades_por_acceso(current_user, ActividadService().get_all())
    lineas = RepartoRepository().find_adjudicaciones_por_actividades(
        [actividad["id"] for actividad in actividades],
    )
    profesor_id = None
    if current_user["rol"] in {"profesor", "psi"}:
        perfil = ProfesorRepository().find_by_usuario_id(current_user["user_id"])
        profesor_id = perfil["id"] if perfil else -1
    filas = _filas_exportacion_adjudicaciones(actividades, lineas, profesor_id)

    try:
        from services.exportacion_adjudicaciones import (
            generar_excel_adjudicaciones,
            generar_pdf_adjudicaciones,
        )
        contenido = generar_excel_adjudicaciones(filas) if formato == "xlsx" else generar_pdf_adjudicaciones(filas)
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="El módulo de exportación no está instalado todavía. Reconstruye el servicio backend.",
        ) from exc

    fecha = datetime.now().strftime("%Y-%m-%d")
    extension = "xlsx" if formato == "xlsx" else "pdf"
    media_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if formato == "xlsx" else "application/pdf"
    )
    return StreamingResponse(
        BytesIO(contenido),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="adjudicaciones_confirmadas_{fecha}.{extension}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/adjudicaciones", summary="Consultar adjudicaciones confirmadas")
def get_adjudicaciones_confirmadas(
    current_user: dict = Depends(get_current_user),
):
    """Relaciona cada actividad visible con sus docentes confirmados.

    La página se apoya únicamente en ``reparto_docente``: los borradores no
    se muestran como adjudicaciones. El profesorado ve solo sus propias líneas;
    los responsables y administración ven las del ámbito que ya pueden
    consultar en el catálogo de actividades.
    """
    actividades = _filtrar_actividades_por_acceso(
        current_user, ActividadService().get_all(),
    )
    actividad_ids = [actividad["id"] for actividad in actividades]
    lineas = RepartoRepository().find_adjudicaciones_por_actividades(actividad_ids)

    solo_propias = current_user["rol"] in {"profesor", "psi"}
    profesor_id = None
    if solo_propias:
        perfil = ProfesorRepository().find_by_usuario_id(current_user["user_id"])
        profesor_id = perfil["id"] if perfil else None
        lineas = [linea for linea in lineas if linea["profesor_id"] == profesor_id]

    docentes_por_actividad: dict[int, list[dict]] = {}
    for linea in lineas:
        docentes_por_actividad.setdefault(linea["actividad_id"], []).append(linea)

    return {
        "visibilidad": "PROPIA" if solo_propias else "AMBITO",
        "actividades": [
            {
                "id": actividad["id"],
                "codigo": actividad["codigo"],
                "nombre_asignatura": actividad.get("nombre_asignatura"),
                "tipo": actividad["tipo"],
                "codigo_grupo": actividad["codigo_grupo"],
                "grupo": actividad["grupo"],
                "area_id": actividad.get("area_id"),
                "area_codigo": actividad.get("area_codigo"),
                "area_nombre": actividad.get("area_nombre"),
                "horas_totales": float(actividad["horas_area"]),
                "horas_asignadas": float(actividad.get("horas_asignadas", 0)),
                "horas_pendientes": float(actividad.get("horas_pendientes", 0)),
                "docentes": docentes_por_actividad.get(actividad["id"], []),
            }
            for actividad in actividades
            if not solo_propias or actividad["id"] in docentes_por_actividad
        ],
    }


@router.get("/{actividad_id}", summary="Obtener actividad por ID")
def get_actividad(
    actividad_id: int,
    current_user: dict = Depends(get_current_user)  # ✅ Verificar acceso
):
    """
    Obtiene una actividad específica.
    
    **Roles permitidos:**
    - ADMIN: Cualquier actividad
    - RESPONSABLE_DEPARTAMENTO: Actividades de su departamento
    - RESPONSABLE_AREA: Actividades de su área
    - PROFESOR/PSI: Actividades de su área
    """
    _verificar_acceso_actividad(current_user, actividad_id, "read")
    
    service = ActividadService()
    try:
        return service.get_by_id(actividad_id)
    except ActividadNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/", status_code=status.HTTP_201_CREATED, summary="Crear actividad")
def create_actividad(
    body: CreateActividadRequest,
    current_user: dict = Depends(get_current_user)  # ✅ Verificar permisos
):
    """
    Crea una nueva actividad.
    
    **Roles permitidos:**
    - ADMIN: En cualquier área
    - RESPONSABLE_DEPARTAMENTO: En áreas de su departamento
    - RESPONSABLE_AREA: Solo en su área
    - PROFESOR/PSI: No permitido
    """
    for area_id in body.area_ids:
        _verificar_acceso_creacion_en_area(current_user, area_id)
    
    service = ActividadService()
    try:
        actividades = service.create_many(
            codigo=body.codigo,
            tipo=body.tipo,
            codigo_grupo=body.codigo_grupo,
            grupo=body.grupo,
            idioma=body.idioma,
            duracion=body.duracion,
            turno=body.turno,
            dias=body.dias,
            horario=body.horario,
            requiere_horario=body.requiere_horario,
            horas_asignatura=body.horas_asignatura,
            horas_actividad=body.horas_actividad,
            horas_area=body.horas_area,
            area_ids=body.area_ids,
            metadata=_metadata_academica(body, incluir_nulos=True),
            cuotas_por_area={cuota.area_id: cuota.horas for cuota in body.cuotas_por_area} or None,
        )
        return actividades[0] if len(actividades) == 1 else {"actividades": actividades}
    except DuplicateResourceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{actividad_id}", summary="Actualizar actividad")
def update_actividad(
    actividad_id: int,
    body: UpdateActividadRequest,
    current_user: dict = Depends(get_current_user)  # ✅ Verificar permisos
):
    """
    Actualiza una actividad existente.
    
    **Roles permitidos:**
    - ADMIN: Cualquier actividad
    - RESPONSABLE_DEPARTAMENTO: Actividades de su departamento
    - RESPONSABLE_AREA: Actividades de su área
    - PROFESOR/PSI: No permitido
    """
    _verificar_acceso_actividad(current_user, actividad_id, "update")
    if body.area_id is not None:
        _verificar_acceso_creacion_en_area(current_user, body.area_id)
    if body.area_ids is not None:
        for area_id in body.area_ids:
            _verificar_acceso_creacion_en_area(current_user, area_id)
    
    service = ActividadService()
    try:
        return service.update(
            actividad_id=actividad_id,
            codigo=body.codigo,
            tipo=body.tipo,
            codigo_grupo=body.codigo_grupo,
            grupo=body.grupo,
            idioma=body.idioma,
            duracion=body.duracion,
            turno=body.turno,
            requiere_horario=body.requiere_horario,
            dias=body.dias,
            horario=body.horario,
            horas_asignatura=body.horas_asignatura,
            horas_actividad=body.horas_actividad,
            horas_area=body.horas_area,
            area_id=body.area_id,
            area_ids=body.area_ids,
            **_metadata_academica(body),
        )
    except ActividadNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConstraintViolation as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{actividad_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar actividad")
def delete_actividad(
    actividad_id: int,
    current_user: dict = Depends(get_current_user)  # ✅ Verificar permisos
):
    """
    Elimina una actividad.
    
    **Roles permitidos:**
    - ADMIN: Cualquier actividad
    - RESPONSABLE_DEPARTAMENTO: Actividades de su departamento
    - RESPONSABLE_AREA: Actividades de su área
    - PROFESOR/PSI: No permitido
    """
    _verificar_acceso_actividad(current_user, actividad_id, "delete")
    
    service = ActividadService()
    try:
        service.delete(actividad_id)
    except ActividadNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConstraintViolation as e:
        raise HTTPException(status_code=400, detail=str(e))
