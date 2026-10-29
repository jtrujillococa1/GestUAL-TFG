/**
 * Datos de ejemplo exclusivos de la vista de conflictos mientras se conecta
 * esa pantalla al origen de datos definitivo. No participan en la ordenación.
 */
export interface MockConflict {
  id: string;
  type: string;
  title: string;
  description: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  status: "abierto" | "en proceso" | "resuelto";
  suggestedAction?: string;
}

export const MOCK_CONFLICTS: MockConflict[] = [
  {
    id: "c1",
    type: "solapamiento horario",
    title: "Conflicto de horario: Prof. Sánchez",
    description: "El profesor tiene asignados dos grupos en la misma franja horaria el lunes a las 12:00.",
    severity: "HIGH",
    status: "abierto",
    suggestedAction: "Reasignar el grupo de Programación I a otro docente disponible.",
  },
  {
    id: "c2",
    type: "profesor sin carga completa",
    title: "Carga incompleta: Dra. López",
    description: "La docente tiene 180 horas asignadas de un objetivo de 240 horas.",
    severity: "MEDIUM",
    status: "abierto",
    suggestedAction: "Asignar el grupo pendiente de Sistemas Operativos.",
  },
  {
    id: "c3",
    type: "grupo sin profesor compatible",
    title: "Grupo huérfano: Cálculo II",
    description: "No hay profesores con disponibilidad y perfil adecuado para este grupo.",
    severity: "HIGH",
    status: "en proceso",
  },
];
