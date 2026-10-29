import { apiClient, apiFetch } from "./api-client";

// --- INTERFACES DE API ---
export interface ApiActividad {
  id: number;
  codigo: string;
  tipo: string; // 'GD', 'GT', 'GL', 'GA'
  codigo_grupo: string;
  grupo: string;
  idioma: string;
  duracion: string;
  turno: string; // 'Mañana', 'Tarde', 'Noche'
  dias?: string | null;
  horario?: string | null;
  requiere_horario?: boolean;
  horario_confirmado?: boolean;
  origen_horario?: string;
  horario_detallado?: Array<{ fecha?: string; dia: string; inicio: string; fin: string }>;
  fuente_horario?: string | null;
  horas_asignatura: number;
  horas_actividad: number;
  horas_area: number;
  horas_asignadas: number;
  horas_pendientes: number;
  area_id: number;
  area_ids?: number[];
  cuotas_por_area?: { area_id: number; horas: number }[];
  areas?: { id: number; codigo: string; nombre: string; departamento_id: number }[];
  area_codigo?: string | null;
  area_nombre?: string | null;
  tiene_asignaciones: boolean;
  nombre_asignatura?: string | null;
  curso_academico?: string | null;
  tipo_estudio?: string | null;
  codigo_plan?: string | null;
  nombre_plan?: string | null;
  codigo_centro?: string | null;
  nombre_centro?: string | null;
  ciclo?: string | null;
  curso?: string | null;
  caracter?: string | null;
  actividad_oficial_id?: string | null;
  nombre_actividad?: string | null;
  codigo_grupo_oficial?: string | null;
}

interface CreateActividadPayload {
  codigo: string;
  tipo: string;
  codigo_grupo: string;
  grupo: string;
  idioma: string;
  duracion: string;
  turno: string;
  dias?: string | null;
  horario?: string | null;
  requiere_horario?: boolean;
  horario_confirmado?: boolean;
  origen_horario?: string;
  horario_detallado?: Array<{ fecha?: string; dia: string; inicio: string; fin: string }>;
  fuente_horario?: string | null;
  horas_asignatura: number;
  horas_actividad: number;
  horas_area: number;
  area_id: number;
  area_ids?: number[];
  cuotas_por_area?: { area_id: number; horas: number }[];
  area_codigo?: string | null;
  area_nombre?: string | null;
  nombre_asignatura?: string | null;
  curso_academico?: string | null;
  tipo_estudio?: string | null;
  codigo_plan?: string | null;
  nombre_plan?: string | null;
  codigo_centro?: string | null;
  nombre_centro?: string | null;
  ciclo?: string | null;
  curso?: string | null;
  caracter?: string | null;
  actividad_oficial_id?: string | null;
  nombre_actividad?: string | null;
  codigo_grupo_oficial?: string | null;
}

interface UpdateActividadPayload extends Partial<CreateActividadPayload> {}

export interface DocenteAdjudicado {
  profesor_id: number;
  nombre: string;
  apellidos: string;
  categoria: string;
  horas_asignadas: number;
}

export interface ActividadAdjudicada {
  id: number;
  codigo: string;
  nombre_asignatura?: string | null;
  tipo: string;
  codigo_grupo: string;
  grupo: string;
  area_id?: number | null;
  area_codigo?: string | null;
  area_nombre?: string | null;
  horas_totales: number;
  horas_asignadas: number;
  horas_pendientes: number;
  docentes: DocenteAdjudicado[];
}

export interface AdjudicacionesResponse {
  visibilidad: "PROPIA" | "AMBITO";
  actividades: ActividadAdjudicada[];
}

export interface DevolucionAdjudicacionResultado {
  ok: boolean;
  revision_id: number;
  area_id: number;
  version: number;
  profesor: string;
  actividad: string;
  horas_devuelta: number;
  reabierta: boolean;
}

// --- ENDPOINTS PRINCIPALES ---

/**
 * Obtener todas las actividades (filtrado automático por backend según rol)
 * GET /api/v1/actividades
 */
export async function getActividades(): Promise<ApiActividad[]> {
  try {
    return await apiFetch<ApiActividad[]>("/actividades/");
  } catch (error) {
    console.error("❌ Error al obtener actividades:", error);
    throw error;
  }
}

