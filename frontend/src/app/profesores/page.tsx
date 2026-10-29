"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  Search,
  Filter,
  Eye,
  MoreHorizontal,
  Edit2,
  Trash2,
  UserCog,
  X,
  FileSpreadsheet,
  FileText,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";
import {
  getProfesoresParaTabla,
  deleteProfesor,
  descargarDirectorioProfesores,
  formatearFecha,
} from "@/lib/profesores";
import { getAreas } from "@/lib/areas";
import { AddProfesorDialog } from "@/components/profesores/add-profesor-dialog";
import { getCachedProfessor, getCachedUser, canManageArea } from "@/lib/auth";
import { useDataSync, useLatestRequest } from "@/hooks/use-data-sync";
import { formatearHoras } from "@/lib/horas";

interface ProfesorTabla {
  id: string;
  usuario_id: number | null;
  name: string;
  firstName: string;
  lastName: string;
  categoria: string;
  fecha_ingreso: string;
  carga_docente: number;
  carga_asignada: number;
  carga_restante: number;
  area_id: number | null;
  area_ids: number[];
  horas_objetivo_por_area?: Record<number, number>;
  areas: { id: number; codigo: string; nombre: string; departamento_id: number }[];
  es_psi: boolean;
  disponibilidad_cuatrimestre: "PRIMERO" | "SEGUNDO" | "AMBOS";
  status: "completo" | "incompleto" | "excedido";
  tiene_asignaciones: boolean;
}

