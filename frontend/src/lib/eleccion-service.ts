import { apiFetch } from "./api-client";

function encodeName(nombre: string): string {
  return encodeURIComponent(nombre);
}

export const eleccionService = {
  async getProfesorActual(areaId?: number) {
    return apiFetch<any>('/profesor-actual', { params: areaId ? { area_id: areaId } : undefined });
  },

  async getTurnosActivos() {
    return apiFetch<any>('/turnos-activos');
  },

  async getOpciones(nombreProfesor: string, areaId: number, offset = 0, limit = 8, signal?: AbortSignal) {
    return apiFetch<any>(`/opciones/${encodeName(nombreProfesor)}`, {
      params: { area_id: areaId, offset, limit },
      signal,
    });
  },

  async getBorrador(nombreProfesor: string, areaId: number) {
    return apiFetch<any>(`/borrador/${encodeName(nombreProfesor)}`, { params: { area_id: areaId } });
  },

  async addToBorrador(
    nombreProfesor: string,
    actividadId: number | undefined,
    codigo: string,
    codigoGrupo: string,
    tipo: string,
    horas: number,
    areaId: number,
    versionOrdenacion?: number,
  ) {
    return apiFetch<any>(`/borrador/${encodeName(nombreProfesor)}/anadir`, {
      method: "POST",
      body: {
        actividad_id: actividadId,
        codigo,
        codigo_grupo: codigoGrupo,
        tipo,
        horas,
        area_id: areaId,
        version_ordenacion: versionOrdenacion,
      },
    });
  },

  async removeFromBorrador(
    nombreProfesor: string,
    actividadId: number | undefined,
    codigo: string,
    codigoGrupo: string,
    tipo: string,
    areaId: number,
    versionOrdenacion?: number,
  ) {
    return apiFetch<any>(`/borrador/${encodeName(nombreProfesor)}/eliminar`, {
      method: "POST",
      body: {
        actividad_id: actividadId,
        codigo,
        codigo_grupo: codigoGrupo,
        tipo,
        area_id: areaId,
        version_ordenacion: versionOrdenacion,
      },
    });
  },

  async clearBorrador(nombreProfesor: string, areaId: number, versionOrdenacion?: number) {
    return apiFetch<any>(`/borrador/${encodeName(nombreProfesor)}`, {
      method: "DELETE",
      params: { area_id: areaId, version_ordenacion: versionOrdenacion },
    });
  },

  async confirmarTurno(areaId: number, versionOrdenacion?: number) {
    return apiFetch<any>('/confirmar-turno', {
      method: "POST",
      params: { area_id: areaId, version_ordenacion: versionOrdenacion },
    });
  },

  async getEstado() {
    return apiFetch<any>('/estado');
  },

  async cerrarArea(areaId: number, versionOrdenacion?: number) {
    return apiFetch<any>(`/areas/${areaId}/cerrar`, {
      method: "POST",
      body: { version_ordenacion: versionOrdenacion },
    });
  },

  async reabrirArea(areaId: number, motivo: string, versionOrdenacion?: number) {
    return apiFetch<any>(`/areas/${areaId}/reabrir`, {
      method: "POST",
      body: { motivo, version_ordenacion: versionOrdenacion },
    });
  },

  async getEventosArea(areaId: number) {
    return apiFetch<any>(`/areas/${areaId}/eventos`);
  },
};

export async function resetOrdenacion(): Promise<{ ok: boolean; mensaje: string }> {
  return apiFetch('/reset-ordenacion', { method: "POST" });
}

export type AlcanceResetOrdenacion = "area" | "departamento";

export interface ResultadoResetOrdenacionAlcance {
  ok: boolean;
  mensaje: string;
  tipo: AlcanceResetOrdenacion;
  id: number;
  areas_afectadas: number;
  confirmaciones_eliminadas: number;
  borradores_eliminados: number;
}

/** Reinicia exclusivamente las colas incluidas en el alcance seleccionado. */
export async function resetOrdenacionPorAlcance(
  tipo: AlcanceResetOrdenacion,
  id: number,
): Promise<ResultadoResetOrdenacionAlcance> {
  return apiFetch('/admin/reset-ordenacion/alcance', {
    method: "POST",
    body: { tipo, id },
  });
}
