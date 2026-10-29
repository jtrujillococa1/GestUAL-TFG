/** Presenta cargas docentes sin artefactos de precisión de JavaScript. */
export function redondearHoras(valor: number | null | undefined, decimales = 1): number {
  const numero = Number(valor);
  if (!Number.isFinite(numero)) return 0;
  const factor = 10 ** decimales;
  return Math.round((numero + Number.EPSILON) * factor) / factor;
}

export function formatearHoras(valor: number | null | undefined, decimales = 1): string {
  return redondearHoras(valor, decimales).toLocaleString("es-ES", {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimales,
  });
}