export default function ProfesoresPage() {
  const router = useRouter();
  const [profesores, setProfesores] = useState<ProfesorTabla[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [editingProfesor, setEditingProfesor] = useState<ProfesorTabla | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [areas, setAreas] = useState<{ id: number; codigo: string; nombre: string; departamento_id: number }[]>([]);
  const [sesion, setSesion] = useState<{ usuarioId: string | null; profesorId: number | null; puedeGestionar: boolean }>({
    usuarioId: null,
    profesorId: null,
    puedeGestionar: false,
  });

  // Filtros avanzados
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [areaFilter, setAreaFilter] = useState<string>("all");
  const [formatoExportando, setFormatoExportando] = useState<"xlsx" | "pdf" | null>(null);
  const beginLoad = useLatestRequest();
  const hasLoaded = useRef(false);

  const loadProfesores = useCallback(async () => {
    const isCurrent = beginLoad();
    try {
      if (!hasLoaded.current) setLoading(true);
      if (isCurrent()) setError(null);
      const [data, areasData] = await Promise.all([
        getProfesoresParaTabla(),
        getAreas().catch(() => []),
      ]);
      if (!isCurrent()) return;
      setProfesores(data);
      setAreas(areasData);
      hasLoaded.current = true;
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Error al cargar profesores");
      toast({
        title: "Error al cargar profesores",
        description: err instanceof Error ? err.message : "Error desconocido",
        variant: "destructive",
      });
    } finally {
      if (isCurrent()) setLoading(false);
    }
  }, [beginLoad]);

  useEffect(() => {
    void loadProfesores();
    const usuario = getCachedUser();
    const profesorActual = getCachedProfessor();
    setSesion({
      usuarioId: usuario?.id ?? null,
      profesorId: profesorActual?.id ?? null,
      puedeGestionar: canManageArea(),
    });
  }, [loadProfesores]);

  useDataSync(loadProfesores);

  const handleDeleteProfesor = async (profesor: ProfesorTabla) => {
    const confirmed = window.confirm(
      `¿Seguro que quieres eliminar a ${profesor.name}? Esta acción no se puede deshacer.`
    );

    if (!confirmed) return;

    try {
      setDeletingId(profesor.id);
      await deleteProfesor(profesor.id);

      toast({
        title: "Profesor eliminado",
        description: `${profesor.name} ha sido eliminado correctamente.`,
      });

      await loadProfesores();
    } catch (err) {
      toast({
        title: "Error al eliminar profesor",
        description:
          err instanceof Error ? err.message : "Ha ocurrido un error inesperado.",
        variant: "destructive",
      });
    } finally {
      setDeletingId(null);
    }
  };

  const filteredProfesores = useMemo(() => {
    const term = search.toLowerCase().trim();

    return profesores.filter((profesor) => {
      // Búsqueda por texto
      const matchesSearch =
        !term ||
        profesor.name.toLowerCase().includes(term) ||
        profesor.categoria.toLowerCase().includes(term);

      // Filtro por estado
      const matchesStatus = statusFilter === "all" || profesor.status === statusFilter;
      const matchesArea = areaFilter === "all" || profesor.area_ids.includes(Number(areaFilter));

      return matchesSearch && matchesStatus && matchesArea;
    });
  }, [profesores, search, statusFilter, areaFilter]);

  const clearFilters = () => {
    setStatusFilter("all");
    setAreaFilter("all");
    setSearch("");
  };

  const exportarDirectorio = async (formato: "xlsx" | "pdf") => {
    setFormatoExportando(formato);
    try {
      await descargarDirectorioProfesores(formato);
      toast({ title: `Directorio exportado en ${formato.toUpperCase()}` });
    } catch (error) {
      toast({
        title: "No se pudo exportar el directorio",
        description: error instanceof Error ? error.message : "Inténtalo de nuevo.",
        variant: "destructive",
      });
    } finally {
      setFormatoExportando(null);
    }
  };

  const activeFiltersCount = [statusFilter !== "all", areaFilter !== "all"].filter(Boolean).length;
  const hasActiveFilters = activeFiltersCount > 0 || search !== "";

  return (
    <div className="min-h-screen">
      <Header />
      <Sidebar />
      <main className="lg:pl-64 pt-16">
        <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-6">
          {/* Header */}
          <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-primary">
                Directorio de Profesores
              </h1>
              <p className="text-sm md:text-base text-muted-foreground">
                Gestión y visualización de la carga docente por profesor.
              </p>
            </div>

            {sesion.puedeGestionar && <AddProfesorDialog onProfesorCreated={loadProfesores} />}
          </div>

          {/* Tabla con filtros */}
          <Card className="border-none shadow-sm overflow-hidden">
            <CardHeader className="pb-3">
              <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
                {/* Buscador */}
                <div className="relative w-full md:w-96">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    placeholder="Buscar por nombre o categoría..."
                    className="pl-9 h-10"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>

                {/* Botones de acción */}
                <div className="flex gap-2 w-full md:w-auto">
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button
                        variant={activeFiltersCount > 0 ? "default" : "outline"}
                        size="sm"
                        className="flex-1 md:flex-none"
                      >
                        <Filter className="w-4 h-4 mr-2" />
                        Filtros {activeFiltersCount > 0 && ` (${activeFiltersCount})`}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-80" align="end">
                      <div className="grid gap-4">
                        <div className="space-y-2">
                          <h4 className="font-bold leading-none text-primary uppercase text-[10px] tracking-widest">
                            Opciones de filtrado
                          </h4>
                          <p className="text-xs text-muted-foreground">
                            Refina la lista por estado de carga y área de pertenencia.
                          </p>
                        </div>

                        <div className="space-y-2">
                          <Label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                            Área
                          </Label>
                          <Select value={areaFilter} onValueChange={setAreaFilter}>
                            <SelectTrigger className="h-9"><SelectValue placeholder="Todas las áreas" /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">Todas las áreas</SelectItem>
                              {areas.map((area) => (
                                <SelectItem key={area.id} value={String(area.id)}>
                                  {area.codigo} - {area.nombre}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>

                        <div className="space-y-2">
                          <Label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                            Estado de carga
                          </Label>
                          <Select value={statusFilter} onValueChange={setStatusFilter}>
                            <SelectTrigger className="h-9">
                              <SelectValue placeholder="Todos los estados" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">Todos los estados</SelectItem>
                              <SelectItem value="completo">Completo</SelectItem>
                              <SelectItem value="incompleto">Incompleto</SelectItem>
                              <SelectItem value="excedido">Excedido</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>

                        {hasActiveFilters && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={clearFilters}
                            className="h-8 text-[10px] font-bold uppercase tracking-wider text-muted-foreground"
                          >
                            <X className="w-3 h-3 mr-1" /> Limpiar filtros
                          </Button>
                        )}
                      </div>
                    </PopoverContent>
                  </Popover>

                  <Button variant="outline" size="sm" className="flex-1 md:flex-none gap-2" disabled={formatoExportando !== null} onClick={() => void exportarDirectorio("xlsx")}>
                    <FileSpreadsheet className="w-4 h-4" />{formatoExportando === "xlsx" ? "Generando…" : "Excel"}
                  </Button>
                  <Button variant="outline" size="sm" className="flex-1 md:flex-none gap-2" disabled={formatoExportando !== null} onClick={() => void exportarDirectorio("pdf")}>
                    <FileText className="w-4 h-4" />{formatoExportando === "pdf" ? "Generando…" : "PDF"}
                  </Button>
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-0 md:p-6 md:pt-0 overflow-x-auto">
              {loading ? (
                <div className="p-10 text-center text-sm text-muted-foreground">
                  Cargando profesores...
                </div>
              ) : error ? (
                <div className="p-6 space-y-3">
                  <p className="text-sm text-destructive">{error}</p>
                  <Button variant="outline" size="sm" onClick={loadProfesores}>
                    Reintentar
                  </Button>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent">
                      <TableHead className="min-w-[220px]">Nombre</TableHead>
                      <TableHead className="hidden md:table-cell">Categoría</TableHead>
                      <TableHead className="hidden lg:table-cell">Áreas</TableHead>
                      <TableHead className="hidden sm:table-cell">Fecha ingreso</TableHead>
                      <TableHead className="hidden lg:table-cell text-center">
                        Objetivo
                      </TableHead>
                      <TableHead className="text-center">Asignada</TableHead>
                      <TableHead>Estado</TableHead>
                      <TableHead className="text-right">Acciones</TableHead>
                    </TableRow>
                  </TableHeader>

                  <TableBody>
                    {filteredProfesores.map((profesor) => {
                      const esPropio = profesor.usuario_id !== null && sesion.usuarioId === String(profesor.usuario_id);
                      const puedeEditar = esPropio || sesion.puedeGestionar;
                      const puedeEliminar = sesion.puedeGestionar && !esPropio;
                      return (
                      <TableRow key={profesor.id}>
                        <TableCell className="font-medium">
                          <div className="flex flex-col">
                            <span className="truncate max-w-[180px] md:max-w-none text-primary font-bold">
                              {profesor.name}
                            </span>
                            <span className="md:hidden text-[10px] text-muted-foreground mt-1">
                              {profesor.categoria}
                            </span>
                          </div>
                        </TableCell>

                        <TableCell className="hidden md:table-cell">
                          <Badge variant="outline" className="text-[10px]">
                            {profesor.categoria}
                          </Badge>
                          {profesor.disponibilidad_cuatrimestre !== "AMBOS" && (
                            <p className="mt-1 text-[10px] text-muted-foreground">
                              {profesor.disponibilidad_cuatrimestre === "PRIMERO" ? "Solo 1.º cuatrimestre" : "Solo 2.º cuatrimestre"}
                            </p>
                          )}
                        </TableCell>

                        <TableCell className="hidden lg:table-cell">
                          <div className="flex max-w-52 flex-wrap gap-1">
                            {profesor.areas.map((area) => (
                              <Badge key={area.id} variant="outline" className="text-[10px]">
                                {area.codigo}
                              </Badge>
                            ))}
                            {profesor.areas.length === 0 && <span className="text-xs text-muted-foreground">Sin área</span>}
                          </div>
                        </TableCell>

                        <TableCell className="hidden sm:table-cell whitespace-nowrap text-xs">
                          {formatearFecha(profesor.fecha_ingreso)}
                        </TableCell>

                        <TableCell className="hidden lg:table-cell text-center font-medium">
                          {formatearHoras(profesor.carga_docente)} h
                        </TableCell>

                        <TableCell className="text-center font-bold text-primary">
                          {formatearHoras(profesor.carga_asignada)} h
                        </TableCell>

                        <TableCell>
                          <Badge
                            variant={
                              profesor.status === "completo"
                                ? "secondary"
                                : profesor.status === "excedido"
                                ? "destructive"
                                : "outline"
                            }
                            className={`capitalize font-medium text-[10px] px-2 py-0 ${
                              profesor.status === "completo" ? "bg-green-100 text-green-800" : ""
                            }`}
                          >
                            {profesor.status}
                          </Badge>
                        </TableCell>

                        <TableCell className="text-right">
                          {puedeEditar || puedeEliminar ? <DropdownMenu modal={false}>
                            <DropdownMenuTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                disabled={deletingId === profesor.id}
                              >
                                <MoreHorizontal className="w-4 h-4" />
                              </Button>
                            </DropdownMenuTrigger>

                            <DropdownMenuContent align="end">
                              {esPropio ? (
                                <DropdownMenuItem className="cursor-pointer" onSelect={() => router.push("/perfil")}>
                                  <UserCog className="w-4 h-4 mr-2" /> Editar mi perfil
                                </DropdownMenuItem>
                              ) : sesion.puedeGestionar ? (
                                <DropdownMenuItem
                                  className="cursor-pointer"
                                  onSelect={(e) => {
                                    e.preventDefault();
                                    setEditingProfesor(profesor);
                                  }}
                                >
                                  <UserCog className="w-4 h-4 mr-2" /> Editar profesor
                                </DropdownMenuItem>
                              ) : null}

                              {puedeEliminar && <DropdownMenuItem
                                className="cursor-pointer text-destructive focus:text-destructive"
                                onClick={() => handleDeleteProfesor(profesor)}
                              >
                                <Trash2 className="w-4 h-4 mr-2" />
                                {deletingId === profesor.id ? "Eliminando..." : "Eliminar"}
                              </DropdownMenuItem>}
                            </DropdownMenuContent>
                          </DropdownMenu> : <span className="text-xs text-muted-foreground">Sin permisos</span>}
                        </TableCell>
                      </TableRow>
                    );})}

                    {filteredProfesores.length === 0 && (
                      <TableRow>
                        <TableCell
                          colSpan={8}
                          className="text-center text-muted-foreground py-10"
                        >
                          No se encontraron profesores con los filtros actuales.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>
      </main>

      {/* Modal de edición */}
      {editingProfesor && (
        <AddProfesorDialog
          profesor={editingProfesor}
          open={!!editingProfesor}
          onOpenChange={(open) => {
            if (!open) setEditingProfesor(null);
          }}
          onProfesorCreated={async () => {
            setEditingProfesor(null);
            await loadProfesores();
          }}
        />
      )}
    </div>
  );
}
