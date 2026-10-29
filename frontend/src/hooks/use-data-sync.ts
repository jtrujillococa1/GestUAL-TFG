"use client";

import { useCallback, useEffect, useRef } from "react";
import { DATA_CHANGED_EVENT } from "@/lib/api-client";

/**
 * Descarta respuestas de peticiones que han quedado antiguas al navegar,
 * recargar o lanzar una nueva consulta. Así una respuesta lenta no puede
 * sobrescribir el estado más reciente de una página.
 */
export function useLatestRequest() {
  const version = useRef(0);

  return useCallback(() => {
    const currentVersion = ++version.current;
    // Solo una solicitud posterior de esta misma pantalla invalida la actual.
    // No se usa el montaje/desmontaje de efectos como señal: React puede
    // repetir esos efectos en desarrollo y descartar una respuesta válida.
    return () => currentVersion === version.current;
  }, []);
}

/**
 * Mantiene una pantalla al día al volver a enfocarla y cuando otra operación
 * CRUD cambia datos. Agrupa avisos cercanos para no duplicar recargas.
 */
export function useDataSync(refresh: () => void | Promise<void>) {
  const refreshRef = useRef(refresh);
  const lastRefresh = useRef(0);
  const scheduled = useRef<number | null>(null);
  const scheduledForce = useRef(false);
  const changePendingWhileHidden = useRef(false);

  useEffect(() => {
    refreshRef.current = refresh;
  }, [refresh]);

  useEffect(() => {
    // La carga inicial de cada pantalla se dispara justo antes de este efecto.
    // Marcarla evita que el foco inicial del navegador la repita enseguida.
    lastRefresh.current = Date.now();

    const run = (force = false) => {
      const now = Date.now();
      if (!force && now - lastRefresh.current < 1_500) return;
      lastRefresh.current = now;
      void refreshRef.current();
    };
    const schedule = (force = false) => {
      scheduledForce.current ||= force;
      if (scheduled.current !== null) return;
      scheduled.current = window.setTimeout(() => {
        scheduled.current = null;
        const forceRefresh = scheduledForce.current;
        scheduledForce.current = false;
        run(forceRefresh);
      }, 80);
    };
    const handleFocus = () => {
      if (document.visibilityState === "visible") schedule(false);
    };
    const handleVisibility = () => {
      if (document.visibilityState !== "visible") return;
      const force = changePendingWhileHidden.current;
      changePendingWhileHidden.current = false;
      schedule(force);
    };
    const handleChange = () => {
      if (document.visibilityState === "visible") {
        schedule(true);
      } else {
        // Si una escritura ocurre mientras esta pantalla no se muestra, se
        // refresca al volver, sin gastar red ni CPU en segundo plano.
        changePendingWhileHidden.current = true;
      }
    };

    window.addEventListener("focus", handleFocus);
    window.addEventListener(DATA_CHANGED_EVENT, handleChange);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      window.removeEventListener("focus", handleFocus);
      window.removeEventListener(DATA_CHANGED_EVENT, handleChange);
      document.removeEventListener("visibilitychange", handleVisibility);
      if (scheduled.current !== null) window.clearTimeout(scheduled.current);
      scheduled.current = null;
      scheduledForce.current = false;
      changePendingWhileHidden.current = false;
    };
  }, []);
}
