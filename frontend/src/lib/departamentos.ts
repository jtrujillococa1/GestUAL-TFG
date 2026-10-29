import { apiFetch } from "./api-client";

// --- INTERFACES DE API ---
interface ApiDepartamento {
  id: number;
  codigo: string;
  nombre: string;
  responsable_departamento_id?: number | null;
}

interface CreateDepartamentoPayload {
  codigo: string;
  nombre: string;
  responsable_departamento_id?: number | null;
}

interface UpdateDepartamentoPayload extends Partial<CreateDepartamentoPayload> {}

// --- ENDPOINTS PRINCIPALES ---

/**
 * Obtener todos los departamentos (filtrado automático por backend según rol)
 * GET /api/v1/departamentos
 */
export async function getDepartamentos(): Promise<ApiDepartamento[]> {
  try {
    return await apiFetch<ApiDepartamento[]>("/departamentos/");
  } catch (error) {
    console.error("❌ Error al obtener departamentos:", error);
    throw error;
  }
}

/**
 * Obtener un departamento por ID
 * GET /api/v1/departamentos/{id}
 */
export async function getDepartamento(id: number | string): Promise<ApiDepartamento> {
  try {
    return await apiFetch<ApiDepartamento>(`/departamentos/${id}`);
  } catch (error) {
    console.error(`❌ Error al obtener departamento ${id}:`, error);
    throw error;
  }
}

/**
 * Crear un nuevo departamento (solo admin)
 * POST /api/v1/departamentos
 */
export async function createDepartamento(payload: CreateDepartamentoPayload): Promise<ApiDepartamento> {
  try {
    return await apiFetch<ApiDepartamento>("/departamentos/", {
      method: "POST",
      body: payload,
    });
  } catch (error) {
    console.error("❌ Error al crear departamento:", error);
    throw error;
  }
}

/**
 * Actualizar un departamento (solo admin)
 * PUT /api/v1/departamentos/{id}
 */
export async function updateDepartamento(
  id: number | string,
  payload: UpdateDepartamentoPayload
): Promise<ApiDepartamento> {
  try {
    return await apiFetch<ApiDepartamento>(`/departamentos/${id}`, {
      method: "PUT",
      body: payload,
    });
  } catch (error) {
    console.error(`❌ Error al actualizar departamento ${id}:`, error);
    throw error;
  }
}

/**
 * Eliminar un departamento (solo admin)
 * DELETE /api/v1/departamentos/{id}
 */
export async function deleteDepartamento(id: number | string): Promise<void> {
  try {
    await apiFetch<void>(`/departamentos/${id}`, {
      method: "DELETE",
    });
  } catch (error) {
    console.error(`❌ Error al eliminar departamento ${id}:`, error);
    throw error;
  }
}

// --- HELPERS Y TRANSFORMACIONES ---

/**
 * Obtener departamentos formateados para select/dropdown
 */
export async function getDepartamentosParaSelect(): Promise<Array<{ value: string; label: string }>> {
  try {
    const departamentos = await getDepartamentos();
    return departamentos.map((dept) => ({
      value: dept.id.toString(),
      label: `${dept.codigo} - ${dept.nombre}`,
    }));
  } catch (error) {
    console.error("❌ Error al obtener departamentos para select:", error);
    return [];
  }
}

/** Asigna el usuario responsable de un departamento. */
export async function asignarResponsableDepartamento(
  id: number | string,
  responsableId: number | null,
): Promise<ApiDepartamento> {
  return apiFetch<ApiDepartamento>(`/departamentos/${id}/responsable`, {
    method: "POST",
    body: { responsable_id: responsableId },
  });
}
