import axios, { AxiosError } from 'axios';

// URL base del backend FastAPI
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Clave para almacenar el token en localStorage
const TOKEN_KEY = 'gestual_access_token';

// Varias vistas pueden pedir el mismo recurso durante el mismo instante (por
// ejemplo, al recuperar el foco justo después de una actualización). Compartir
// únicamente esas lecturas simultáneas evita tráfico y trabajo duplicados sin
// conservar resultados antiguos: al terminar la petición se elimina del mapa.
// Las peticiones con AbortSignal mantienen siempre su propio ciclo de vida.
const inFlightGetRequests = new Map<string, Promise<unknown>>();

function serializarParametros(params?: Record<string, unknown>): string {
  if (!params) return "";
  return Object.keys(params)
    .sort()
    .map((key) => `${key}:${JSON.stringify(params[key])}`)
    .join("|");
}

function claveGet(endpoint: string, params?: Record<string, unknown>): string {
  // Incluir el token impide compartir una lectura entre dos sesiones si se
  // cierra una cuenta e inicia otra antes de que la primera respuesta termine.
  return `${getToken() ?? "anonimo"}::${endpoint}::${serializarParametros(params)}`;
}

function invalidarLecturasEnCurso(): void {
  // No se cancelan las peticiones que ya están en marcha; simplemente una
  // lectura posterior a una escritura no reutiliza un resultado potencialmente
  // anterior al cambio.
  inFlightGetRequests.clear();
}

// Cliente axios configurado
export const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
  // Evita que una pantalla quede bloqueada indefinidamente si el servidor no
  // responde. Las operaciones nunca se reintentan automáticamente: un POST o
  // DELETE podría haberse aplicado aunque se pierda la respuesta.
  timeout: 20_000,
});

export const DATA_CHANGED_EVENT = "gestual:data-changed";

export type DataChangeDetail = {
  endpoint: string;
  method: "POST" | "PUT" | "PATCH" | "DELETE";
};

function notifyDataChanged(detail: DataChangeDetail): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<DataChangeDetail>(DATA_CHANGED_EVENT, { detail }));
}

// --- HELPERS DE TOKEN ---
export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === 'undefined') return;
  invalidarLecturasEnCurso();
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  if (typeof window === 'undefined') return;
  invalidarLecturasEnCurso();
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem('gestual_current_user');
  localStorage.removeItem('gestual_current_professor');
}

// Interceptor para agregar token de autenticación en cada petición
apiClient.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Interceptor para manejar errores de autenticación
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (axios.isCancel(error)) {
      return Promise.reject(error);
    }
    if (error.response?.status === 401) {
      removeToken();
      if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
        window.location.href = `${process.env.NEXT_PUBLIC_BASE_PATH || ''}/login`;
      }
    }
    const detail = error.response?.data && typeof error.response.data === 'object' && 'detail' in error.response.data
      ? String((error.response.data as { detail?: unknown }).detail || error.message)
      : error.message;
    return Promise.reject(new Error(detail));
  }
);

// Función helper para peticiones API
export async function apiFetch<T>(
  endpoint: string,
  options: {
    method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
    body?: any;
    params?: Record<string, any>;
    signal?: AbortSignal;
    timeoutMs?: number;
    notifyDataChange?: boolean;
  } = {}
): Promise<T> {
  const method = options.method || "GET";
  try {
    const requestConfig = {
      url: endpoint,
      method,
      data: options.body,
      params: options.params,
      signal: options.signal,
      ...(options.timeoutMs ? { timeout: options.timeoutMs } : {}),
    };

    let responseData: T;
    if (method === "GET" && !options.signal) {
      const key = claveGet(endpoint, options.params);
      const existente = inFlightGetRequests.get(key) as Promise<T> | undefined;
      if (existente) {
        responseData = await existente;
      } else {
        const request = apiClient.request<T>(requestConfig).then((response) => response.data);
        inFlightGetRequests.set(key, request);
        // La limpieza se maneja para éxito y error sin crear una promesa
        // rechazada sin observar en la consola.
        request.then(
          () => { if (inFlightGetRequests.get(key) === request) inFlightGetRequests.delete(key); },
          () => { if (inFlightGetRequests.get(key) === request) inFlightGetRequests.delete(key); },
        );
        responseData = await request;
      }
    } else {
      responseData = (await apiClient.request<T>(requestConfig)).data;
    }
    if (method !== "GET") {
      invalidarLecturasEnCurso();
    }
    if (method !== "GET" && options.notifyDataChange !== false) {
      // Cada escritura informa a las vistas abiertas para que se refresquen.
      notifyDataChanged({ endpoint, method });
    }
    return responseData;
  } catch (error) {
    if (axios.isCancel(error)) throw error;
    if (axios.isAxiosError(error)) {
      throw new Error(error.response?.data?.detail || error.message);
    }
    throw error;
  }
}
