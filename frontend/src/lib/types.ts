export type Role = 'Admin' | 'Responsable de departamento' | 'Responsable de área' | 'Profesor' | 'PSI';

export interface User {
  id: string;
  nombre: string;
  apellidos: string;
  email: string;
  rol: Role;
  activo: boolean;
  avatar?: string;
}

export type CategoriaDocente =
  | 'Catedrático'
  | 'Titular'
  | 'Contratado'
  | 'Ayudante'
  | 'Asociado'
  | 'Postdoc'
  | 'Doctorando'
  | 'PSI';

export interface Departamento {
  id: number; // ✅ Cambiado de string a number
  codigo: string;
  nombre: string;
  responsable_departamento_id?: number | null; // ✅ Cambiado de string a number
}

export interface Area {
  id: number; // ✅ Cambiado de string a number
  codigo: string;
  nombre: string;
  departamento_id: number; // ✅ Cambiado de string a number
  responsable_area_id?: number | null; // ✅ Cambiado de string a number
}

export interface Professor {
  id: number; // ✅ Cambiado de string a number
  usuario_id: number; // ✅ Cambiado de string a number
  nombre: string;
  apellidos: string;
  categoria: CategoriaDocente;
  fecha_ingreso: string;
  carga_docente: number;
  /** Área principal conservada por compatibilidad. */
  area_id: number | null;
  /** Un profesor puede participar en varias áreas. */
  area_ids: number[];
  areas?: Pick<Area, 'id' | 'codigo' | 'nombre' | 'departamento_id'>[];
  es_psi: boolean;
  /** Cuatrimestres en los que puede asumir docencia. */
  disponibilidad_cuatrimestre: 'PRIMERO' | 'SEGUNDO' | 'AMBOS';
  /** Lista ordenada: 1 es la asignatura preferida. */
  prioridades_asignaturas?: { codigo: string; nombre: string; prioridad: number }[];
  creado_en?: string;
}

export type TipoActividad = 'GD' | 'GT' | 'GL' | 'GA' | 'T' | 'P' | 'L' | 'S';
export type TipoAsignatura = 'Básica' | 'Obligatoria' | 'Optativa' | 'TFG' | 'TFM' | 'Máster';
export type TurnoHorario = 'Mañana' | 'Tarde' | 'Noche';

export interface Activity {
  id: number; // ✅ Cambiado de string a number
  codigo: string;
  tipo: string; // ✅ string flexible para 'T', 'P', 'L', etc.
  codigo_grupo: string;
  grupo: string;
  idioma: string;
  duracion: string; // ✅ Cambiado a string para 'C' (cuatrimestral) o 'A' (anual)
  turno: string; // ✅ Cambiado a string para 'M', 'T', 'N'
  horas_asignatura: number;
  horas_actividad: number;
  horas_area: number;
  /** Área que recibe la cuota de horas de esta fila. */
  area_id: number;
  /** Áreas académicas a las que está vinculada la actividad. */
  area_ids?: number[];
  areas?: Pick<Area, 'id' | 'codigo' | 'nombre' | 'departamento_id'>[];
  profesor_id?: number | null;
  dias?: string;
  horario?: string;
}

export interface RepartoDocente {
  id: number; // ✅ Cambiado de string a number
  profesor_id: number; // ✅ Cambiado de string a number
  actividad_id: number; // ✅ Cambiado de string a number
  horas_asignadas: number;
  asignado_por_usuario_id: number; // ✅ Cambiado de string a number
  confirmado: boolean;
  creado_en: string;
}

// ViewModels y Auxiliares
export interface DashboardViewModel {
  rol: Role;
  stats: {
    label: string;
    value: string | number;
    sub?: string;
    icon: any;
    color: string;
    bg: string;
  }[];
  progresoAsignacion: number;
  horasTotales: number;
  horasAsignadas: number;
  conflictProbability: number;
  alertas: {
    id: string;
    type: "conflict" | "warning" | "info";
    title: string;
    severity: "HIGH" | "MEDIUM" | "LOW";
  }[];
  profesorActual?: string | null;
  ordenacionTerminada: boolean;
}

export interface ApiEstadoOrdenacion {
  profesor_actual: string | null;
  ordenacion_terminada: boolean;
  profesores_completados: any[];
  profesores_pendientes: any[];
}

// Tipos adicionales para el backend
export interface ApiTeacher {
  id: number;
  usuario_id: number;
  nombre: string;
  apellidos: string;
  email?: string;
  categoria: string;
  fecha_ingreso: string;
  horas_maximas: number;
}

export interface ApiGroup {
  id: number;
  asignatura: string;
  grupo: string;
  tipo_actividad: string;
  tipo_asignatura: string;
  curso: number;
  cuatrimestre: number;
  turno: string;
  dias?: string | null;
  horario?: string | null;
  horas_totales: number;
  horas_asignadas: number;
  horas_pendientes: number;
}

export interface ApiProfesorEstado {
  id: number;
  nombre: string;
  apellidos: string;
  horas_maximas: number;
  horas_confirmadas: number;
  horas_restantes: number;
}

export interface ApiRepartoLinea {
  profesor_id: number;
  nombre: string;
  apellidos: string;
  categoria: string;
  grupo_id: number;
  asignatura: string;
  grupo: string;
  tipo_actividad: string;
  tipo_asignatura: string;
  curso: number;
  cuatrimestre: number;
  turno: string;
  dias?: string | null;
  horario?: string | null;
  horas_asignadas: number;
}
