"use client";

import { useState, useEffect, useMemo } from "react";
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
import { Checkbox } from "@/components/ui/checkbox";
import { ArrowDown, ArrowUp, ListOrdered, UserPlus, X } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import {
  createProfesor,
  createProfesorConCuenta,
  updateProfesor,
} from "@/lib/profesores";
import { getAreas } from "@/lib/areas";
import { getActividades, type ApiActividad } from "@/lib/actividades";
import { getUserRole } from "@/lib/auth";

const profesorSchema = z.object({
  crear_cuenta: z.boolean().default(false),
  email: z.string().trim().email("Correo no válido").or(z.literal("")),
  password: z.string().min(12, "La contraseña debe tener al menos 12 caracteres").or(z.literal("")),
  rol: z.enum(["profesor", "psi"]),
  nombre: z.string().min(2, "El nombre es obligatorio"),
  apellidos: z.string().min(2, "Los apellidos son obligatorios"),
  categoria: z.string().min(1, "La categoría es obligatoria"),
  fecha_ingreso: z.string().min(1, "La fecha de ingreso es obligatoria"),
  carga_docente: z.coerce.number().min(0, "Carga no válida"),
  disponibilidad_cuatrimestre: z.enum(["PRIMERO", "SEGUNDO", "AMBOS"]),
  area_ids: z.array(z.number()).min(1, "Debe seleccionar al menos un área"),
  horas_objetivo_por_area: z.record(z.string(), z.coerce.number().min(0, "Las horas no pueden ser negativas")).default({}),
  es_psi: z.boolean().default(false),
  prioridades_asignaturas: z.array(z.string()).default([]),
}).superRefine((values, ctx) => {
  if (values.crear_cuenta) {
    if (!values.email) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["email"], message: "El correo es obligatorio" });
    }
    if (!values.password) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["password"], message: "Indica una contraseña temporal" });
    }
    if (values.es_psi !== (values.rol === "psi")) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["rol"], message: "El rol debe coincidir con la condición PSI" });
    }
  }
  const totalPorAreas = values.area_ids.reduce(
    (acumulado, areaId) => acumulado + Number(values.horas_objetivo_por_area[String(areaId)] ?? 0),
    0,
  );
  if (Math.abs(totalPorAreas - values.carga_docente) > 0.01) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["horas_objetivo_por_area"],
      message: "La suma de las horas por área debe coincidir con la carga objetivo total.",
    });
  }
});

type ProfesorFormValues = z.infer<typeof profesorSchema>;