/**
 * Obtener una actividad por ID
 * GET /api/v1/actividades/{id}
 */
export async function getActividad(id: number | string): Promise<ApiActividad> {
  try {
    return await apiFetch<ApiActividad>(`/actividades/${id}`);
  } catch (error) {
    console.error(`❌ Error al obtener actividad ${id}:`, error);
    throw error;
  }
}

/**
 * Crear una nueva actividad
 * POST /api/v1/actividades
 */
export async function createActividad(payload: CreateActividadPayload): Promise<ApiActividad> {
  try {
    return await apiFetch<ApiActividad>("/actividades/", {
      method: "POST",
      body: payload,
    });
  } catch (error) {
    console.error("❌ Error al crear actividad:", error);
    throw error;
  }
}

/**
 * Actualizar una actividad
 * PUT /api/v1/actividades/{id}
 */
export async function updateActividad(
  id: number | string,
  payload: UpdateActividadPayload
): Promise<ApiActividad> {
  try {
    return await apiFetch<ApiActividad>(`/actividades/${id}`, {
      method: "PUT",
      body: payload,
    });
  } catch (error) {
    console.error(`❌ Error al actualizar actividad ${id}:`, error);
    throw error;
  }
}

/**
 * Eliminar una actividad
 * DELETE /api/v1/actividades/{id}
 */
export async function deleteActividad(id: number | string): Promise<void> {
  try {
    await apiFetch<void>(`/actividades/${id}`, {
      method: "DELETE",
    });
  } catch (error) {
    console.error(`❌ Error al eliminar actividad ${id}:`, error);
    throw error;
  }
}

// --- HELPERS Y TRANSFORMACIONES ---

/**
 * Obtener actividades formateadas para tabla
 */
export async function getActividadesParaTabla(): Promise<any[]> {
  try {
    const actividades = await getActividades();

    return actividades.map((actividad) => {
      const horasAsignadas = actividad.horas_asignadas ?? 0;
      const horasPendientes = actividad.horas_pendientes ?? (actividad.horas_actividad - horasAsignadas);

      return {
        id: actividad.id.toString(),
        codigo: actividad.codigo,
        tipo: actividad.tipo,
        grupo: actividad.grupo,
        idioma: actividad.idioma,
        duracion: actividad.duracion,
        turno: actividad.turno,
        dias: actividad.dias,
        horario: actividad.horario,
        requiere_horario: actividad.requiere_horario,
        horario_confirmado: actividad.horario_confirmado,
        origen_horario: actividad.origen_horario,
        horario_detallado: actividad.horario_detallado,
        fuente_horario: actividad.fuente_horario,
        horas_asignatura: actividad.horas_asignatura,
        horas_actividad: actividad.horas_actividad,
        horas_area: actividad.horas_area,
        horas_asignadas: horasAsignadas,
        horas_pendientes: horasPendientes,
        area_id: actividad.area_id,
        area_ids: actividad.area_ids ?? [actividad.area_id],
        cuotas_por_area: actividad.cuotas_por_area,
        areas: actividad.areas ?? (actividad.area_codigo ? [{
          id: actividad.area_id,
          codigo: actividad.area_codigo,
          nombre: actividad.area_nombre ?? "",
          departamento_id: 0,
        }] : []),
        area_codigo: actividad.area_codigo,
        area_nombre: actividad.area_nombre,
        nombre_asignatura: actividad.nombre_asignatura,
        curso_academico: actividad.curso_academico,
        tipo_estudio: actividad.tipo_estudio,
        codigo_plan: actividad.codigo_plan,
        nombre_plan: actividad.nombre_plan,
        codigo_centro: actividad.codigo_centro,
        nombre_centro: actividad.nombre_centro,
        ciclo: actividad.ciclo,
        curso: actividad.curso,
        caracter: actividad.caracter,
        actividad_oficial_id: actividad.actividad_oficial_id,
        nombre_actividad: actividad.nombre_actividad,
        codigo_grupo_oficial: actividad.codigo_grupo_oficial,
        codigo_grupo: actividad.codigo_grupo,
        tiene_asignaciones: actividad.tiene_asignaciones,
        status: horasPendientes > 0 ? "pendiente" : "asignado",
      };
    });
  } catch (error) {
    console.error("❌ Error al obtener actividades para tabla:", error);
    throw error;
  }
}

