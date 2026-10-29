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
import { Building2, MoreHorizontal, User, Search, Edit2, Trash2 } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { getDepartamentos, deleteDepartamento } from "@/lib/departamentos";
import { getCuentasResponsables } from "@/lib/usuarios";
import { AddDepartamentoDialog } from "@/components/departamentos/add-departamento-dialog";
import { useDataSync, useLatestRequest } from "@/hooks/use-data-sync";

interface DepartamentoTabla {
  id: number;
  codigo: string;
  nombre: string;
  responsable_departamento_id?: number | null;
  responsable_nombre?: string;
}

export default function DepartamentosPage() {
  const [departamentos, setDepartamentos] = useState<DepartamentoTabla[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [editingDepartamento, setEditingDepartamento] = useState<DepartamentoTabla | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const beginLoad = useLatestRequest();
  const hasLoaded = useRef(false);

  const loadDepartamentos = useCallback(async () => {
    const isCurrent = beginLoad();
    try {
      if (!hasLoaded.current) setLoading(true);
      if (isCurrent()) setError(null);
      const [depts, cuentas] = await Promise.all([
        getDepartamentos(),
        getCuentasResponsables(),
      ]);
      if (!isCurrent()) return;

      const responsablesPorId = new Map(cuentas.map((cuenta) => [cuenta.id, cuenta]));
      const deptsConInfo = depts.map((dept) => {
        const resp = dept.responsable_departamento_id == null
          ? undefined
          : responsablesPorId.get(dept.responsable_departamento_id);

        return {
          ...dept,
          responsable_nombre: resp ? `${resp.nombre} ${resp.apellidos}` : undefined,
        };
      });

      setDepartamentos(deptsConInfo);
      hasLoaded.current = true;
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Error desconocido");
      toast({
        title: "Error al cargar departamentos",
        description: err instanceof Error ? err.message : "Error desconocido",
        variant: "destructive",
      });
    } finally {
      if (isCurrent()) setLoading(false);
    }
  }, [beginLoad]);

  useEffect(() => {
    void loadDepartamentos();
  }, [loadDepartamentos]);

  useDataSync(loadDepartamentos);

  const handleDeleteDepartamento = async (dept: DepartamentoTabla) => {
    const confirmed = window.confirm(
      `¿Seguro que quieres eliminar el departamento ${dept.nombre}?`
    );

    if (!confirmed) return;

    try {
      setDeletingId(dept.id);
      await deleteDepartamento(dept.id);

      toast({
        title: "Departamento eliminado",
        description: `El departamento ${dept.nombre} ha sido eliminado correctamente.`,
      });

      await loadDepartamentos();
    } catch (err) {
      toast({
        title: "Error al eliminar departamento",
        description: err instanceof Error ? err.message : "Ha ocurrido un error inesperado.",
        variant: "destructive",
      });
    } finally {
      setDeletingId(null);
    }
  };

  const filteredDepartamentos = departamentos.filter(
    (dept) =>
      dept.nombre.toLowerCase().includes(search.toLowerCase()) ||
      dept.codigo.toLowerCase().includes(search.toLowerCase())
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
                Departamentos
              </h1>
              <p className="text-sm text-muted-foreground">
                Gestión de la estructura orgánica universitaria.
              </p>
            </div>

            <AddDepartamentoDialog onDepartamentoCreated={loadDepartamentos} />
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
                  Cargando departamentos...
                </div>
              ) : error ? (
                <div className="space-y-3 p-6">
                  <p className="text-sm text-destructive">{error}</p>
                  <Button variant="outline" size="sm" onClick={loadDepartamentos}>Reintentar</Button>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Código</TableHead>
                      <TableHead>Nombre</TableHead>
                      <TableHead>Responsable de Departamento</TableHead>
                      <TableHead className="text-right">Acciones</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredDepartamentos.map((dept) => (
                      <TableRow key={dept.id}>
                        <TableCell className="font-bold">{dept.codigo}</TableCell>
                        <TableCell className="text-primary font-semibold">
                          {dept.nombre}
                        </TableCell>
                        <TableCell>
                          {dept.responsable_nombre ? (
                            <div className="flex items-center gap-2 text-xs">
                              <User className="w-3 h-3 text-primary" />
                              {dept.responsable_nombre}
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
                                disabled={deletingId === dept.id}
                              >
                                <MoreHorizontal className="w-4 h-4" />
                              </Button>
                            </DropdownMenuTrigger>

                            <DropdownMenuContent align="end">
                              <DropdownMenuItem
                                className="cursor-pointer"
                                onSelect={(e) => {
                                  e.preventDefault();
                                  setEditingDepartamento(dept);
                                }}
                              >
                                <Edit2 className="w-4 h-4 mr-2" />
                                Editar departamento
                              </DropdownMenuItem>

                              <DropdownMenuItem
                                className="cursor-pointer text-destructive focus:text-destructive"
                                onClick={() => handleDeleteDepartamento(dept)}
                              >
                                <Trash2 className="w-4 h-4 mr-2" />
                                {deletingId === dept.id ? "Eliminando..." : "Eliminar"}
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}

                    {filteredDepartamentos.length === 0 && (
                      <TableRow>
                        <TableCell
                          colSpan={4}
                          className="text-center text-muted-foreground py-10"
                        >
                          No se encontraron departamentos.
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
      {editingDepartamento && (
        <AddDepartamentoDialog
          departamento={editingDepartamento}
          open={!!editingDepartamento}
          onOpenChange={(open) => {
            if (!open) setEditingDepartamento(null);
          }}
          onDepartamentoCreated={async () => {
            setEditingDepartamento(null);
            await loadDepartamentos();
          }}
        />
      )}
    </div>
  );
}
