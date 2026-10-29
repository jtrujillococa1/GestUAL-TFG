import { apiFetch } from "./api-client";

export interface UsuarioPerfil {
  id: number;
  nombre: string;
  apellidos: string;
  email: string;
  rol: string;
  activo: boolean;
}

export interface CuentaResponsable extends UsuarioPerfil {
  rol: "responsable_departamento" | "responsable_area";
}

export interface ActualizarUsuarioPayload {
  nombre?: string;
  apellidos?: string;
  email?: string;
  password?: string;
}

export function getMiUsuario(): Promise<UsuarioPerfil> {
  return apiFetch<UsuarioPerfil>("/usuarios/me");
}

export function getCuentasResponsables(): Promise<CuentaResponsable[]> {
  return apiFetch<CuentaResponsable[]>("/usuarios/responsables");
}

export function updateMiUsuario(
  usuarioId: number,
  cambios: ActualizarUsuarioPayload,
): Promise<UsuarioPerfil> {
  return apiFetch<UsuarioPerfil>(`/usuarios/${usuarioId}`, {
    method: "PUT",
    body: cambios,
  });
}