/**
 * Obtener label de tipo de actividad
 */
export function getLabelTipoActividad(tipo: string): string {
  const labels: Record<string, string> = {
    // Valores actuales en BD (TipoActividad enum)
    GD: "Teoría",
    GT: "Prácticas",
    GL: "Laboratorio",
    GA: "Seminario",
    // Compatibilidad con valores legacy
    T: "Teoría",
    P: "Prácticas",
    L: "Laboratorio",
    S: "Seminario",
  };
  return labels[tipo] || tipo;
}

/**
 * Obtener label de turno
 */
export function getLabelTurno(turno: string): string {
  const labels: Record<string, string> = {
    // Valores actuales en BD (TurnoHorario enum)
    Mañana: "Mañana",
    Tarde: "Tarde",
    Noche: "Noche",
    // Compatibilidad con valores legacy
    M: "Mañana",
    T: "Tarde",
    N: "Noche",
  };
  return labels[turno] || turno;
}

/**
 * Obtener label de duración
 */
export function getLabelDuracion(duracion: string): string {
  const labels: Record<string, string> = {
    // Valores normalizados por el solver
    "1": "1er Cuatrimestre",
    "2": "2º Cuatrimestre",
    anual: "Anual",
    // Compatibilidad con valores legacy
    C: "Cuatrimestral",
    A: "Anual",
  };
  return labels[duracion] || duracion;
}

/**
 * Obtener color de badge según estado
 */
export function getColorEstado(status: string): string {
  const colors: Record<string, string> = {
    asignado: "bg-green-100 text-green-800",
    pendiente: "bg-yellow-100 text-yellow-800",
    parcial: "bg-blue-100 text-blue-800",
  };
  return colors[status] || "bg-gray-100 text-gray-800";
}

/** Actividades y docentes con adjudicaciones ya confirmadas, nunca borradores. */
export async function getAdjudicacionesConfirmadas(): Promise<AdjudicacionesResponse> {
  return apiFetch<AdjudicacionesResponse>("/actividades/adjudicaciones");
}

/** Devuelve una única línea confirmada al borrador de su profesor para revisión. */
export async function devolverAdjudicacion(
  actividadId: number,
  profesorId: number,
  areaId: number,
  motivo: string,
): Promise<DevolucionAdjudicacionResultado> {
  return apiFetch<DevolucionAdjudicacionResultado>(`/adjudicaciones/${actividadId}/devolver`, {
    method: "POST",
    body: { profesor_id: profesorId, area_id: areaId, motivo },
  });
}

/** Descarga el resultado confirmado del ámbito que puede consultar el usuario. */
export async function descargarAdjudicacionesConfirmadas(formato: "xlsx" | "pdf"): Promise<void> {
  const respuesta = await apiClient.get<Blob>("/actividades/adjudicaciones/exportar", {
    params: { formato },
    responseType: "blob",
  });
  if (typeof window === "undefined") return;
  const fecha = new Date().toISOString().slice(0, 10);
  const enlace = document.createElement("a");
  enlace.href = window.URL.createObjectURL(respuesta.data);
  enlace.download = `adjudicaciones_confirmadas_${fecha}.${formato}`;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  window.setTimeout(() => window.URL.revokeObjectURL(enlace.href), 0);
}

/** Descarga el catálogo de actividades que el usuario puede consultar. */
export async function descargarDirectorioActividades(formato: "xlsx" | "pdf"): Promise<void> {
  const respuesta = await apiClient.get<Blob>("/actividades/exportar", {
    params: { formato },
    responseType: "blob",
  });
  if (typeof window === "undefined") return;
  const enlace = document.createElement("a");
  enlace.href = window.URL.createObjectURL(respuesta.data);
  enlace.download = `directorio_actividades_${new Date().toISOString().slice(0, 10)}.${formato}`;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  window.setTimeout(() => window.URL.revokeObjectURL(enlace.href), 0);
}
