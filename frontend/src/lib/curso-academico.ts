/** Normaliza solo la etiqueta; conserva la clave original enviada a la API. */
export function formatearCursoAcademico(curso: string): string {
  const match = curso.trim().match(/^(\d{4})[-/](\d{2}|\d{4})$/);
  if (!match) return curso;
  return `${match[1]}/${match[2].length === 2 ? match[1].slice(0, 2) + match[2] : match[2]}`;
}