interface AddProfesorDialogProps {
  onProfesorCreated?: () => Promise<void> | void;
  profesor?: any;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

function repartirCargaEntreAreas(areaIds: number[], cargaDocente: number): Record<string, number> {
  if (!areaIds.length) return {};
  const carga = Math.max(0, Number(cargaDocente) || 0);
  const parte = Math.floor((carga / areaIds.length) * 10) / 10;
  const resultado: Record<string, number> = {};
  areaIds.forEach((areaId, indice) => {
    resultado[String(areaId)] = indice === areaIds.length - 1
      ? Number((carga - parte * (areaIds.length - 1)).toFixed(1))
      : parte;
  });
  return resultado;
}

export function AddProfesorDialog({
  onProfesorCreated,
  profesor,
  open: controlledOpen,
  onOpenChange: controlledOnOpenChange,
}: AddProfesorDialogProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [areas, setAreas] = useState<any[]>([]);
  const [asignaturas, setAsignaturas] = useState<ApiActividad[]>([]);
  const isEdit = !!profesor;

  const open = controlledOpen ?? internalOpen;
  const setOpen = controlledOnOpenChange ?? setInternalOpen;

  const form = useForm<ProfesorFormValues>({
    resolver: zodResolver(profesorSchema),
    defaultValues: {
      crear_cuenta: false,
      email: "",
      password: "",
      rol: "profesor",
      nombre: "",
      apellidos: "",
      categoria: "TU",
      fecha_ingreso: new Date().toISOString().split("T")[0],
      carga_docente: 0,
      disponibilidad_cuatrimestre: "AMBOS",
      area_ids: [],
      horas_objetivo_por_area: {},
      es_psi: false,
      prioridades_asignaturas: [],
    },
  });
  const crearCuenta = form.watch("crear_cuenta");
  const puedeCrearCuenta = !isEdit && ["Admin", "Responsable de área", "Responsable de departamento"].includes(getUserRole() ?? "");

  // Cargar áreas cuando se abre el diálogo
  useEffect(() => {
    if (!open) return;
    let active = true;
    getAreas()
      .then((datos) => {
        if (active) setAreas(datos);
      })
      .catch((err) => {
        if (active) {
          console.error("Error al cargar áreas:", err);
          toast({
            title: "Error al cargar áreas",
            description: "No se pudieron cargar las áreas disponibles",
            variant: "destructive",
          });
        }
      });
    getActividades()
      .then((datos) => { if (active) setAsignaturas(datos); })
      .catch(() => {
        // El alta sigue siendo posible sin cargar sugerencias. La validación
        // definitiva se hace en el servidor al guardar las prioridades.
        if (active) setAsignaturas([]);
      });
    return () => { active = false; };
  }, [open]);

  // Cargar datos del profesor si estamos editando
  useEffect(() => {
    if (!open) return;

    if (isEdit && profesor) {
      form.reset({
        crear_cuenta: false,
        email: "",
        password: "",
        rol: profesor.es_psi ? "psi" : "profesor",
        nombre: profesor.firstName || profesor.nombre || "",
        apellidos: profesor.lastName || profesor.apellidos || "",
        categoria: profesor.categoria || "TU",
        fecha_ingreso: profesor.fecha_ingreso || new Date().toISOString().split("T")[0],
        carga_docente: profesor.carga_docente ?? 0,
        disponibilidad_cuatrimestre: profesor.disponibilidad_cuatrimestre ?? "AMBOS",
        area_ids: profesor.area_ids ?? (profesor.area_id ? [profesor.area_id] : []),
        horas_objetivo_por_area: profesor.horas_objetivo_por_area
          ?? repartirCargaEntreAreas(
            profesor.area_ids ?? (profesor.area_id ? [profesor.area_id] : []),
            profesor.carga_docente ?? 0,
          ),
        es_psi: profesor.es_psi || false,
        prioridades_asignaturas: (profesor.prioridades_asignaturas ?? []).map((item: { codigo: string }) => item.codigo),
      });
    } else {
      form.reset({
        crear_cuenta: ["Admin", "Responsable de área", "Responsable de departamento"].includes(getUserRole() ?? ""),
        email: "",
        password: "",
        rol: "profesor",
        nombre: "",
        apellidos: "",
        categoria: "TU",
        fecha_ingreso: new Date().toISOString().split("T")[0],
        carga_docente: 0,
        disponibilidad_cuatrimestre: "AMBOS",
        area_ids: areas.length > 0 ? [areas[0].id] : [],
        horas_objetivo_por_area: areas.length > 0 ? { [String(areas[0].id)]: 0 } : {},
        es_psi: false,
        prioridades_asignaturas: [],
      });
    }
  }, [open, isEdit, profesor, form, areas]);

  const areaIdsSeleccionadas = form.watch("area_ids");
  const categoriaSeleccionada = form.watch("categoria");
  useEffect(() => {
    if (categoriaSeleccionada?.trim().toUpperCase() === "PSI") {
      form.setValue("es_psi", true);
      form.setValue("rol", "psi");
    }
  }, [categoriaSeleccionada, form]);
  const prioridadesAsignaturas = form.watch("prioridades_asignaturas");
  const asignaturasPriorizables = useMemo(() => {
    const areasSeleccionadas = new Set(areaIdsSeleccionadas);
    const porCodigo = new Map<string, ApiActividad>();
    asignaturas.forEach((actividad) => {
      const actividadAreas = actividad.area_ids ?? (actividad.area_id ? [actividad.area_id] : []);
      if (actividadAreas.some((areaId) => areasSeleccionadas.has(areaId)) && !porCodigo.has(actividad.codigo)) {
        porCodigo.set(actividad.codigo, actividad);
      }
    });
    return [...porCodigo.values()].sort((a, b) =>
      (a.nombre_asignatura || a.codigo).localeCompare(b.nombre_asignatura || b.codigo, "es"),
    );
  }, [asignaturas, areaIdsSeleccionadas]);
  const asignaturaPorCodigo = useMemo(
    () => new Map(asignaturasPriorizables.map((actividad) => [actividad.codigo, actividad])),
    [asignaturasPriorizables],
  );

  const actualizarPrioridades = (siguientes: string[]) => {
    form.setValue("prioridades_asignaturas", [...new Set(siguientes)], { shouldDirty: true });
  };

  async function onSubmit(values: ProfesorFormValues) {
    try {
      setSubmitting(true);

      const perfil = {
        nombre: values.nombre,
        apellidos: values.apellidos,
        categoria: values.categoria,
        fecha_ingreso: values.fecha_ingreso,
        carga_docente: values.carga_docente,
        area_id: values.area_ids.includes(Number(profesor?.area_id))
          ? Number(profesor.area_id)
          : values.area_ids[0],
        area_ids: values.area_ids,
        horas_objetivo_por_area: Object.fromEntries(
          values.area_ids.map((areaId) => [
            areaId,
            Number(values.horas_objetivo_por_area[String(areaId)] ?? 0),
          ]),
        ),
        es_psi: values.es_psi,
        disponibilidad_cuatrimestre: values.disponibilidad_cuatrimestre,
        prioridades_asignaturas: values.prioridades_asignaturas,
      };

      if (isEdit && profesor) {
        await updateProfesor(profesor.id, perfil);
        toast({
          title: "Profesor actualizado",
          description: `${values.nombre} ${values.apellidos} ha sido actualizado correctamente.`,
        });
      } else if (values.crear_cuenta) {
        await createProfesorConCuenta({
          ...perfil,
          email: values.email,
          password: values.password,
          rol: values.rol,
        });
        toast({
          title: "Profesor y cuenta creados",
          description: `Se ha creado el perfil y la cuenta de ${values.nombre} ${values.apellidos}.`,
        });
      } else {
        await createProfesor(perfil);
        toast({
          title: "Profesor creado",
          description: `${values.nombre} ${values.apellidos} ha sido creado correctamente.`,
        });
      }

      setOpen(false);
      form.reset();
      await onProfesorCreated?.();
    } catch (err) {
      toast({
        title: isEdit ? "Error al actualizar profesor" : "Error al crear profesor",
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
          <UserPlus className="w-4 h-4 mr-2" />
          Añadir Profesor
        </Button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-[500px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Editar Profesor" : "Nuevo Profesor"}</DialogTitle>
          <DialogDescription>
            Completa los datos del docente.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 py-2">
            {/* Nombre y Apellidos */}
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="nombre"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Nombre</FormLabel>
                    <FormControl>
                      <Input placeholder="Ana" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="apellidos"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Apellidos</FormLabel>
                    <FormControl>
                      <Input placeholder="García López" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {!isEdit && puedeCrearCuenta && (
              <FormField
                control={form.control}
                name="crear_cuenta"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
                    <FormControl>
                      <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                    </FormControl>
                    <div className="space-y-1 leading-none">
                      <FormLabel>Crear cuenta de acceso</FormLabel>
                      <p className="text-[10px] text-muted-foreground">
                        Crea la cuenta y el perfil docente juntos, sin usar identificadores internos.
                      </p>
                    </div>
                  </FormItem>
                )}
              />
            )}

            {!isEdit && crearCuenta && (
              <div className="space-y-4 rounded-md border border-primary/20 bg-muted/30 p-4">
                <p className="text-sm font-medium">Credenciales iniciales</p>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="email"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Correo institucional</FormLabel>
                        <FormControl><Input type="email" autoComplete="off" placeholder="nombre@universidad.es" {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Contraseña temporal</FormLabel>
                        <FormControl><Input type="password" autoComplete="new-password" placeholder="Mínimo 12 caracteres" {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <FormField
                  control={form.control}
                  name="rol"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Rol de acceso</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                        <SelectContent>
                          <SelectItem value="profesor">Profesor</SelectItem>
                          <SelectItem value="psi">PSI</SelectItem>
                        </SelectContent>
                      </Select>
                      <p className="text-[10px] text-muted-foreground">Las responsabilidades se asignan mediante una cuenta institucional distinta de esta cuenta docente.</p>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            )}

            {!isEdit && !puedeCrearCuenta && (
              <p className="rounded-md bg-muted p-3 text-xs text-muted-foreground">
                Este perfil se crea sin cuenta. Solo el administrador puede crear cuentas de acceso.
              </p>
            )}

            {/* Categoría y Fecha Ingreso */}
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="categoria"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Categoría docente</FormLabel>
                    <FormControl><Input list="categorias-docentes" placeholder="TU, AYD, Asociado…" {...field} /></FormControl>
                    <datalist id="categorias-docentes">
                      <option value="CU">Catedrático/a de Universidad</option>
                      <option value="TU">Titular de Universidad</option>
                      <option value="CD">Contratado/a Doctor/a</option>
                      <option value="AYD">Ayudante Doctor/a</option>
                      <option value="AY">Ayudante</option>
                      <option value="AS">Asociado/a</option>
                      <option value="PSI">Profesor Sustituto Interino</option>
                    </datalist>
                    <p className="text-[10px] text-muted-foreground">Puedes escribir cualquier código o denominación oficial de la universidad.</p>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="fecha_ingreso"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Fecha Ingreso</FormLabel>
                    <FormControl>
                      <Input type="date" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {/* Carga Docente */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="carga_docente"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Carga Objetivo (h)</FormLabel>
                    <FormControl>
                      <Input type="number" step="0.1" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="disponibilidad_cuatrimestre"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Disponibilidad docente</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                      <SelectContent>
                        <SelectItem value="AMBOS">Ambos cuatrimestres</SelectItem>
                        <SelectItem value="PRIMERO">Solo primer cuatrimestre</SelectItem>
                        <SelectItem value="SEGUNDO">Solo segundo cuatrimestre</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-[10px] text-muted-foreground">Fuera de este periodo las actividades se mostrarán como no viables.</p>
                    <FormMessage />
                  </FormItem>
                )}
              />

            </div>

            <FormField
              control={form.control}
              name="area_ids"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Áreas de pertenencia</FormLabel>
                  <p className="text-xs text-muted-foreground">
                    Selecciona todas las áreas en las que el profesor puede participar y elegir docencia.
                  </p>
                  <div className="max-h-40 space-y-2 overflow-y-auto rounded-md border p-3">
                    {areas.map((area) => {
                      const seleccionada = field.value.includes(area.id);
                      return (
                        <label key={area.id} className="flex cursor-pointer items-center gap-2 text-sm">
                          <Checkbox
                            checked={seleccionada}
                            onCheckedChange={(checked) => {
                              const siguientesAreas = checked === true
                                ? [...field.value, area.id]
                                : field.value.filter((id) => id !== area.id);
                              field.onChange(siguientesAreas);
                              form.setValue(
                                "horas_objetivo_por_area",
                                repartirCargaEntreAreas(siguientesAreas, form.getValues("carga_docente")),
                                { shouldValidate: true },
                              );
                            }}
                          />
                          <span>{area.codigo} - {area.nombre}</span>
                        </label>
                      );
                    })}
                    {areas.length === 0 && <p className="text-sm text-muted-foreground">No hay áreas disponibles.</p>}
                  </div>
                  <FormMessage />
                </FormItem>
              )}
            />

            {form.watch("area_ids").length > 0 && (
              <FormField
                control={form.control}
                name="horas_objetivo_por_area"
                render={() => (
                  <FormItem className="space-y-3 rounded-md border border-primary/20 bg-muted/30 p-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <FormLabel>Distribución de la carga por área</FormLabel>
                        <p className="text-xs text-muted-foreground">
                          Define qué parte de la carga total se ordenará en cada área. Las áreas con 0 h son solo de pertenencia y no crean turno.
                        </p>
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => form.setValue(
                          "horas_objetivo_por_area",
                          repartirCargaEntreAreas(form.getValues("area_ids"), form.getValues("carga_docente")),
                          { shouldValidate: true },
                        )}
                      >
                        Repartir por igual
                      </Button>
                    </div>
                    <div className="space-y-2">
                      {form.watch("area_ids").map((areaId) => {
                        const area = areas.find((item) => item.id === areaId);
                        return (
                          <FormField
                            key={areaId}
                            control={form.control}
                            name={`horas_objetivo_por_area.${areaId}`}
                            render={({ field }) => (
                              <FormItem className="grid grid-cols-[1fr_112px] items-center gap-3">
                                <FormLabel className="font-normal">{area ? `${area.codigo} · ${area.nombre}` : `Área ${areaId}`}</FormLabel>
                                <FormControl><Input type="number" min="0" step="0.5" aria-label={`Horas en ${area?.codigo ?? areaId}`} {...field} /></FormControl>
                              </FormItem>
                            )}
                          />
                        );
                      })}
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            <div className="space-y-3 rounded-md border border-primary/20 bg-muted/20 p-4">
              <div className="flex items-start gap-2">
                <ListOrdered className="mt-0.5 h-4 w-4 text-primary" />
                <div>
                  <FormLabel>Prioridad de asignaturas</FormLabel>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Indica las asignaturas que mejor conoce el docente. La primera tendrá mayor prioridad en la ordenación y en posibles propuestas de conflicto. Las no listadas quedarán después.
                  </p>
                </div>
              </div>
              <Select
                value=""
                onValueChange={(codigo) => actualizarPrioridades([...prioridadesAsignaturas, codigo])}
                disabled={asignaturasPriorizables.length === 0}
              >
                <SelectTrigger><SelectValue placeholder={asignaturasPriorizables.length ? "Añadir asignatura prioritaria" : "Selecciona primero un área"} /></SelectTrigger>
                <SelectContent>
                  {asignaturasPriorizables.filter((actividad) => !prioridadesAsignaturas.includes(actividad.codigo)).map((actividad) => (
                    <SelectItem key={actividad.codigo} value={actividad.codigo}>
                      {actividad.nombre_asignatura || actividad.codigo} · {actividad.codigo}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {prioridadesAsignaturas.length > 0 ? (
                <ol className="space-y-2">
                  {prioridadesAsignaturas.map((codigo, indice) => {
                    const actividad = asignaturaPorCodigo.get(codigo);
                    return <li key={codigo} className="flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm">
                      <span className="w-5 font-semibold text-primary">{indice + 1}</span>
                      <span className="min-w-0 flex-1 truncate">{actividad?.nombre_asignatura || codigo}<span className="ml-1 text-xs text-muted-foreground">· {codigo}</span></span>
                      <Button type="button" size="icon" variant="ghost" className="h-7 w-7" disabled={indice === 0} onClick={() => {
                        const siguiente = [...prioridadesAsignaturas]; [siguiente[indice - 1], siguiente[indice]] = [siguiente[indice], siguiente[indice - 1]]; actualizarPrioridades(siguiente);
                      }} aria-label="Subir prioridad"><ArrowUp className="h-3.5 w-3.5" /></Button>
                      <Button type="button" size="icon" variant="ghost" className="h-7 w-7" disabled={indice === prioridadesAsignaturas.length - 1} onClick={() => {
                        const siguiente = [...prioridadesAsignaturas]; [siguiente[indice], siguiente[indice + 1]] = [siguiente[indice + 1], siguiente[indice]]; actualizarPrioridades(siguiente);
                      }} aria-label="Bajar prioridad"><ArrowDown className="h-3.5 w-3.5" /></Button>
                      <Button type="button" size="icon" variant="ghost" className="h-7 w-7 text-destructive hover:text-destructive" onClick={() => actualizarPrioridades(prioridadesAsignaturas.filter((item) => item !== codigo))} aria-label="Quitar prioridad"><X className="h-3.5 w-3.5" /></Button>
                    </li>;
                  })}
                </ol>
              ) : <p className="text-xs text-muted-foreground">No hay prioridades declaradas todavía.</p>}
            </div>

            {/* Checkbox PSI */}
            <FormField
              control={form.control}
              name="es_psi"
              render={({ field }) => (
                <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={(checked) => {
                        const esPsi = checked === true;
                        field.onChange(esPsi);
                        if (esPsi) form.setValue("rol", "psi");
                        if (!esPsi && form.getValues("rol") === "psi") {
                          form.setValue("rol", "profesor");
                        }
                      }}
                    />
                  </FormControl>
                  <div className="space-y-1 leading-none">
                    <FormLabel>Es Profesor Sustituto Interino (PSI)</FormLabel>
                    <p className="text-[10px] text-muted-foreground">
                      Los PSI tienen turno y prioridad; únicamente un gestor puede realizar su elección.
                    </p>
                  </div>
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting
                  ? "Guardando..."
                  : isEdit
                  ? "Actualizar Profesor"
                  : "Crear Profesor"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
