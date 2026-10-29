"use client";

import { LogOut, User as UserIcon, Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuLabel, 
  DropdownMenuSeparator, 
  DropdownMenuTrigger 
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useRouter } from "next/navigation";
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet";
import { SidebarContent } from "./sidebar";
import { getCachedUser, logout } from "@/lib/auth";
import { memo, useEffect, useState } from "react";

// Definir tipo local para evitar conflictos
interface HeaderUserData {
  id: string;
  nombre: string;
  apellidos: string;
  email: string;
  rol: string;
  activo: boolean;
}

// El encabezado no recibe datos de las pantallas. Memorizarlo evita volver a
// renderizar avatar, menú y SVG en cada pulsación de filtros o búsqueda de la
// vista que esté abierta; sus propios cambios de sesión siguen actualizándolo.
export const Header = memo(function Header() {
  const router = useRouter();
  const [user, setUser] = useState<HeaderUserData | null>(null);
  const [menuAbierto, setMenuAbierto] = useState(false);

  useEffect(() => {
    const cargarUsuario = () => {
      const userData = getCachedUser();
      if (!userData) return;
      setUser({
          id: String(userData.id || ''),
          nombre: userData.nombre || '',
          apellidos: userData.apellidos || '',
          email: userData.email || '',
          rol: userData.rol || 'Profesor',
          activo: userData.activo !== undefined ? userData.activo : true,
        });
    };
    cargarUsuario();
    window.addEventListener("gestual-profile-updated", cargarUsuario);
    return () => window.removeEventListener("gestual-profile-updated", cargarUsuario);
  }, []);

  const handleLogout = () => {
    logout();
  };

  const getInitials = () => {
    if (!user) return 'U';
    const firstInitial = user.nombre?.[0] || '';
    const lastInitial = user.apellidos?.[0] || '';
    return (firstInitial + lastInitial).toUpperCase() || 'U';
  };

  return (
    <header className="fixed top-0 left-0 right-0 h-16 border-b bg-card z-50 px-4 md:px-6 flex items-center justify-between">
      <div className="flex items-center gap-2 md:gap-4">
        <div className="lg:hidden">
          <Sheet open={menuAbierto} onOpenChange={setMenuAbierto}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="md:mr-2" aria-label="Abrir menú de navegación">
                <Menu className="w-5 h-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="p-0 w-64">
              <SheetTitle className="sr-only">Navegación de GestUAL</SheetTitle>
              <div className="pt-16 h-full">
                <SidebarContent onNavigate={() => setMenuAbierto(false)} />
              </div>
            </SheetContent>
          </Sheet>
        </div>
        
        <div className="bg-primary p-1.5 rounded-lg shrink-0">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-5 h-5 md:w-6 md:h-6 text-white">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
          </svg>
        </div>
        <div className="flex flex-col overflow-hidden">
          <span className="text-lg md:text-xl font-bold tracking-tight text-primary truncate">GestUAL</span>
          <span className="text-[8px] md:text-[10px] uppercase tracking-widest text-muted-foreground font-semibold truncate">Ordenación Docente</span>
        </div>
      </div>

      <div className="flex items-center gap-2 md:gap-6">

        <div className="flex items-center gap-1 md:gap-3">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="relative h-9 w-9 rounded-full">
                <Avatar className="h-9 w-9 border">
                  <AvatarImage 
                    src={`https://api.dicebear.com/7.x/initials/svg?seed=${encodeURIComponent(user?.nombre || 'U')}`} 
                    alt="Avatar" 
                  />
                  <AvatarFallback>{getInitials()}</AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56" align="end" forceMount>
              <DropdownMenuLabel className="font-normal">
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-medium leading-none">
                    {user?.nombre || 'Usuario'} {user?.apellidos || ''}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {user?.email || ''}
                  </p>
                  <p className="text-[10px] text-muted-foreground uppercase font-bold tracking-tight">
                    {user?.rol || 'Profesor'}
                  </p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="cursor-pointer" onSelect={() => router.push("/perfil")}>
                <UserIcon className="mr-2 h-4 w-4" />
                <span>Mi Perfil</span>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem 
                className="cursor-pointer text-destructive focus:text-destructive" 
                onClick={handleLogout}
              >
                <LogOut className="mr-2 h-4 w-4" />
                <span>Cerrar sesión</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
});
