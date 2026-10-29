import { apiFetch } from "./api-client";

export type MovimientoConflicto = {
  actividad_id: number;
  asignatura: string;
  codigo: string;
  grupo: string;
  desde_profesor_id: number;
  desde: string;
  hacia_profesor_id: number;
  hacia: string;
  horas: number;
  prioridad_destino?: number | null;
};

export type PropuestaConflicto = {
  id: number;
  area_id: number;
  profesor_bloqueado_id: number;
  profesor_bloqueado: string;
  version_base: number;
  estado: "PENDIENTE" | "APROBADA" | "RECHAZADA" | "OBSOLETA";
  creada_en: string;
  decidida_en?: string | null;
  motivo_rechazo?: string | null;
  propuesta: {
    movimientos: MovimientoConflicto[];
    afectados: { profesor_id: number; profesor: string }[];
    impacto: { profesores_afectados: number; movimientos: number; horas_reasignadas: number; limite_profesores?: number; criterio?: string };
  };
};

export function getPropuestasConflicto(areaId: number) {
  return apiFetch<PropuestaConflicto[]>(`/areas/${areaId}/conflictos`);
}

export function generarPropuestaConflicto(areaId: number) {
  return apiFetch<PropuestaConflicto>(`/areas/${areaId}/conflictos/propuestas`, { method: "POST", timeoutMs: 120000 });
}

export function decidirPropuestaConflicto(
  areaId: number,
  propuestaId: number,
  aprobar: boolean,
  motivo?: string,
) {
  return apiFetch<{ id: number; area_id: number; estado: string; version: number; advertencia_calendario?: string }>(
    `/areas/${areaId}/conflictos/${propuestaId}/decision`,
    { method: "POST", body: { aprobar, motivo } },
  );
}
