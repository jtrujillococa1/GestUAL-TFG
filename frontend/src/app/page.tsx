"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** La raíz es siempre la puerta de acceso, incluso si quedó una sesión guardada. */
export default function RootPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/login");
  }, [router]);

  return <div className="min-h-screen bg-background" />;
}
