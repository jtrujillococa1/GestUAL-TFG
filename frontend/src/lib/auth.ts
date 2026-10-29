import { apiClient, getToken, setToken, removeToken } from './api-client';
import { User, Professor, Role } from './types';
import { getMiProfesor } from './profesores';

const USER_KEY = 'gestual_current_user';
const PROFESSOR_KEY = 'gestual_current_professor';

interface LoginResponse {
  access_token: string;
  token_type: string;
}

interface LoginCredentials {
  email: string;
  password: string;
}

function normalizeRole(backendRole: string): Role {
  const normalizedRole = String(backendRole || '').trim().toLowerCase();
  const roleMap: Record<string, Role> = {
    'admin': 'Admin',
    'responsable_departamento': 'Responsable de departamento',
    'responsable de departamento': 'Responsable de departamento',
    'responsable_area': 'Responsable de área',
    'responsable de área': 'Responsable de área',
    'profesor': 'Profesor',
    'psi': 'PSI',
  };
  return roleMap[normalizedRole] || 'Profesor';
}

/**
 * Decodificar payload JWT de forma segura
 */
function decodeJWT(token: string): any {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');

    if (typeof window !== 'undefined') {
      // Navegador - usar atob nativo
      const jsonPayload = atob(base64);
      return JSON.parse(jsonPayload);
    } else {
      // Servidor Node.js - usar Buffer
      const jsonPayload = Buffer.from(base64, 'base64').toString('utf-8');
      return JSON.parse(jsonPayload);
    }
  } catch (error) {
    console.error('Error decodificando JWT:', error);
    throw new Error('Token JWT inválido');
  }
}

export async function login(credentials: LoginCredentials): Promise<User> {
  try {
    const formData = new URLSearchParams();
    formData.append('username', credentials.email);
    formData.append('password', credentials.password);

    const response = await apiClient.post<LoginResponse>('/auth/token', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });

    setToken(response.data.access_token);
    const user = await getCurrentUser();

    if (typeof window !== 'undefined') {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    }

    if (user.id) {
      try {
        const professor = await getCurrentProfessor();
        if (professor && typeof window !== 'undefined') {
          localStorage.setItem(PROFESSOR_KEY, JSON.stringify(professor));
        }
      } catch (err) {
        console.log('Usuario no tiene profesor asociado');
      }
    }

    return user;
  } catch (error: any) {
    console.error('❌ Error en login:', error);
    throw new Error(error.response?.data?.detail || 'Credenciales inválidas');
  }
}

export async function getCurrentUser(): Promise<User> {
  try {
    const token = getToken();

    if (!token) {
      throw new Error('No hay token de autenticación');
    }

    // Decodificar el token JWT de forma segura
    const payload = decodeJWT(token);

    const user: User = {
      id: String(payload.sub),
      nombre: payload.email.split('@')[0],
      apellidos: '',
      email: payload.email,
      rol: normalizeRole(payload.rol),
      activo: true,
    };

    return user;
  } catch (error) {
    console.error('Error obteniendo usuario:', error);
    if (typeof window !== 'undefined') {
      const cached = localStorage.getItem(USER_KEY);
      if (cached) {
        return JSON.parse(cached);
      }
    }
    throw error;
  }
}

export async function getCurrentProfessor(): Promise<Professor | null> {
  try {
    const profesorData = await getMiProfesor();
    if (!profesorData) return null;

    const usuarioId = profesorData.usuario_id ?? Number(getCachedUser()?.id);
    if (!Number.isFinite(usuarioId)) return null;

    const professor: Professor = {
      id: profesorData.id,
      usuario_id: usuarioId,
      nombre: profesorData.nombre,
      apellidos: profesorData.apellidos,
      categoria: profesorData.categoria as any,
      fecha_ingreso: profesorData.fecha_ingreso,
      carga_docente: profesorData.carga_docente,
      area_id: profesorData.area_id,
      area_ids: profesorData.area_ids ?? (profesorData.area_id ? [profesorData.area_id] : []),
      areas: profesorData.areas ?? [],
      es_psi: profesorData.es_psi || false,
      disponibilidad_cuatrimestre: profesorData.disponibilidad_cuatrimestre ?? "AMBOS",
    };

    return professor;
  } catch (error) {
    console.error('Error al obtener profesor actual:', error);
    return null;
  }
}

export function getCachedUser(): User | null {
  if (typeof window === 'undefined') return null;
  const cached = localStorage.getItem(USER_KEY);
  if (!cached) return null;
  try {
    const user = JSON.parse(cached) as User;
    // Las sesiones creadas por versiones anteriores podían conservar el rol
    // del backend (p. ej. "responsable_departamento"). Se normaliza aquí para
    // que no pierdan las capacidades de gestión al navegar entre pantallas.
    return { ...user, rol: normalizeRole(user.rol) };
  } catch {
    return null;
  }
}

export function getCachedProfessor(): Professor | null {
  if (typeof window === 'undefined') return null;
  const cached = localStorage.getItem(PROFESSOR_KEY);
  if (!cached) return null;
  try {
    return JSON.parse(cached);
  } catch {
    return null;
  }
}

export function logout(): void {
  removeToken();
  if (typeof window !== 'undefined') {
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(PROFESSOR_KEY);
    window.location.href = `${process.env.NEXT_PUBLIC_BASE_PATH || ''}/login`;
  }
}

export function isAuthenticated(): boolean {
  const token = getToken();
  if (!token) return false;
  try {
    const payload = decodeJWT(token);
    if (typeof payload.exp === "number" && payload.exp * 1000 <= Date.now()) {
      removeToken();
      return false;
    }
    return true;
  } catch {
    removeToken();
    return false;
  }
}

export function getUserRole(): Role {
  const user = getCachedUser();
  return user?.rol || 'Profesor';
}

export function isPSI(): boolean {
  return getUserRole() === 'PSI';
}

export function isAdmin(): boolean {
  return getUserRole() === 'Admin';
}

export function canManageDepartment(): boolean {
  const role = getUserRole();
  return role === 'Admin' || role === 'Responsable de departamento';
}

export function canManageArea(): boolean {
  const role = getUserRole();
  return role === 'Admin' || role === 'Responsable de departamento' || role === 'Responsable de área';
}

/** Actualiza la sesión visible después de editar los datos personales. */
export function updateCachedUser(user: Omit<User, "rol"> & { rol: string }): User {
  const actualizado: User = { ...user, rol: normalizeRole(user.rol) };
  if (typeof window !== "undefined") {
    localStorage.setItem(USER_KEY, JSON.stringify(actualizado));
    window.dispatchEvent(new Event("gestual-profile-updated"));
  }
  return actualizado;
}

/** Conserva alineado el perfil docente almacenado para las pantallas de turnos. */
export function updateCachedProfessor(professor: Professor | null): void {
  if (typeof window === "undefined") return;
  if (professor) localStorage.setItem(PROFESSOR_KEY, JSON.stringify(professor));
  else localStorage.removeItem(PROFESSOR_KEY);
}