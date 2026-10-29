"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Layers, MoreHorizontal, User, Building2, Search, Edit2, Trash2 } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { getAreas, deleteArea } from "@/lib/areas";
import { getDepartamentos } from "@/lib/departamentos";
import { getCuentasResponsables } from "@/lib/usuarios";
import { AddAreaDialog } from "@/components/areas/add-area-dialog";
import { useDataSync, useLatestRequest } from "@/hooks/use-data-sync";

interface AreaTabla {
  id: number;
  codigo: string;
  nombre: string;
  departamento_id: number;
  departamento_nombre?: string;
  responsable_area_id?: number | null;
  responsable_nombre?: string;
}

export default function AreasPage() {
  const [areas, setAreas] = useState<AreaTabla[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [editingArea, setEditingArea] = useState<AreaTabla | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const beginLoad = useLatestRequest();
  const hasLoaded = useRef(false);

  const loadAreas = useCallback(async () => {
    const isCurrent = beginLoad();
    try {
      if (!hasLoaded.current) setLoading(true);
      if (isCurrent()) setError(null);
      const [areasData, depts, cuentas] = await Promise.all([
        getAreas(),
        getDepartamentos(),
        getCuentasResponsables(),
      ]);
      if (!isCurrent()) return;

      // Evita recorrer el catálogo completo de departamentos y profesorado
      // por cada área al trabajar con estructuras universitarias grandes.
      const departamentosPorId = new Map(depts.map((departamento) => [departamento.id, departamento]));
      const responsablesPorId = new Map(cuentas.map((cuenta) => [cuenta.id, cuenta]));
      const areasConInfo = areasData.map((area) => {
        const dept = departamentosPorId.get(area.departamento_id);
        const resp = area.responsable_area_id == null
          ? undefined
          : responsablesPorId.get(area.responsable_area_id);

        return {
          ...area,
          departamento_nombre: dept?.nombre,
          responsable_nombre: resp ? `${resp.nombre} ${resp.apellidos}` : undefined,
        };
      });

      setAreas(areasConInfo);
      hasLoaded.current = true;
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Error desconocido");
      toast({
        title: "Error al cargar áreas",
        description: err instanceof Error ? err.message : "Error desconocido",
        variant: "destructive",
      });
    } finally {
      if (isCurrent()) setLoading(false);
    }
  }, [beginLoad]);

  useEffect(() => {
    void loadAreas();
  }, [loadAreas]);

  useDataSync(loadAreas);

  const handleDeleteArea = async (area: AreaTabla) => {
    const confirmed = window.confirm(
      `¿Seguro que quieres eliminar el área ${area.nombre}?`
    );

    if (!confirmed) return;

    try {
      setDeletingId(area.id);
      await deleteArea(area.id);

      toast({
        title: "Área eliminada",
        description: `El área ${area.nombre} ha sido eliminada correctamente.`,
      });

      await loadAreas();
    } catch (err) {
      toast({
        title: "Error al eliminar área",
        description: err instanceof Error ? err.message : "Ha ocurrido un error inesperado.",
        variant: "destructive",
      });
    } finally {
      setDeletingId(null);
    }
  };

  const filteredAreas = areas.filter(
    (area) =>
      area.nombre.toLowerCase().includes(search.toLowerCase()) ||
      area.codigo.toLowerCase().includes(search.toLowerCase())
  );

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
                Áreas de Conocimiento
              </h1>
              <p className="text-sm text-muted-foreground">
                Áreas de conocimiento y sus responsables.
              </p>
            </div>

            <AddAreaDialog onAreaCreated={loadAreas} />
          </div>

          {/* Tabla */}
          <Card className="border-none shadow-sm overflow-hidden">
            <CardHeader className="pb-3">
              <div className="relative w-full md:w-96">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="Buscar por código o nombre..."
                  className="pl-9 h-10"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            </CardHeader>

            <CardContent className="p-0 overflow-x-auto">
              {loading ? (
                <div className="p-10 text-center text-sm text-muted-foreground">
                  Cargando áreas...
                </div>
              ) : error ? (
                <div className="space-y-3 p-6">
                  <p className="text-sm text-destructive">{error}</p>
                  <Button variant="outline" size="sm" onClick={loadAreas}>Reintentar</Button>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Código</TableHead>
                      <TableHead>Nombre</TableHead>
                      <TableHead>Departamento</TableHead>
                      <TableHead>Responsable de Área</TableHead>
                      <TableHead className="text-right">Acciones</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredAreas.map((area) => (
                      <TableRow key={area.id}>
                        <TableCell className="font-bold">{area.codigo}</TableCell>
                        <TableCell className="text-primary font-semibold">
                          {area.nombre}
                        </TableCell>
                        <TableCell className="text-xs">
                          <div className="flex items-center gap-1.5">
                            <Building2 className="w-3 h-3" />
                            {area.departamento_nombre || "Sin departamento"}
                          </div>
                        </TableCell>
                        <TableCell>
                          {area.responsable_nombre ? (
                            <div className="flex items-center gap-2 text-xs">
                              <User className="w-3 h-3 text-primary" />
                              {area.responsable_nombre}
                            </div>
                          ) : (
                            <span className="text-[10px] italic text-muted-foreground">
                              Sin asignar
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          <DropdownMenu modal={false}>
                            <DropdownMenuTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                disabled={deletingId === area.id}
                              >
                                <MoreHorizontal className="w-4 h-4" />
                              </Button>
                            </DropdownMenuTrigger>

                            <DropdownMenuContent align="end">
                              <DropdownMenuItem
                                className="cursor-pointer"
                                onSelect={(e) => {
                                  e.preventDefault();
                                  setEditingArea(area);
                                }}
                              >
                                <Edit2 className="w-4 h-4 mr-2" />
                                Editar área
                              </DropdownMenuItem>

                              <DropdownMenuItem
                                className="cursor-pointer text-destructive focus:text-destructive"
                                onClick={() => handleDeleteArea(area)}
                              >
                                <Trash2 className="w-4 h-4 mr-2" />
                                {deletingId === area.id ? "Eliminando..." : "Eliminar"}
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}

                    {filteredAreas.length === 0 && (
                      <TableRow>
                        <TableCell
                          colSpan={5}
                          className="text-center text-muted-foreground py-10"
                        >
                          No se encontraron áreas.
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
      {editingArea && (
        <AddAreaDialog
          area={editingArea}
          open={!!editingArea}
          onOpenChange={(open) => {
            if (!open) setEditingArea(null);
          }}
          onAreaCreated={async () => {
            setEditingArea(null);
            await loadAreas();
          }}
        />
      )}
    </div>
  );
}
