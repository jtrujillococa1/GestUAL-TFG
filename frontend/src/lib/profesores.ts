import { apiClient, apiFetch } from "./api-client";
import type { Professor } from "./types";
import { redondearHoras } from "./horas";

// --- INTERFACES DE API ---
export interface ApiProfesor {
  id: number;
  usuario_id: number | null;
  nombre: string;
  apellidos: string;
  categoria: string;
  fecha_ingreso: string;
  carga_docente: number;
  horas_confirmadas: number;
  area_id: number | null;
  area_ids: number[];
  horas_objetivo_por_area?: Record<number, number>;
  areas: { id: number; codigo: string; nombre: string; departamento_id: number }[];
  es_psi: boolean;
  disponibilidad_cuatrimestre: "PRIMERO" | "SEGUNDO" | "AMBOS";
  prioridades_asignaturas: { codigo: string; nombre: string; prioridad: number }[];
  departamento_id: number | null;
  tiene_asignaciones: boolean;
}

interface CreateProfesorPayload {
  nombre: string;
  apellidos: string;
  categoria: string;
  fecha_ingreso: string;
  carga_docente: number;
  area_id: number | null;
  area_ids: number[];
  horas_objetivo_por_area?: Record<number, number>;
  es_psi: boolean;
  disponibilidad_cuatrimestre: "PRIMERO" | "SEGUNDO" | "AMBOS";
  prioridades_asignaturas: string[];
}

interface UpdateProfesorPayload extends Partial<CreateProfesorPayload> {}

export interface CreateProfesorConCuentaPayload extends CreateProfesorPayload {
  email: string;
  password: string;
  rol: "profesor" | "psi";
}

interface ApiProfesorEstado {
  id: number;
  nombre: string;
  apellidos: string;
  carga_docente: number;
  horas_confirmadas: number;
  horas_restantes: number;
}

// --- ENDPOINTS PRINCIPALES ---

/**
 * Obtener todos los profesores (filtrado automático por backend según rol)
 * GET /api/v1/profesores
 */
export async function getProfesores(): Promise<ApiProfesor[]> {
  try {
    return await apiFetch<ApiProfesor[]>("/profesores/");
  } catch (error) {
    console.error("❌ Error al obtener profesores:", error);
    throw error;
  }
}

/**
 * Obtener un profesor por ID
 * GET /api/v1/profesores/{id}
 */
export async function getProfesor(id: number | string): Promise<ApiProfesor> {
  try {
    return await apiFetch<ApiProfesor>(`/profesores/${id}`);
  } catch (error) {
    console.error(`❌ Error al obtener profesor ${id}:`, error);
    throw error;
  }
}

/**
 * Crear un nuevo profesor
 * POST /api/v1/profesores
 */
export async function createProfesor(payload: CreateProfesorPayload): Promise<ApiProfesor> {
  try {
    return await apiFetch<ApiProfesor>("/profesores/", {
      method: "POST",
      body: payload,
    });
  } catch (error) {
    console.error("❌ Error al crear profesor:", error);
    throw error;
  }
}

/** Recupera exclusivamente el perfil docente de la sesión activa. */
export async function getMiProfesor(): Promise<ApiProfesor | null> {
  return apiFetch<ApiProfesor | null>("/profesores/mi");
}

/** Crea de forma atómica la cuenta de acceso y el perfil docente. */
export async function createProfesorConCuenta(
  payload: CreateProfesorConCuentaPayload,
): Promise<ApiProfesor> {
  return apiFetch<ApiProfesor>("/profesores/con-cuenta", {
    method: "POST",
    body: payload,
  });
}

/**
 * Actualizar un profesor
 * PUT /api/v1/profesores/{id}
 */
export async function updateProfesor(
  id: number | string,
  payload: UpdateProfesorPayload
): Promise<ApiProfesor> {
  try {
    return await apiFetch<ApiProfesor>(`/profesores/${id}`, {
      method: "PUT",
      body: payload,
    });
  } catch (error) {
    console.error(`❌ Error al actualizar profesor ${id}:`, error);
    throw error;
  }
}

/**
 * Eliminar un profesor
 * DELETE /api/v1/profesores/{id}
 */
export async function deleteProfesor(id: number | string): Promise<void> {
  try {
    await apiFetch<void>(`/profesores/${id}`, {
      method: "DELETE",
    });
  } catch (error) {
    console.error(`❌ Error al eliminar profesor ${id}:`, error);
    throw error;
  }
}

// --- HELPERS Y TRANSFORMACIONES ---

