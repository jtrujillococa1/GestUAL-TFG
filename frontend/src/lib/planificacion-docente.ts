import { apiFetch } from "@/lib/api";

export type ProfesorPlanificacion = {
  id: number;
  nombre: string;
  apellidos: string;
  categoria: string;
  area_ids: number[];
  areas: Array<{ id: number; codigo: string; nombre: string }>;
};

export type SesionPlanificada = {
  id: number;
  actividad_id: number;
  reparto_id: number | null;
  fecha: string;
  hora_inicio: string;
  hora_fin: string;
  horas: number;
  horas_adjudicadas: number | null;
  horas_actividad: number;
  es_horario_referencia: boolean;
  orden_adjudicacion: number;
  orden_sesion: number;
  estado: "PLANIFICADA";
  origen: "AUTOMATICO" | "MANUAL";
  observacion: string | null;
  codigo: string;
  nombre_asignatura: string | null;
  tipo: string;
  codigo_grupo: string;
  grupo: string;
  area_id: number | null;
  area_codigo: string | null;
  area_nombre: string | null;
};

export type IncidenciaPlanificacion = {
  requiere_horario: boolean;
  id: number;
  actividad_id: number;
  reparto_id: number | null;
  horas: number;
  horas_adjudicadas: number | null;
  horas_actividad: number;
  es_horario_referencia: boolean;
  estado: "AJUSTE_PENDIENTE" | "PENDIENTE_HORARIO";
  observacion: string | null;
  codigo: string;
  nombre_asignatura: string | null;
  tipo: string;
  codigo_grupo: string;
  grupo: string;
};

export type CalendarioDocente = {
  profesor: Omit<ProfesorPlanificacion, "area_ids">;
  es_propio: boolean;
  curso_academico: string;
  cursos_disponibles: string[];
  semana_inicio: string;
  semana_fin: string;
  sesiones: SesionPlanificada[];
  incidencias: IncidenciaPlanificacion[];
  dias_no_lectivos: Array<{ fecha: string; tipo: string; nombre: string }>;
};

export function getProfesoresPlanificacion() {
  return apiFetch<ProfesorPlanificacion[]>("/planificacion-docente/profesores");
}

export function getCalendarioProfesor(
  profesorId: number,
  opciones: { cursoAcademico?: string; semana?: string } = {},
) {
  return apiFetch<CalendarioDocente>(`/planificacion-docente/profesores/${profesorId}`, {
    params: {
      curso_academico: opciones.cursoAcademico,
      semana: opciones.semana,
    },
  });
}

export function regenerarPlanificacion() {
  return apiFetch<{ actividades: number; sesiones: number }>("/planificacion-docente/regenerar", {
    method: "POST",
    body: {},
  });
}
