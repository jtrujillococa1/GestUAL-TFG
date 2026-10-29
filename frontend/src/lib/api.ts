/**
 * API Wrapper - Exporta la función apiFetch del cliente HTTP
 * Este archivo mantiene la compatibilidad con el código existente
 * que importa desde '@/lib/api'
 */

export { apiFetch } from './api-client';

// Re-exportar helpers útiles si son necesarios en otros módulos
export { getToken, setToken, removeToken } from './api-client';