/**
 * Obtener profesores formateados para tabla
 * Combina datos de profesores con estado de ordenación
 */
export async function getProfesoresParaTabla(): Promise<any[]> {
  try {
    // El directorio incluye las cargas de todos los perfiles visibles.
    // /estado está limitado al propio docente y no sirve para sus compañeros.
    const profesores = await getProfesores();

    // Transformar a formato de tabla
    return profesores.map((profesor) => {
      const cargaObjetivo = redondearHoras(profesor.carga_docente);
      const cargaAsignada = redondearHoras(profesor.horas_confirmadas ?? 0);
      const cargaRestante = redondearHoras(cargaObjetivo - cargaAsignada);

      return {
        id: profesor.id.toString(),
        usuario_id: profesor.usuario_id,
        name: `${profesor.nombre} ${profesor.apellidos}`,
        firstName: profesor.nombre,
        lastName: profesor.apellidos,
        categoria: profesor.categoria,
        fecha_ingreso: profesor.fecha_ingreso,
        carga_docente: cargaObjetivo,
        carga_asignada: cargaAsignada,
        carga_restante: cargaRestante,
        area_id: profesor.area_id,
        area_ids: profesor.area_ids ?? (profesor.area_id ? [profesor.area_id] : []),
        horas_objetivo_por_area: profesor.horas_objetivo_por_area ?? {},
        areas: profesor.areas ?? [],
        es_psi: profesor.es_psi,
        disponibilidad_cuatrimestre: profesor.disponibilidad_cuatrimestre ?? "AMBOS",
        status: calcularEstado(cargaRestante),
        tiene_asignaciones: profesor.tiene_asignaciones,
      };
    });
  } catch (error) {
    console.error("❌ Error al obtener profesores para tabla:", error);
    throw error;
  }
}

/**
 * Formatear fecha en formato español
 */
export function formatearFecha(dateString: string): string {
  if (!dateString) return "-";

  const date = new Date(dateString);
  return new Intl.DateTimeFormat("es-ES", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

/**
 * Calcular estado del profesor según horas restantes
 */
function calcularEstado(horasRestantes: number): "completo" | "incompleto" | "excedido" {
  if (Math.abs(horasRestantes) < 0.01) return "completo";
  if (horasRestantes < 0) return "excedido";
  return "incompleto";
}

/**
 * Obtener label de categoría docente
 */
export function getLabelCategoria(categoria: string): string {
  const labels: Record<string, string> = {
    CU: "Catedrático",
    TU: "Titular",
    CD: "Contratado Doctor",
    AY: "Ayudante",
    AS: "Asociado",
    PSI: "Personal de Sustitución",
  };
  return labels[categoria] || categoria;
}

export function getLabelDisponibilidadCuatrimestre(
  disponibilidad: "PRIMERO" | "SEGUNDO" | "AMBOS" | string | undefined,
): string {
  return {
    PRIMERO: "Solo 1.º cuatrimestre",
    SEGUNDO: "Solo 2.º cuatrimestre",
    AMBOS: "Ambos cuatrimestres",
  }[disponibilidad ?? "AMBOS"] ?? "Ambos cuatrimestres";
}

/** Actualiza exclusivamente la disponibilidad de la persona conectada. */
export async function updateMiDisponibilidadCuatrimestre(
  disponibilidad_cuatrimestre: "PRIMERO" | "SEGUNDO" | "AMBOS",
): Promise<ApiProfesor> {
  return apiFetch<ApiProfesor>("/profesores/mi/disponibilidad", {
    method: "PUT",
    body: { disponibilidad_cuatrimestre },
  });
}

/** Guarda el orden personal de asignaturas preferidas del docente conectado. */
export async function updateMiPrioridadesAsignaturas(
  prioridades_asignaturas: string[],
): Promise<ApiProfesor> {
  return apiFetch<ApiProfesor>("/profesores/mi/prioridades-asignaturas", {
    method: "PUT",
    body: { prioridades_asignaturas },
  });
}

/** Descarga el directorio de profesorado visible para la sesión actual. */
export async function descargarDirectorioProfesores(formato: "xlsx" | "pdf"): Promise<void> {
  const respuesta = await apiClient.get<Blob>("/profesores/exportar", {
    params: { formato },
    responseType: "blob",
  });
  if (typeof window === "undefined") return;
  const enlace = document.createElement("a");
  enlace.href = window.URL.createObjectURL(respuesta.data);
  enlace.download = `directorio_profesores_${new Date().toISOString().slice(0, 10)}.${formato}`;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  window.setTimeout(() => window.URL.revokeObjectURL(enlace.href), 0);
}
