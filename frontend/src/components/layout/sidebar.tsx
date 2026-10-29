"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  LayoutDashboard, 
  Users, 
  BookOpen, 
  BookOpenCheck,
  CheckSquare, 
  Upload,
  Building2,
  Layers,
  ChevronLeft,
  ChevronRight,
  CalendarDays,
  GitCompareArrows,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { memo, useCallback, useEffect, useMemo, useState } from "react";
import { getUserRole } from "@/lib/auth";

type VisibleRole = ReturnType<typeof getUserRole>;

const NAV_ITEMS: ReadonlyArray<{
  label: string;
  href: string;
  icon: typeof LayoutDashboard;
  roles: readonly VisibleRole[];
}> = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, roles: ['Admin', 'Responsable de departamento', 'Responsable de área', 'Profesor', 'PSI'] },
  { label: "Departamentos", href: "/departamentos", icon: Building2, roles: ['Admin'] },
  { label: "Áreas", href: "/areas", icon: Layers, roles: ['Admin', 'Responsable de departamento'] },
  { label: "Profesores", href: "/profesores", icon: Users, roles: ['Admin', 'Responsable de departamento', 'Responsable de área', 'Profesor', 'PSI'] },
  { label: "Actividades", href: "/actividades", icon: BookOpen, roles: ['Admin', 'Responsable de departamento', 'Responsable de área', 'Profesor', 'PSI'] },
  { label: "Adjudicaciones", href: "/adjudicaciones", icon: BookOpenCheck, roles: ['Admin', 'Responsable de departamento', 'Responsable de área', 'Profesor', 'PSI'] },
  { label: "Calendario docente", href: "/calendario-docente", icon: CalendarDays, roles: ['Admin', 'Responsable de departamento', 'Responsable de área', 'Profesor', 'PSI'] },
  { label: "Conflictos", href: "/conflictos", icon: GitCompareArrows, roles: ['Admin', 'Responsable de departamento', 'Responsable de área'] },
  { label: "Ordenación", href: "/eleccion", icon: CheckSquare, roles: ['Admin', 'Responsable de departamento', 'Responsable de área', 'Profesor'] },
  { label: "Importación", href: "/importacion", icon: Upload, roles: ['Admin'] },
] as const;

export const SidebarContent = memo(function SidebarContent({ isCollapsed, onToggle, onNavigate }: { isCollapsed?: boolean, onToggle?: () => void, onNavigate?: () => void }) {
  const pathname = usePathname();
  // localStorage no está disponible durante el renderizado del servidor. Empezar
  // con el mismo rol en servidor y cliente evita que el menú se hidrate con
  // enlaces distintos y se rompa la navegación al recuperar la sesión.
  const [role, setRole] = useState<ReturnType<typeof getUserRole>>("Profesor");

  useEffect(() => {
    setRole(getUserRole());
  }, []);

  const filteredItems = useMemo(
    () => NAV_ITEMS.filter((item) => item.roles.includes(role)),
    [role],
  );

  return (
    <div className="flex flex-col h-full py-4">
      <nav className="flex-1 px-3 space-y-1">
        {filteredItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              aria-current={isActive ? "page" : undefined}
              title={isCollapsed ? item.label : undefined}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md transition-colors group",
                isActive 
                  ? "bg-primary text-primary-foreground" 
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              )}
            >
              <item.icon className="w-5 h-5 shrink-0" />
              {!isCollapsed && <span className="text-sm font-medium">{item.label}</span>}
            </Link>
          );
        })}
      </nav>
      
      {onToggle && (
        <div className="px-3 pt-4 border-t mt-auto">
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-center md:justify-start"
            onClick={onToggle}
          >
            {isCollapsed ? <ChevronRight className="w-5 h-5" /> : <div className="flex items-center gap-2"><ChevronLeft className="w-5 h-5" /> <span className="text-xs">Contraer</span></div>}
          </Button>
        </div>
      )}
    </div>
  );
});

export const Sidebar = memo(function Sidebar() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const alternarColapsado = useCallback(() => {
    setIsCollapsed((actual) => !actual);
  }, []);

  return (
    <aside className={cn(
      "fixed left-0 top-16 h-[calc(100vh-4rem)] border-r bg-card transition-all duration-300 z-40 hidden lg:block",
      isCollapsed ? "w-16" : "w-64"
    )}>
      <SidebarContent isCollapsed={isCollapsed} onToggle={alternarColapsado} />
    </aside>
  );
});
