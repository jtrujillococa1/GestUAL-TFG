"""
Schemas Pydantic para validación de datos.
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Any, Dict, Optional, List
from datetime import date, datetime
from enum import Enum


class RolUsuario(str, Enum):
    ADMIN = "admin"
    RESPONSABLE_DEPARTAMENTO = "responsable_departamento"
    RESPONSABLE_AREA = "responsable_area"
    PROFESOR = "profesor"
    PSI = "psi"


class TipoActividad(str, Enum):
    GD = "GD"
    GT = "GT"
    GL = "GL"
    GA = "GA"


class TurnoHorario(str, Enum):
    MANANA = "Mañana"
    TARDE = "Tarde"
    NOCHE = "Noche"
    MANANA_TARDE = "Mañana/Tarde"
    TARDE_SEMIPRESENCIAL_VIRTUAL = "Tarde semipresencial y virtual"


class DisponibilidadCuatrimestre(str, Enum):
    PRIMERO = "PRIMERO"
    SEGUNDO = "SEGUNDO"
    AMBOS = "AMBOS"


class UsuarioSchema(BaseModel):
    id: int
    nombre: str
    apellidos: str
    email: EmailStr
    rol: RolUsuario
    activo: bool = True


class CrearUsuarioSchema(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    apellidos: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password_hash: Optional[str] = None
    rol: RolUsuario
    activo: bool = True


class EditarUsuarioSchema(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=100)
    apellidos: Optional[str] = Field(default=None, min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    password_hash: Optional[str] = None
    rol: Optional[RolUsuario] = None
    activo: Optional[bool] = None


class DepartamentoSchema(BaseModel):
    id: int
    codigo: str
    nombre: str
    responsable_departamento_id: Optional[int] = None


class AreaSchema(BaseModel):
    id: int
    codigo: str
    nombre: str
    departamento_id: int
    responsable_area_id: Optional[int] = None


class ProfesorSchema(BaseModel):
    id: int
    usuario_id: Optional[int] = None
    nombre: str
    apellidos: str
    categoria: str
    fecha_ingreso: date
    carga_docente: float
    area_id: Optional[int] = None
    area_ids: List[int] = Field(default_factory=list)
    areas: List[dict] = Field(default_factory=list)
    horas_objetivo_por_area: dict[int, float] = Field(default_factory=dict)
    departamento_id: Optional[int] = None
    es_psi: bool = False
    disponibilidad_cuatrimestre: DisponibilidadCuatrimestre = DisponibilidadCuatrimestre.AMBOS
    identificador_origen: Optional[str] = None
    activo_origen: Optional[bool] = None
    tiene_asignaciones: bool = False
    
    class Config:
        from_attributes = True


class CrearProfesorSchema(BaseModel):
    usuario_id: Optional[int] = None
    nombre: str = Field(min_length=1, max_length=100)
    apellidos: str = Field(min_length=1, max_length=200)
    categoria: str
    fecha_ingreso: date
    carga_docente: float = Field(gt=0)
    area_id: Optional[int] = None
    es_psi: bool = False
    disponibilidad_cuatrimestre: DisponibilidadCuatrimestre = DisponibilidadCuatrimestre.AMBOS


class EditarProfesorSchema(BaseModel):
    usuario_id: Optional[int] = None
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=100)
    apellidos: Optional[str] = Field(default=None, min_length=1, max_length=200)
    categoria: Optional[str] = None
    fecha_ingreso: Optional[date] = None
    carga_docente: Optional[float] = Field(default=None, gt=0)
    area_id: Optional[int] = None
    area_ids: Optional[List[int]] = None
    es_psi: Optional[bool] = None
    disponibilidad_cuatrimestre: Optional[DisponibilidadCuatrimestre] = None


class PesoCategoriaSchema(BaseModel):
    categoria: str
    peso: int = Field(ge=1)


class ActividadSchema(BaseModel):
    id: int
    codigo: str
    tipo: TipoActividad
    codigo_grupo: str
    grupo: str
    idioma: Optional[str] = None
    duracion: str
    turno: TurnoHorario
    dias: Optional[str] = None
    horario: Optional[str] = None
    requiere_horario: bool = True
    horario_confirmado: bool = False
    origen_horario: str = "PENDIENTE"
    horas_asignatura: float
    horas_actividad: float
    horas_area: float
    area_id: Optional[int] = None
    area_ids: List[int] = Field(default_factory=list)
    areas: List[dict] = Field(default_factory=list)
    horas_asignadas: float = 0
    horas_pendientes: float = 0
    tiene_asignaciones: bool = False
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


class CrearActividadSchema(BaseModel):
    codigo: str = Field(min_length=1, max_length=50)
    tipo: TipoActividad
    codigo_grupo: str = Field(min_length=1, max_length=50)
    grupo: str = Field(min_length=1, max_length=100)
    idioma: Optional[str] = Field(default=None, max_length=50)
    duracion: str = Field(min_length=1, max_length=50)
    turno: TurnoHorario
    dias: Optional[str] = Field(default=None, max_length=100)
    horario: Optional[str] = Field(default=None, max_length=500)
    requiere_horario: bool = True
    horario_confirmado: bool = False
    origen_horario: str = Field(default="PENDIENTE", max_length=30)
    horas_asignatura: float = Field(ge=0)
    horas_actividad: float = Field(gt=0)
    horas_area: float = Field(ge=0)
    area_id: Optional[int] = None
    area_ids: List[int] = Field(default_factory=list)
    nombre_asignatura: Optional[str] = Field(default=None, max_length=255)
    tipo_estudio: Optional[str] = Field(default=None, max_length=20)
    codigo_plan: Optional[str] = Field(default=None, max_length=50)
    nombre_plan: Optional[str] = Field(default=None, max_length=255)
    codigo_centro: Optional[str] = Field(default=None, max_length=50)
    nombre_centro: Optional[str] = Field(default=None, max_length=255)
    ciclo: Optional[str] = Field(default=None, max_length=50)
    curso: Optional[str] = Field(default=None, max_length=50)
    caracter: Optional[str] = Field(default=None, max_length=100)
    actividad_oficial_id: Optional[str] = Field(default=None, max_length=50)
    nombre_actividad: Optional[str] = Field(default=None, max_length=255)
    codigo_grupo_oficial: Optional[str] = Field(default=None, max_length=50)
    curso_academico: Optional[str] = Field(default=None, max_length=20)


class EditarActividadSchema(BaseModel):
    codigo: Optional[str] = Field(default=None, min_length=1, max_length=50)
    tipo: Optional[TipoActividad] = None
    codigo_grupo: Optional[str] = Field(default=None, min_length=1, max_length=50)
    grupo: Optional[str] = Field(default=None, min_length=1, max_length=100)
    idioma: Optional[str] = Field(default=None, max_length=50)
    duracion: Optional[str] = Field(default=None, min_length=1, max_length=50)
    turno: Optional[TurnoHorario] = None
    dias: Optional[str] = Field(default=None, max_length=100)
    horario: Optional[str] = Field(default=None, max_length=500)
    requiere_horario: Optional[bool] = None
    horario_confirmado: Optional[bool] = None
    origen_horario: Optional[str] = Field(default=None, max_length=30)
    horas_asignatura: Optional[float] = Field(default=None, ge=0)
    horas_actividad: Optional[float] = Field(default=None, gt=0)
    horas_area: Optional[float] = Field(default=None, ge=0)
    area_id: Optional[int] = None
    area_ids: Optional[List[int]] = None
    nombre_asignatura: Optional[str] = Field(default=None, max_length=255)
    tipo_estudio: Optional[str] = Field(default=None, max_length=20)
    codigo_plan: Optional[str] = Field(default=None, max_length=50)
    nombre_plan: Optional[str] = Field(default=None, max_length=255)
    codigo_centro: Optional[str] = Field(default=None, max_length=50)
    nombre_centro: Optional[str] = Field(default=None, max_length=255)
    ciclo: Optional[str] = Field(default=None, max_length=50)
    curso: Optional[str] = Field(default=None, max_length=50)
    caracter: Optional[str] = Field(default=None, max_length=100)
    actividad_oficial_id: Optional[str] = Field(default=None, max_length=50)
    nombre_actividad: Optional[str] = Field(default=None, max_length=255)
    codigo_grupo_oficial: Optional[str] = Field(default=None, max_length=50)
    curso_academico: Optional[str] = Field(default=None, max_length=20)


class EleccionSchema(BaseModel):
    actividad_id: Optional[int] = None
    profesor: str
    codigo: str
    nombre_asignatura: Optional[str] = None
    tipo: TipoActividad
    codigo_grupo: str
    grupo: str
    # Las selecciones confirmables siempre exigen horas positivas en el
    # servicio. Se permite el cero solo en la respuesta de opciones para
    # representar de forma honesta una actividad cuya cuota ya está cubierta.
    horas: float = Field(ge=0)
    turno: Optional[TurnoHorario] = None
    duracion: Optional[str] = None
    idioma: Optional[str] = None
    dias: Optional[str] = None
    horario: Optional[str] = None
    requiere_horario: Optional[bool] = None
    horario_confirmado: Optional[bool] = None
    origen_horario: Optional[str] = None


class ProfesorEstadoSchema(BaseModel):
    id: int
    nombre: str
    apellidos: str
    categoria: str
    carga_docente: float
    horas_confirmadas: float
    horas_restantes: float
    area_id: Optional[int] = None
    area_ids: List[int] = Field(default_factory=list)
    es_psi: bool = False


class EstadoOrdenacionSchema(BaseModel):
    en_preparacion: bool = False
    profesor_actual: Optional[str]
    ordenacion_terminada: bool
    profesores_completados: List[ProfesorEstadoSchema]
    profesores_pendientes: List[ProfesorEstadoSchema]
    incidencia: Optional[str] = None
    version: int = 0
    cerrada: bool = False
    cerrado_en: Optional[datetime] = None


class OpcionSchema(BaseModel):
    opcion: EleccionSchema
    horas_restantes: float = Field(ge=0)
    horas_maximas_actividad: float = Field(ge=0)
    categoria: str
    total_repartos: int
    actividades_divididas: int = 0
    riesgo: Optional[int] = 0
    riesgo_nivel: str = "BAJO"
    riesgo_impacto: Optional[int] = 0
    riesgo_motivos: List[str] = Field(default_factory=list)
    riesgo_desglose: dict[str, int] = Field(default_factory=dict)
    viable: bool = True
    motivo_no_viable: Optional[str] = None
    bloqueada_por_solape: bool = False
    cached: bool = False
    prioridad_asignatura: Optional[int] = None


class BorradorSchema(BaseModel):
    profesor: str
    seleccion: List[EleccionSchema]
    horas_confirmadas: float = 0
    horas_seleccionadas: float
    carga_docente: float
    horas_restantes: float
    turno_completo: bool
    version: int = 0
    cerrada: bool = False
    # Se informa únicamente cuando este borrador contiene líneas devueltas.
    # Permite a la interfaz explicar que ya están preseleccionadas y ofrecer
    # su sustitución sin reiniciar el área.
    revisiones_pendientes: List[Dict[str, Any]] = Field(default_factory=list)


class ConfirmacionResultadoSchema(BaseModel):
    ok: bool
    profesor_confirmado: Optional[str] = None
    siguiente_profesor: Optional[str] = None
    ordenacion_terminada: bool = False
    error: Optional[str] = None
    version: int = 0


class ControlOrdenacionSchema(BaseModel):
    area_id: int
    version: int
    cerrada: bool
    cerrado_en: Optional[datetime] = None
    advertencias: List[str] = Field(default_factory=list)


class EventoOrdenacionSchema(BaseModel):
    id: int
    area_id: int
    usuario_id: Optional[int] = None
    tipo: str
    detalle: dict = Field(default_factory=dict)
    creado_en: Optional[datetime] = None


class RepartoLineaSchema(BaseModel):
    profesor_id: int
    nombre: str
    apellidos: str
    categoria: str
    es_psi: bool = False
    area_id: Optional[int] = None

    actividad_id: int
    codigo: str
    tipo: TipoActividad
    codigo_grupo: str
    grupo: str
    idioma: Optional[str] = None
    duracion: str
    turno: TurnoHorario
    dias: Optional[str] = None
    horario: Optional[str] = None
    horas_asignatura: float
    horas_actividad: float
    horas_area: float

    horas_asignadas: float


class DashboardSchema(BaseModel):
    total_profesores: int
    total_psi: int
    total_actividades: int
    porcentaje_asignacion: float
    actividades_incompletas: int
    profesores_completados: int
    profesores_pendientes: int
    horas_totales_sistema: float
    horas_asignadas_sistema: float
    equilibrio_horas: bool
    ordenacion_terminada: bool
    profesor_actual: Optional[str] = None


class RiesgoSchema(BaseModel):
    riesgo: int
    nivel: str
    motivo: str


class CacheStatsSchema(BaseModel):
    size: int
    hits: int
    misses: int
    hit_rate: str
