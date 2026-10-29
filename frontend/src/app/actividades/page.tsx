"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  Clock,
  MoreHorizontal,
  Trash2,
  Edit2,
  X,
  BookOpen,
  FileSpreadsheet,
  FileText,
} from "lucide-react";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";
import { getUserRole } from "@/lib/auth";
import { getAreas } from "@/lib/areas";
import {
  getActividadesParaTabla,
  deleteActividad,
  getLabelTipoActividad,
  getLabelTurno,
  getLabelDuracion,
  getColorEstado,
  descargarDirectorioActividades,
} from "@/lib/actividades";
import { AddActividadDialog } from "@/components/actividades/add-actividad-dialog";
import { useDataSync, useLatestRequest } from "@/hooks/use-data-sync";


interface ActividadTabla {
  id: string;
  codigo: string;
  nombre_asignatura?: string | null;
  tipo: string;
  codigo_grupo: string;
  grupo: string;
  idioma: string;
  duracion: string;
  turno: string;
  dias?: string | null;
  horario?: string | null;
  requiere_horario?: boolean;
  horario_confirmado?: boolean;
  origen_horario?: string;
  horario_detallado?: Array<{ fecha?: string; dia: string; inicio: string; fin: string }>;
  fuente_horario?: string | null;
  horas_asignatura: number;
  horas_actividad: number;
  horas_area: number;
  horas_asignadas: number;
  horas_pendientes: number;
  area_id: number;
  area_ids: number[];
  cuotas_por_area?: { area_id: number; horas: number }[];
  areas: { id: number; codigo: string; nombre: string; departamento_id: number }[];
  area_codigo?: string | null;
  area_nombre?: string | null;
  curso_academico?: string | null;
  tipo_estudio?: string | null;
  codigo_plan?: string | null;
  nombre_plan?: string | null;
  codigo_centro?: string | null;
  nombre_centro?: string | null;
  ciclo?: string | null;
  curso?: string | null;
  caracter?: string | null;
  actividad_oficial_id?: string | null;
  nombre_actividad?: string | null;
  codigo_grupo_oficial?: string | null;
  tiene_asignaciones: boolean;
  status: string;
}

