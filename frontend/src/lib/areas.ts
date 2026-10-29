import { apiFetch } from "./api-client";

// --- INTERFACES DE API ---
interface ApiArea {
  id: number;
  codigo: string;
  nombre: string;
  departamento_id: number;
  responsable_area_id?: number | null;
}

interface CreateAreaPayload {
  codigo: string;
  nombre: string;
  departamento_id: number;
  responsable_area_id?: number | null;
}

interface UpdateAreaPayload extends Partial<CreateAreaPayload> {}

// --- ENDPOINTS PRINCIPALES ---

/**
 * Obtener todas las áreas (filtrado automático por backend según rol)
 * GET /api/v1/areas
 */
export async function getAreas(): Promise<ApiArea[]> {
  try {
    return await apiFetch<ApiArea[]>("/areas/");
  } catch (error) {
    console.error("❌ Error al obtener áreas:", error);
    throw error;
  }
}

/**
 * Obtener un área por ID
 * GET /api/v1/areas/{id}
 */
export async function getArea(id: number | string): Promise<ApiArea> {
  try {
    return await apiFetch<ApiArea>(`/areas/${id}`);
  } catch (error) {
    console.error(`❌ Error al obtener área ${id}:`, error);
    throw error;
  }
}

/**
 * Crear una nueva área
 * POST /api/v1/areas
 */
export async function createArea(payload: CreateAreaPayload): Promise<ApiArea> {
  try {
    return await apiFetch<ApiArea>("/areas/", {
      method: "POST",
      body: payload,
    });
  } catch (error) {
    console.error("❌ Error al crear área:", error);
    throw error;
  }
}

/**
 * Actualizar un área
 * PUT /api/v1/areas/{id}
 */
export async function updateArea(
  id: number | string,
  payload: UpdateAreaPayload
): Promise<ApiArea> {
  try {
    return await apiFetch<ApiArea>(`/areas/${id}`, {
      method: "PUT",
      body: payload,
    });
  } catch (error) {
    console.error(`❌ Error al actualizar área ${id}:`, error);
    throw error;
  }
}

/**
 * Eliminar un área
 * DELETE /api/v1/areas/{id}
 */
export async function deleteArea(id: number | string): Promise<void> {
  try {
    await apiFetch<void>(`/areas/${id}`, {
      method: "DELETE",
    });
  } catch (error) {
    console.error(`❌ Error al eliminar área ${id}:`, error);
    throw error;
  }
}

// --- HELPERS Y TRANSFORMACIONES ---

/**
 * Obtener áreas formateadas para select/dropdown
 */
export async function getAreasParaSelect(): Promise<Array<{ value: string; label: string }>> {
  try {
    const areas = await getAreas();
    return areas.map((area) => ({
      value: area.id.toString(),
      label: `${area.codigo} - ${area.nombre}`,
    }));
  } catch (error) {
    console.error("❌ Error al obtener áreas para select:", error);
    return [];
  }
}

/**
 * Obtener áreas de un departamento específico
 */
export async function getAreasPorDepartamento(departamentoId: number | string): Promise<ApiArea[]> {
  try {
    const todasLasAreas = await getAreas();
    const deptId = typeof departamentoId === 'string' ? parseInt(departamentoId) : departamentoId;
    return todasLasAreas.filter((area) => area.departamento_id === deptId);
  } catch (error) {
    console.error(`❌ Error al obtener áreas del departamento ${departamentoId}:`, error);
    return [];
  }
}

/** Asigna el usuario responsable de un área. */
export async function asignarResponsableArea(
  id: number | string,
  responsableId: number | null,
): Promise<ApiArea> {
  return apiFetch<ApiArea>(`/areas/${id}/responsable`, {
    method: "POST",
    body: { responsable_id: responsableId },
  });
}
