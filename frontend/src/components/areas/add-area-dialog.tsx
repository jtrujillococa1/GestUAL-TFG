"use client";

import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Layers } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { createArea, updateArea } from "@/lib/areas";
import { getDepartamentos } from "@/lib/departamentos";
import { getProfesores } from "@/lib/profesores";
import { getCuentasResponsables } from "@/lib/usuarios";
import { CrearResponsable } from '@/components/crear-responsable';

const areaSchema = z.object({
  codigo: z.string().min(2, "Código obligatorio (mínimo 2 caracteres)"),
  nombre: z.string().min(3, "Nombre obligatorio (mínimo 3 caracteres)"),
  departamento_id: z.coerce.number().min(1, "Debe seleccionar un departamento"),
  responsable_area_id: z.coerce.number().nullable().optional(),
});

type AreaFormValues = z.infer<typeof areaSchema>;

interface AddAreaDialogProps {
  onAreaCreated?: () => Promise<void> | void;
  area?: any;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export function AddAreaDialog({
  onAreaCreated,
  area,
  open: controlledOpen,
  onOpenChange: controlledOnOpenChange,
}: AddAreaDialogProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [departamentos, setDepartamentos] = useState<any[]>([]);
  const [profesores, setProfesores] = useState<any[]>([]);
  const [cuentasResponsables, setCuentasResponsables] = useState<any[]>([]);
  const isEdit = !!area;

  const open = controlledOpen ?? internalOpen;
  const setOpen = controlledOnOpenChange ?? setInternalOpen;

  const form = useForm<AreaFormValues>({
    resolver: zodResolver(areaSchema),
    defaultValues: {
      codigo: "",
      nombre: "",
      departamento_id: 1,
      responsable_area_id: null,
    },
  });

  // Cargar departamentos y profesores
  useEffect(() => {
    if (!open) return;
    let active = true;
    Promise.all([getDepartamentos(), getProfesores(), getCuentasResponsables()])
      .then(([depts, profs, cuentas]) => {
        if (active) {
          setDepartamentos(depts);
          setProfesores(profs);
          setCuentasResponsables(cuentas.filter((cuenta) => cuenta.rol === "responsable_area"));
        }
      })
      .catch((err) => {
        if (active) {
          console.error("Error al cargar datos:", err);
          toast({
            title: "Error al cargar datos",
            description: "No se pudieron cargar los departamentos o profesores",
            variant: "destructive",
          });
        }
      });
    return () => { active = false; };
  }, [open]);

  // Cargar datos del área si estamos editando
  useEffect(() => {
    if (!open) return;

    if (isEdit && area) {
      form.reset({
        codigo: area.codigo || "",
        nombre: area.nombre || "",
        departamento_id: area.departamento_id || 1,
        responsable_area_id: area.responsable_area_id || null,
      });
    } else {
      form.reset({
        codigo: "",
        nombre: "",
        departamento_id: departamentos.length > 0 ? departamentos[0].id : 1,
        responsable_area_id: null,
      });
    }
  }, [open, isEdit, area, form, departamentos]);

  async function onSubmit(values: AreaFormValues) {
    try {
      setSubmitting(true);

      if (isEdit && area) {
        await updateArea(area.id, values);
        toast({
          title: "Área actualizada",
          description: `El área ${values.nombre} ha sido actualizada correctamente.`,
        });
      } else {
        await createArea(values);
        toast({
          title: "Área creada",
          description: `El área ${values.nombre} ha sido creada correctamente.`,
        });
      }

      setOpen(false);
      form.reset();
      await onAreaCreated?.();
    } catch (err) {
      toast({
        title: isEdit ? "Error al actualizar área" : "Error al crear área",
        description: err instanceof Error ? err.message : "Ha ocurrido un error inesperado.",
        variant: "destructive",
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !submitting && setOpen(v)}>
      <DialogTrigger asChild>
        <Button>
          <Layers className="w-4 h-4 mr-2" />
          Nueva Área
        </Button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Editar Área" : "Nueva Área"}</DialogTitle>
          <DialogDescription>
            Define el área de conocimiento y su departamento.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 py-2">
            {/* Código y Nombre */}
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="codigo"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Código</FormLabel>
                    <FormControl>
                      <Input placeholder="ATC" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="nombre"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Nombre</FormLabel>
                    <FormControl>
                      <Input placeholder="Arquitectura de Computadores" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {/* Departamento */}
            <FormField
              control={form.control}
              name="departamento_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Departamento</FormLabel>
                  <Select
                    onValueChange={(value) => {
                      const id = Number(value);
                      if (value && Number.isInteger(id) && id > 0) field.onChange(id);
                    }}
                    value={field.value?.toString()}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Seleccionar departamento" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {departamentos.map((dept) => (
                        <SelectItem key={dept.id} value={dept.id.toString()}>
                          {dept.codigo} - {dept.nombre}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Responsable de Área (opcional) */}
            <CrearResponsable rol="responsable_area" nombre={form.watch('nombre')} onCreated={(cuenta) => { setCuentasResponsables(actuales => [...actuales, cuenta]); form.setValue('responsable_area_id', cuenta.id); }} />
            <FormField
              control={form.control}
              name="responsable_area_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Cuenta responsable de área (opcional)</FormLabel>
                  <Select
                    onValueChange={(value) => {
                      if (!value) return;
                      const id = Number(value);
                      if (value === "null") field.onChange(null);
                      else if (Number.isInteger(id) && id > 0) field.onChange(id);
                    }}
                    value={field.value?.toString() || "null"}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Sin responsable" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="null">Sin responsable</SelectItem>
                      {cuentasResponsables.map((cuenta) => (
                        <SelectItem key={cuenta.id} value={cuenta.id.toString()}>
                          {cuenta.nombre} · {cuenta.apellidos}
                        </SelectItem>
                      ))}
                      {profesores.filter((prof) => prof.usuario_id).map((prof) => (
                        <SelectItem key={prof.id} value={prof.usuario_id.toString()}>
                          {prof.nombre} {prof.apellidos} · crear cuenta responsable
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-[10px] text-muted-foreground">Si eliges un docente, se crea automáticamente una cuenta institucional independiente para el área.</p>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? "Guardando..." : isEdit ? "Actualizar Área" : "Crear Área"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
