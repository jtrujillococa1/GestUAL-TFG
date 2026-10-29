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
import { Building2 } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { createDepartamento, updateDepartamento } from "@/lib/departamentos";
import { getProfesores } from "@/lib/profesores";
import { getCuentasResponsables } from "@/lib/usuarios";
import { CrearResponsable } from '@/components/crear-responsable';

const departamentoSchema = z.object({
  codigo: z.string().min(2, "Código obligatorio (mínimo 2 caracteres)"),
  nombre: z.string().min(3, "Nombre obligatorio (mínimo 3 caracteres)"),
  responsable_departamento_id: z.coerce.number().nullable().optional(),
});

type DepartamentoFormValues = z.infer<typeof departamentoSchema>;

interface AddDepartamentoDialogProps {
  onDepartamentoCreated?: () => Promise<void> | void;
  departamento?: any;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export function AddDepartamentoDialog({
  onDepartamentoCreated,
  departamento,
  open: controlledOpen,
  onOpenChange: controlledOnOpenChange,
}: AddDepartamentoDialogProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [profesores, setProfesores] = useState<any[]>([]);
  const [cuentasResponsables, setCuentasResponsables] = useState<any[]>([]);
  const isEdit = !!departamento;

  const open = controlledOpen ?? internalOpen;
  const setOpen = controlledOnOpenChange ?? setInternalOpen;

  const form = useForm<DepartamentoFormValues>({
    resolver: zodResolver(departamentoSchema),
    defaultValues: {
      codigo: "",
      nombre: "",
      responsable_departamento_id: null,
    },
  });

  // Cargar profesores
  useEffect(() => {
    if (!open) return;
    let active = true;
    Promise.all([getProfesores(), getCuentasResponsables()])
      .then(([datos, cuentas]) => {
        if (active) {
          setProfesores(datos);
          setCuentasResponsables(cuentas.filter((cuenta) => cuenta.rol === "responsable_departamento"));
        }
      })
      .catch((err) => {
        if (active) {
          console.error("Error al cargar profesores:", err);
          toast({
            title: "Error al cargar profesores",
            description: "No se pudieron cargar los profesores disponibles",
            variant: "destructive",
          });
        }
      });
    return () => { active = false; };
  }, [open]);

  // Cargar datos del departamento si estamos editando
  useEffect(() => {
    if (!open) return;

    if (isEdit && departamento) {
      form.reset({
        codigo: departamento.codigo || "",
        nombre: departamento.nombre || "",
        responsable_departamento_id: departamento.responsable_departamento_id || null,
      });
    } else {
      form.reset({
        codigo: "",
        nombre: "",
        responsable_departamento_id: null,
      });
    }
  }, [open, isEdit, departamento, form]);

  async function onSubmit(values: DepartamentoFormValues) {
    try {
      setSubmitting(true);

      if (isEdit && departamento) {
        await updateDepartamento(departamento.id, values);
        toast({
          title: "Departamento actualizado",
          description: `El departamento ${values.nombre} ha sido actualizado correctamente.`,
        });
      } else {
        await createDepartamento(values);
        toast({
          title: "Departamento creado",
          description: `El departamento ${values.nombre} ha sido creado correctamente.`,
        });
      }

      setOpen(false);
      form.reset();
      await onDepartamentoCreated?.();
    } catch (err) {
      toast({
        title: isEdit ? "Error al actualizar departamento" : "Error al crear departamento",
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
          <Building2 className="w-4 h-4 mr-2" />
          Nuevo Departamento
        </Button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "Editar Departamento" : "Nuevo Departamento"}
          </DialogTitle>
          <DialogDescription>
            Define el departamento universitario.
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
                      <Input placeholder="INF" {...field} />
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
                      <Input placeholder="Informática" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {/* Responsable de Departamento (opcional) */}
            <FormField
              control={form.control}
              name="responsable_departamento_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Cuenta responsable de departamento (opcional)</FormLabel>
                  <CrearResponsable rol="responsable_departamento" nombre={form.watch('nombre')} onCreated={(cuenta) => { setCuentasResponsables(actuales => [...actuales, cuenta]); form.setValue('responsable_departamento_id', cuenta.id); }} />
                  <Select
                    onValueChange={(value) => {
                      // Radix puede emitir un valor vacío al incorporar una
                      // cuenta creada sincrónicamente al formulario.
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
                  <p className="text-[10px] text-muted-foreground">Si eliges un docente, se crea automáticamente una cuenta institucional independiente para el departamento.</p>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting
                  ? "Guardando..."
                  : isEdit
                  ? "Actualizar Departamento"
                  : "Crear Departamento"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