function normalizarTexto(valor?: string | null) {
  return String(valor ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es");
}

export default function ActividadesPage() {
  const [actividades, setActividades] = useState<ActividadTabla[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [editingActividad, setEditingActividad] = useState<ActividadTabla | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [role, setRole] = useState("Profesor");
  const [areas, setAreas] = useState<{ id: number; codigo: string; nombre: string; departamento_id: number }[]>([]);

  // Filtros avanzados
  const [tipoFilter, setTipoFilter] = useState<string>("all");
  const [turnoFilter, setTurnoFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [areaFilter, setAreaFilter] = useState<string>("all");
  const [cuatrimestreFilter, setCuatrimestreFilter] = useState("all");
  const [formatoExportando, setFormatoExportando] = useState<"xlsx" | "pdf" | null>(null);
  const beginLoad = useLatestRequest();
  const hasLoaded = useRef(false);

  const canEdit = role === "Admin" || role.includes("Responsable");

  useEffect(() => {
    setRole(getUserRole());
  }, []);

  const loadActividades = useCallback(async () => {
    const isCurrent = beginLoad();
    try {
      if (!hasLoaded.current) setLoading(true);
      if (isCurrent()) setError(null);
      const [data, areasData] = await Promise.all([
        getActividadesParaTabla(),
        getAreas().catch(() => []),
      ]);
      if (!isCurrent()) return;
      setActividades(data);
      setAreas(areasData);
      hasLoaded.current = true;
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Error al cargar actividades");
      toast({
        title: "Error al cargar actividades",
        description: err instanceof Error ? err.message : "Error desconocido",
        variant: "destructive",
      });
    } finally {
      if (isCurrent()) setLoading(false);
    }
  }, [beginLoad]);

  useEffect(() => {
    void loadActividades();
  }, [loadActividades]);

  useDataSync(loadActividades);

  const handleDeleteActividad = async (actividad: ActividadTabla) => {
    const confirmed = window.confirm(
      `¿Seguro que quieres eliminar la actividad ${actividad.codigo} - ${actividad.grupo}?`
    );

    if (!confirmed) return;

    try {
      setDeletingId(actividad.id);
      await deleteActividad(actividad.id);

      toast({
        title: "Actividad eliminada",
        description: `La actividad ${actividad.codigo} ha sido eliminada correctamente.`,
      });

      await loadActividades();
    } catch (err) {
      toast({
        title: "Error al eliminar actividad",
        description:
          err instanceof Error ? err.message : "Ha ocurrido un error inesperado.",
        variant: "destructive",
      });
    } finally {
      setDeletingId(null);
    }
  };

  const filteredActividades = useMemo(() => {
    const term = normalizarTexto(search).trim();

    return actividades.filter((act) => {
      // El nombre es el criterio principal; el código se conserva como ayuda
      // para las personas que conocen la referencia administrativa.
      const textoActividad = normalizarTexto([
        act.nombre_asignatura, act.grupo, act.tipo, act.codigo,
      ].filter(Boolean).join(" "));
      const matchesSearch = !term || textoActividad.includes(term);

      // Filtros avanzados
      const matchesTipo = tipoFilter === "all" || act.tipo === tipoFilter;
      const matchesTurno = turnoFilter === "all" || act.turno === turnoFilter;
      const matchesStatus = statusFilter === "all" || act.status === statusFilter;
      const matchesArea = areaFilter === "all" || act.area_ids.includes(Number(areaFilter));

      const periodo = normalizarTexto(act.duracion || '').trim();
      const primero = ['1', 'c1', '1c', '1q', 'primer cuatrimestre', '1er cuatrimestre', 'primero'].includes(periodo);
      const segundo = ['2', 'c2', '2c', '2q', 'segundo cuatrimestre', '2º cuatrimestre', 'segundo'].includes(periodo);
      const anual = ['a', 'anual', 'curso completo', 'todo el curso'].includes(periodo);
      const matchesCuatrimestre = cuatrimestreFilter === 'all'
        || (cuatrimestreFilter === 'C1' && (primero || anual))
        || (cuatrimestreFilter === 'C2' && (segundo || anual))
        || (cuatrimestreFilter === 'A' && anual);
      return matchesSearch && matchesTipo && matchesTurno && matchesStatus && matchesArea && matchesCuatrimestre;
    }).sort((primera, segunda) =>
      (primera.nombre_asignatura || primera.codigo).localeCompare(
        segunda.nombre_asignatura || segunda.codigo,
        "es",
      ),
    );
  }, [actividades, search, tipoFilter, turnoFilter, statusFilter, areaFilter, cuatrimestreFilter]);

  const activeFiltersCount = [
    cuatrimestreFilter !== "all",
    tipoFilter !== "all",
    turnoFilter !== "all",
    statusFilter !== "all",
    areaFilter !== "all",
  ].filter(Boolean).length;

  const clearFilters = () => {
    setCuatrimestreFilter("all");
    setTipoFilter("all");
    setTurnoFilter("all");
    setStatusFilter("all");
    setAreaFilter("all");
    setSearch("");
  };

  const exportarDirectorio = async (formato: "xlsx" | "pdf") => {
    setFormatoExportando(formato);
    try {
      await descargarDirectorioActividades(formato);
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
                Catálogo de Actividades
              </h1>
              <p className="text-sm md:text-base text-muted-foreground">
                Gestión completa de actividades docentes del sistema.
              </p>
            </div>

            {canEdit && (
              <AddActividadDialog onActividadCreated={loadActividades} />
            )}
          </div>

          {/* Tabla con filtros */}
          <Card className="border-none shadow-sm overflow-hidden">
            <CardHeader className="pb-3">
              <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
                {/* Buscador */}
                <div className="relative w-full md:w-96">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    placeholder="Buscar por nombre de asignatura, grupo o tipo..."
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
                        Filtros {activeFiltersCount > 0 && `(${activeFiltersCount})`}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-80" align="end">
                      <div className="grid gap-4">
                        <div className="space-y-2">
                          <h4 className="font-bold leading-none text-primary uppercase text-[10px] tracking-widest">
                            Filtros avanzados
                          </h4>
                          <p className="text-xs text-muted-foreground">
                            Segmenta por tipo, turno, estado y área asociada.
                          </p>
                        </div>

                        <div className="space-y-2">
                          <Label className="text-[10px] font-bold uppercase text-muted-foreground">
                            Área
                          </Label>
                          <Select value={areaFilter} onValueChange={setAreaFilter}>
                            <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="Todas las áreas" /></SelectTrigger>
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
                          <Label className="text-[10px] font-bold uppercase text-muted-foreground">
                            Tipo de Actividad
                          </Label>
                          <Select value={tipoFilter} onValueChange={setTipoFilter}>
                            <SelectTrigger className="h-8 text-xs">
                              <SelectValue placeholder="Todos los tipos" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">Todos los tipos</SelectItem>
                              <SelectItem value="GD">Teoría</SelectItem>
                              <SelectItem value="GT">Prácticas</SelectItem>
                              <SelectItem value="GL">Laboratorio</SelectItem>
                              <SelectItem value="GA">Seminario</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>

                        <div className="space-y-2">
                          <Label className="text-[10px] font-bold uppercase text-muted-foreground">
                            Turno
                          </Label>
                          <Select value={turnoFilter} onValueChange={setTurnoFilter}>
                            <SelectTrigger className="h-8 text-xs">
                              <SelectValue placeholder="Todos los turnos" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">Todos los turnos</SelectItem>
                              <SelectItem value="Mañana">Mañana</SelectItem>
                              <SelectItem value="Tarde">Tarde</SelectItem>
                              <SelectItem value="Noche">Noche</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>

                        <div className="space-y-2">
                          <Label className="text-[10px] font-bold uppercase text-muted-foreground">
                            Estado
                          </Label>
                          <Select value={statusFilter} onValueChange={setStatusFilter}>
                            <SelectTrigger className="h-8 text-xs">
                              <SelectValue placeholder="Todos los estados" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">Todos los estados</SelectItem>
                              <SelectItem value="asignado">Asignado</SelectItem>
                              <SelectItem value="pendiente">Pendiente</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>

                        <div className="space-y-2">
                          <Label htmlFor="filtro-cuatrimestre">Cuatrimestre</Label>
                          <Select value={cuatrimestreFilter} onValueChange={setCuatrimestreFilter}>
                            <SelectTrigger id="filtro-cuatrimestre" className="h-8 text-xs"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">Todos los cuatrimestres</SelectItem>
                              <SelectItem value="C1">Primer cuatrimestre (incluye anuales)</SelectItem>
                              <SelectItem value="C2">Segundo cuatrimestre (incluye anuales)</SelectItem>
                              <SelectItem value="A">Solo anuales</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        {activeFiltersCount > 0 && (
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
                  Cargando actividades...
                </div>
              ) : error ? (
                <div className="p-6 space-y-3">
                  <p className="text-sm text-destructive">{error}</p>
                  <Button variant="outline" size="sm" onClick={loadActividades}>
                    Reintentar
                  </Button>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent">
                      <TableHead className="min-w-[220px]">Asignatura</TableHead>
                      <TableHead>Tipo</TableHead>
                      <TableHead>Grupo</TableHead>
                      <TableHead>Área</TableHead>
                      <TableHead>Idioma</TableHead>
                      <TableHead>Turno</TableHead>
                      <TableHead>Horas</TableHead>
                      <TableHead>Estado</TableHead>
                      {canEdit && <TableHead className="text-right">Acciones</TableHead>}
                    </TableRow>
                  </TableHeader>

                  <TableBody>
                    {filteredActividades.map((actividad) => (
                      <TableRow key={actividad.id} className="hover:bg-muted/30">
                        <TableCell className="font-bold text-primary">
                          {actividad.nombre_asignatura || actividad.codigo}
                          {actividad.nombre_asignatura && (
                            <p className="mt-1 text-xs font-normal text-muted-foreground">Código {actividad.codigo}</p>
                          )}
                        </TableCell>

                        <TableCell>
                          <Badge variant="outline" className="text-[10px] font-bold">
                            {getLabelTipoActividad(actividad.tipo)}
                          </Badge>
                        </TableCell>

                        <TableCell className="font-medium">
                          {actividad.grupo}
                          {actividad.requiere_horario === false ? (
                            <p className="mt-1 text-xs font-normal text-sky-700">
                              Sin horario fijo · no genera solapes
                            </p>
                          ) : (actividad.dias || actividad.horario) && (
                            <p className="mt-1 text-xs font-normal text-muted-foreground">
                              {[actividad.dias, actividad.horario].filter(Boolean).join(" · ")}
                              {actividad.horario_confirmado ? " · confirmado" : " · pendiente"}
                            </p>
                          )}
                        </TableCell>

                        <TableCell className="text-xs">
                          <div className="flex max-w-48 flex-wrap gap-1">
                            {actividad.areas.map((area) => (
                              <Badge key={area.id} variant="outline" className="text-[10px]">{area.codigo}</Badge>
                            ))}
                          </div>
                          {actividad.areas.length === 0 && <p className="font-semibold text-primary">{actividad.area_codigo || "Sin área"}</p>}
                        </TableCell>

                        <TableCell className="text-xs uppercase">
                          {actividad.idioma}
                        </TableCell>

                        <TableCell className="text-xs">
                          <div className="flex items-center gap-1.5">
                            <Clock className="w-3 h-3 text-muted-foreground" />
                            {getLabelTurno(actividad.turno)}
                          </div>
                        </TableCell>

                        <TableCell>
                          <div className="flex flex-col">
                            <span className="font-bold text-primary">
                              {actividad.horas_actividad}h
                            </span>
                            <span className="text-[9px] text-muted-foreground uppercase font-bold">
                              {actividad.horas_asignadas}h / {actividad.horas_area}h
                            </span>
                          </div>
                        </TableCell>

                        <TableCell>
                          <Badge
                            variant={actividad.status === "asignado" ? "secondary" : "outline"}
                            className={`capitalize font-bold text-[10px] px-2 py-0 h-5 ${getColorEstado(
                              actividad.status
                            )}`}
                          >
                            {actividad.status}
                          </Badge>
                        </TableCell>

                        {canEdit && (
                          <TableCell className="text-right">
                            <DropdownMenu modal={false}>
                              <DropdownMenuTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-8 w-8"
                                  disabled={deletingId === actividad.id}
                                >
                                  <MoreHorizontal className="w-4 h-4" />
                                </Button>
                              </DropdownMenuTrigger>

                              <DropdownMenuContent align="end">
                                <DropdownMenuItem
                                  className="cursor-pointer"
                                  onSelect={(e) => {
                                    e.preventDefault();
                                    setEditingActividad(actividad);
                                  }}
                                >
                                  <Edit2 className="w-4 h-4 mr-2" />
                                  Editar actividad
                                </DropdownMenuItem>

                                <DropdownMenuItem
                                  className="cursor-pointer text-destructive focus:text-destructive"
                                  onClick={() => handleDeleteActividad(actividad)}
                                >
                                  <Trash2 className="w-4 h-4 mr-2" />
                                  {deletingId === actividad.id ? "Eliminando..." : "Eliminar"}
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </TableCell>
                        )}
                      </TableRow>
                    ))}

                    {filteredActividades.length === 0 && (
                      <TableRow>
                        <TableCell
                          colSpan={canEdit ? 9 : 8}
                          className="text-center text-muted-foreground py-10"
                        >
                          No se encontraron actividades con los criterios de búsqueda actuales.
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
      {canEdit && editingActividad && (
        <AddActividadDialog
          actividad={editingActividad}
          open={!!editingActividad}
          onOpenChange={(open) => {
            if (!open) setEditingActividad(null);
          }}
          onActividadCreated={async () => {
            setEditingActividad(null);
            await loadActividades();
          }}
        />
      )}
    </div>
  );
}
