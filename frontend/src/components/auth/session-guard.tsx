"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { isAuthenticated } from "@/lib/auth";

/** Evita que una ruta privada llegue a cargar datos sin una sesión válida. */
export function SessionGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isLogin = pathname === "/login";
  const [ready, setReady] = useState(isLogin);

  useEffect(() => {
    if (isLogin) {
      setReady(true);
      return;
    }
    if (!isAuthenticated()) {
      setReady(false);
      router.replace("/login");
      return;
    }
    setReady(true);
  }, [isLogin, pathname, router]);

  if (!isLogin && !ready) {
    return <div className="min-h-screen bg-background" aria-label="Comprobando sesión" />;
  }

  return <>{children}</>;
}
