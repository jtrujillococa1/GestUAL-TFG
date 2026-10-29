"use client";

import { useState, useEffect } from "react";
import { useFieldArray, useForm } from "react-hook-form";
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
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { BookOpen, Plus, Trash2 } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { createActividad, updateActividad } from "@/lib/actividades";
import { getAreas } from "@/lib/areas";

const DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"];
const HORA_RE = /^([01]\d|2[0-3]):[0-5]\d$/;

const sesionSchema = z.object({
  dia: z.string().min(1, "Selecciona un día"),
  inicio: z.string().regex(HORA_RE, "Indica la hora de inicio"),
  fin: z.string().regex(HORA_RE, "Indica la hora de fin"),
  fecha: z.string().optional(),
}).refine(({ inicio, fin }) => inicio < fin, {
  message: "La hora de fin debe ser posterior a la de inicio",
  path: ["fin"],
}).refine(({ inicio, fin }) => inicio >= "08:00" && fin <= "22:00", {
  message: "Las clases deben estar entre las 08:00 y las 22:00",
  path: ["inicio"],
});

const actividadSchema = z.object({
  codigo: z.string().min(3, "Código obligatorio (mínimo 3 caracteres)"),
  nombre_asignatura: z.string().min(3, "Nombre de asignatura obligatorio"),
  tipo: z.string().min(1, "Tipo obligatorio"),
  codigo_grupo: z.string().min(1, "Código de grupo obligatorio"),
  grupo: z.string().min(1, "Identificador de grupo obligatorio"),
  idioma: z.string().min(1, "Idioma obligatorio"),
  duracion: z.string().min(1, "Duración obligatoria"),
  turno: z.string().min(1, "Turno obligatorio"),
  requiere_horario: z.boolean().default(true),
  sesiones: z.array(sesionSchema),
  sustituir_horario_detallado: z.boolean().default(false),
  horario_confirmado: z.boolean().default(true),
  fuente_horario: z.string().optional(),
  horas_asignatura: z.coerce.number().min(0, "Horas de asignatura deben ser >= 0"),
  horas_actividad: z.coerce.number().min(0.5, "Horas de actividad deben ser >= 0.5"),
  horas_area: z.coerce.number().min(0, "Horas de área deben ser >= 0"),
  area_ids: z.array(z.number()).min(1, "Selecciona al menos un área"),
  curso_academico: z.string().min(4, "Indica el curso académico"),
  tipo_estudio: z.string().optional(),
  codigo_plan: z.string().optional(),
  nombre_plan: z.string().optional(),
  codigo_centro: z.string().optional(),
  nombre_centro: z.string().optional(),
  ciclo: z.string().optional(),
  curso: z.string().optional(),
  caracter: z.string().optional(),
  actividad_oficial_id: z.string().optional(),
  nombre_actividad: z.string().optional(),
  codigo_grupo_oficial: z.string().optional(),
}).refine((actividad) => !actividad.requiere_horario || actividad.sesiones.length > 0, {
  message: "Añade al menos una sesión o indica que la actividad no tiene horario fijo",
  path: ["sesiones"],
});

type ActividadFormValues = z.infer<typeof actividadSchema>;

function extraerSesiones(horario?: string | null, dias?: string | null) {
  const sesiones: Array<{ dia: string; inicio: string; fin: string; fecha?: string }> = [];
  const explicitas = /([A-Za-zÁÉÍÓÚáéíóúÑñ]+)\s+(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})/g;
  for (const coincidencia of horario?.matchAll(explicitas) ?? []) {
    const dia = DIAS_SEMANA.find((valor) => valor.toLocaleLowerCase("es") === coincidencia[1].toLocaleLowerCase("es"));
    if (dia) sesiones.push({ dia, inicio: coincidencia[2].padStart(5, "0"), fin: coincidencia[3].padStart(5, "0"), fecha: "" });
  }
  if (sesiones.length) return sesiones;

  const franja = horario?.match(/(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})/);
  if (!franja) return [{ dia: "Lunes", inicio: "09:00", fin: "10:30", fecha: "" }];
  for (const valor of (dias ?? "").split(/[,;/·]/)) {
    const dia = DIAS_SEMANA.find((nombre) => nombre.toLocaleLowerCase("es").startsWith(valor.trim().toLocaleLowerCase("es").slice(0, 3)));
    if (dia) sesiones.push({ dia, inicio: franja[1].padStart(5, "0"), fin: franja[2].padStart(5, "0"), fecha: "" });
  }
  return sesiones.length ? sesiones : [{ dia: "Lunes", inicio: "09:00", fin: "10:30", fecha: "" }];
}

function repartirCuotas(areaIds: number[], horasTotales: number): Record<number, string> {
  if (areaIds.length === 0) return {};
  const base = Math.floor((horasTotales * 10) / areaIds.length) / 10;
  const resultado: Record<number, string> = {};
  areaIds.forEach((areaId, index) => {
    const horas = index === areaIds.length - 1
      ? Math.round((horasTotales - base * (areaIds.length - 1)) * 10) / 10
      : base;
    resultado[areaId] = String(horas);
  });
  return resultado;
}

function cuotasIniciales(actividad: any, areaIds: number[]): Record<number, string> {
  const cuotas = Array.isArray(actividad?.cuotas_por_area)
    ? actividad.cuotas_por_area as Array<{ area_id?: unknown; horas?: unknown }>
    : [] as Array<{ area_id?: unknown; horas?: unknown }>;
  const resultado: Record<number, string> = {};
  for (const cuota of cuotas) {
    const areaId = Number(cuota?.area_id);
    if (Number.isInteger(areaId) && areaId > 0) {
      resultado[areaId] = String(cuota.horas ?? "");
    }
  }

  if (Object.keys(resultado).length > 0) return resultado;

  const areaPrincipal = Number(actividad?.area_id);
  if (Number.isInteger(areaPrincipal) && areaPrincipal > 0) {
    return { [areaPrincipal]: String(actividad?.horas_area ?? 0) };
  }
  return repartirCuotas(areaIds, Number(actividad?.horas_actividad) || 0);
}

interface AddActividadDialogProps {
  onActividadCreated?: () => Promise<void> | void;
  actividad?: any;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export function AddActividadDialog({
  onActividadCreated,
  actividad,
  open: controlledOpen,
  onOpenChange: controlledOnOpenChange,
}: AddActividadDialogProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [areas, setAreas] = useState<any[]>([]);
  const [cuotasPorArea, setCuotasPorArea] = useState<Record<number, string>>({});
  const isEdit = !!actividad;

  const open = controlledOpen ?? internalOpen;
  const setOpen = controlledOnOpenChange ?? setInternalOpen;

  const form = useForm<ActividadFormValues>({
    resolver: zodResolver(actividadSchema),
    defaultValues: {
      codigo: "",
      nombre_asignatura: "",
      tipo: "GD",
      codigo_grupo: "1",
      grupo: "Grupo 1",
      idioma: "ES",
      duracion: "Anual",
      turno: "Mañana",
      requiere_horario: true,
      sesiones: [{ dia: "Lunes", inicio: "09:00", fin: "10:30", fecha: "" }],
      sustituir_horario_detallado: false,
      horario_confirmado: true,
      fuente_horario: "",
      horas_asignatura: 6,
      horas_actividad: 6,
      horas_area: 6,
      area_ids: [],
      curso_academico: "2026/2027",
      tipo_estudio: "",
      codigo_plan: "",
      nombre_plan: "",
      codigo_centro: "",
      nombre_centro: "",
      ciclo: "",
      curso: "",
      caracter: "",
      actividad_oficial_id: "",
      nombre_actividad: "",
      codigo_grupo_oficial: "",
    },
  });
  const { fields: sesiones, append: agregarSesion, remove: eliminarSesion } = useFieldArray({
    control: form.control,
    name: "sesiones",
  });
  const areasSeleccionadas = form.watch("area_ids");
  const horasActividad = form.watch("horas_actividad");
  const requiereHorario = form.watch("requiere_horario");

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
    return () => { active = false; };
  }, [open]);

  // Cargar datos de la actividad si estamos editando
  useEffect(() => {
    if (!open) return;

    if (isEdit && actividad) {
      const areaIds = actividad.area_ids ?? (actividad.area_id ? [actividad.area_id] : []);
      form.reset({
        codigo: actividad.codigo || "",
        nombre_asignatura: actividad.nombre_asignatura || actividad.codigo || "",
        tipo: actividad.tipo || "GD",
        codigo_grupo: actividad.codigo_grupo || "A",
        grupo: actividad.grupo || "A",
        idioma: actividad.idioma || "ES",
        duracion: actividad.duracion || "Anual",
        turno: actividad.turno || "Mañana",
        requiere_horario: actividad.requiere_horario ?? true,
        sesiones: extraerSesiones(actividad.horario, actividad.dias),
        sustituir_horario_detallado: false,
        horario_confirmado: actividad.horario_confirmado ?? true,
        fuente_horario: actividad.fuente_horario || "",
        horas_asignatura: actividad.horas_asignatura ?? 6,
        horas_actividad: actividad.horas_actividad ?? 6,
        horas_area: actividad.horas_area ?? 6,
        area_ids: areaIds,
        curso_academico: actividad.curso_academico || "2026/2027",
        tipo_estudio: actividad.tipo_estudio || "",
        codigo_plan: actividad.codigo_plan || "",
        nombre_plan: actividad.nombre_plan || "",
        codigo_centro: actividad.codigo_centro || "",
        nombre_centro: actividad.nombre_centro || "",
        ciclo: actividad.ciclo || "",
        curso: actividad.curso || "",
        caracter: actividad.caracter || "",
        actividad_oficial_id: actividad.actividad_oficial_id || "",
        nombre_actividad: actividad.nombre_actividad || "",
        codigo_grupo_oficial: actividad.codigo_grupo_oficial || "",
      });
      setCuotasPorArea(cuotasIniciales(actividad, areaIds));
    } else {
      form.reset({
        codigo: "",
        nombre_asignatura: "",
        tipo: "GD",
        codigo_grupo: "1",
        grupo: "Grupo 1",
        idioma: "ES",
        duracion: "Anual",
        turno: "Mañana",
        requiere_horario: true,
        sesiones: [{ dia: "Lunes", inicio: "09:00", fin: "10:30", fecha: "" }],
        sustituir_horario_detallado: false,
        horario_confirmado: true,
        fuente_horario: "",
        horas_asignatura: 6,
        horas_actividad: 6,
        horas_area: 6,
        area_ids: areas.length > 0 ? [areas[0].id] : [],
        curso_academico: "2026/2027",
        tipo_estudio: "",
        codigo_plan: "",
        nombre_plan: "",
        codigo_centro: "",
        nombre_centro: "",
        ciclo: "",
        curso: "",
        caracter: "",
        actividad_oficial_id: "",
        nombre_actividad: "",
        codigo_grupo_oficial: "",
      });
      setCuotasPorArea(repartirCuotas(areas.length > 0 ? [areas[0].id] : [], 6));
    }
  }, [open, isEdit, actividad, form, areas]);

  async function onSubmit(values: ActividadFormValues) {
    const dias = values.requiere_horario
      ? [...new Set(values.sesiones.map((sesion) => sesion.dia))].join(", ")
      : null;
    const horario = values.requiere_horario
      ? values.sesiones.map((sesion) => `${sesion.dia} ${sesion.inicio}-${sesion.fin}`).join(" | ")
      : null;
    const { sesiones: _sesiones, sustituir_horario_detallado, ...datosActividad } = values;
    const detalleManual = values.requiere_horario
      ? values.sesiones.map((sesion) => ({
          dia: sesion.dia,
          inicio: sesion.inicio,
          fin: sesion.fin,
          ...(sesion.fecha ? { fecha: sesion.fecha } : {}),
        }))
      : [];
    const conservaDetalleOficial = isEdit
      && !sustituir_horario_detallado
      && Array.isArray(actividad?.horario_detallado)
      && actividad.horario_detallado.length > 0;

    const cuotas = values.area_ids.map((areaId) => ({
      area_id: areaId,
      horas: Number(cuotasPorArea[areaId] ?? values.horas_area),
    }));
    const totalCuotas = Math.round(cuotas.reduce((total, cuota) => total + cuota.horas, 0) * 10) / 10;
    if (!isEdit && Math.abs(totalCuotas - values.horas_actividad) > 0.01) {
      toast({
        title: "Revisa las cuotas por área",
        description: "La suma de sus horas debe coincidir exactamente con las horas de actividad.",
        variant: "destructive",
      });
      return;
    }

    const areaPrincipalExistente = Number(actividad?.area_id);
    const areaPrincipal = isEdit && values.area_ids.includes(areaPrincipalExistente)
      ? areaPrincipalExistente
      : values.area_ids[0];
    const horasArea = Number(cuotasPorArea[areaPrincipal] ?? values.horas_area);
    const actividadManual = {
      ...datosActividad,
      // Una fila mantiene la cuota de su área principal. Las demás áreas son
      // asociaciones académicas compartidas para filtros y visibilidad.
      area_id: areaPrincipal,
      horas_area: horasArea,
      ...(!isEdit ? { cuotas_por_area: cuotas } : {}),
      dias,
      horario,
      horario_confirmado: values.requiere_horario
        ? (conservaDetalleOficial ? actividad.horario_confirmado : values.horario_confirmado)
        : false,
      origen_horario: values.requiere_horario
        ? (conservaDetalleOficial ? actividad.origen_horario : "MANUAL")
        : "NO_APLICA",
      horario_detallado: conservaDetalleOficial ? actividad.horario_detallado : detalleManual,
    };

    try {
      setSubmitting(true);

      if (isEdit && actividad) {
        await updateActividad(actividad.id, actividadManual);
        toast({
          title: "Actividad actualizada",
          description: `La actividad ${values.codigo} ha sido actualizada correctamente.`,
        });
      } else {
        await createActividad(actividadManual);
        toast({
          title: "Actividad creada",
          description: `La actividad ${values.codigo} ha sido creada correctamente.`,
        });
      }

      setOpen(false);
      form.reset();
      await onActividadCreated?.();
    } catch (err) {
      toast({
        title: isEdit ? "Error al actualizar actividad" : "Error al crear actividad",
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
          <BookOpen className="w-4 h-4 mr-2" />
          Nueva Actividad
        </Button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-[700px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Editar Actividad" : "Nueva Actividad"}</DialogTitle>
          <DialogDescription>
            Define los parámetros de la actividad docente.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 py-2">
            {/* Fila 1: Código, Tipo, Idioma */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <FormField
                control={form.control}
                name="codigo"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Código</FormLabel>
                    <FormControl>
                      <Input placeholder="PROG" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="tipo"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Tipo de actividad</FormLabel>
                    <FormControl><Input placeholder="GD, GT, GL…" {...field} /></FormControl>
                    <p className="text-[10px] text-muted-foreground">Introduce el código oficial; GD es teoría y GT prácticas.</p>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="idioma"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Idioma</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="ES">Español</SelectItem>
                        <SelectItem value="EN">Inglés</SelectItem>
                        <SelectItem value="CA">Catalán</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <FormField
                control={form.control}
                name="nombre_asignatura"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Asignatura</FormLabel>
                    <FormControl><Input placeholder="Programación" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="curso_academico"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Curso académico</FormLabel>
                    <FormControl><Input placeholder="2026/2027" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <details className="rounded-md border p-4">
              <summary className="cursor-pointer text-sm font-medium">Datos académicos oficiales (opcionales)</summary>
              <p className="mt-2 text-xs text-muted-foreground">
                Completa estos campos si proceden del plan docente oficial. No afectan al cálculo de la ordenación, pero se guardan para trazabilidad y exportación.
              </p>
              <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                {[
                  ["tipo_estudio", "Tipo de estudio", "Grado, Máster…"],
                  ["codigo_plan", "Código del plan", "GII-2024"],
                  ["nombre_plan", "Nombre del plan", "Grado en Ingeniería Informática"],
                  ["codigo_centro", "Código del centro", "ETSII"],
                  ["nombre_centro", "Nombre del centro", "Escuela Técnica Superior…"],
                  ["ciclo", "Ciclo", "Grado"],
                  ["curso", "Curso dentro del plan", "3º"],
                  ["caracter", "Carácter", "Obligatoria"],
                  ["actividad_oficial_id", "ID oficial de actividad", "Identificador institucional"],
                  ["nombre_actividad", "Nombre oficial de actividad", "Denominación institucional"],
                  ["codigo_grupo_oficial", "Código oficial de grupo", "T1"],
                  ["fuente_horario", "Enlace de la fuente horaria", "https://…"],
                ].map(([name, label, placeholder]) => (
                  <FormField
                    key={name}
                    control={form.control}
                    name={name as keyof ActividadFormValues}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{label}</FormLabel>
                        <FormControl><Input placeholder={placeholder} {...field} value={String(field.value ?? "")} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                ))}
              </div>
            </details>

            {/* Fila 2: Código Grupo, Grupo, Duración, Turno */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <FormField
                control={form.control}
                name="codigo_grupo"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Cód. Grupo</FormLabel>
                    <FormControl>
                      <Input placeholder="A" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="grupo"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Descripción</FormLabel>
                    <FormControl>
                      <Input placeholder="Teoría A" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="duracion"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Duración</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="Primer cuatrimestre">1er Cuatrimestre</SelectItem>
                        <SelectItem value="Segundo cuatrimestre">2º Cuatrimestre</SelectItem>
                        <SelectItem value="Anual">Anual</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="turno"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Turno</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="Mañana">Mañana</SelectItem>
                        <SelectItem value="Tarde">Tarde</SelectItem>
                        <SelectItem value="Noche">Noche</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <div className="space-y-3 rounded-md border p-4">
              <div>
                <p className="text-sm font-medium">Horario semanal del grupo</p>
                <p className="text-xs text-muted-foreground">Añade una fila por sesión entre las 08:00 y las 22:00. Las prácticas externas u otras actividades sin presencialidad fija se pueden registrar sin franja semanal.</p>
              </div>
              <FormField
                control={form.control}
                name="requiere_horario"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md bg-muted/50 p-3">
                    <FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl>
                    <div className="space-y-1 leading-none">
                      <FormLabel>Tiene horario presencial fijo</FormLabel>
                      <p className="text-xs text-muted-foreground">Desmárcalo para prácticas externas: mantendrá sus horas, pero no ocupará una franja ni generará solapes.</p>
                    </div>
                  </FormItem>
                )}
              />
              {requiereHorario ? <div className="space-y-3">
                {sesiones.map((sesion, index) => (
                  <div key={sesion.id} className="grid grid-cols-2 items-start gap-2 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.25fr)_auto]">
                    <FormField
                      control={form.control}
                      name={`sesiones.${index}.dia` as const}
                      render={({ field }) => (
                        <FormItem>
                          {index === 0 && <FormLabel>Día</FormLabel>}
                          <Select onValueChange={field.onChange} value={field.value}>
                            <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                            <SelectContent>{DIAS_SEMANA.map((dia) => <SelectItem key={dia} value={dia}>{dia}</SelectItem>)}</SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name={`sesiones.${index}.inicio` as const}
                      render={({ field }) => (
                        <FormItem>
                          {index === 0 && <FormLabel>Inicio</FormLabel>}
                          <FormControl><Input type="time" min="08:00" max="22:00" step="900" {...field} /></FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name={`sesiones.${index}.fin` as const}
                      render={({ field }) => (
                        <FormItem>
                          {index === 0 && <FormLabel>Fin</FormLabel>}
                          <FormControl><Input type="time" min="08:00" max="22:00" step="900" {...field} /></FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name={`sesiones.${index}.fecha` as const}
                      render={({ field }) => (
                        <FormItem>
                          {index === 0 && <FormLabel>Fecha (opcional)</FormLabel>}
                          <FormControl><Input type="date" {...field} value={field.value ?? ""} /></FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className={index === 0 ? "mt-6" : ""}
                      onClick={() => eliminarSesion(index)}
                      disabled={sesiones.length === 1}
                      aria-label="Eliminar sesión"
                    ><Trash2 className="h-4 w-4" /></Button>
                  </div>
                ))}
                <Button type="button" variant="outline" size="sm" onClick={() => agregarSesion({ dia: "Miércoles", inicio: "12:00", fin: "13:30", fecha: "" })}>
                  <Plus className="mr-2 h-4 w-4" />Añadir sesión
                </Button>
                {isEdit && Array.isArray(actividad?.horario_detallado) && actividad.horario_detallado.length > 0 && (
                  <FormField
                    control={form.control}
                    name="sustituir_horario_detallado"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md bg-sky-50 p-3">
                        <FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl>
                        <div className="space-y-1 leading-none">
                          <FormLabel>Sustituir las sesiones oficiales detalladas</FormLabel>
                          <p className="text-xs text-muted-foreground">Sin marcar, las fechas oficiales ya guardadas se conservan aunque actualices los demás datos.</p>
                        </div>
                      </FormItem>
                    )}
                  />
                )}
              </div> : (
                <div className="rounded-md border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900">
                  Se guardará como actividad sin horario fijo. Podrá seleccionarse durante la ordenación y aparecerá fuera de la cuadrícula semanal.
                </div>
              )}
              {requiereHorario && (
              <FormField
                control={form.control}
                name="horario_confirmado"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-start space-x-3 space-y-0">
                    <FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl>
                    <div className="space-y-1 leading-none">
                      <FormLabel>Horario confirmado</FormLabel>
                      <p className="text-xs text-muted-foreground">Los confirmados bloquean las combinaciones que se solapan; desmárcalo solo si es provisional.</p>
                    </div>
                  </FormItem>
                )}
              />
              )}
            </div>

            {/* Fila 3: Horas */}
            <div className="grid grid-cols-3 gap-4">
              <FormField
                control={form.control}
                name="horas_asignatura"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Horas Asignatura</FormLabel>
                    <FormControl>
                      <Input type="number" step="0.5" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="horas_actividad"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Horas Actividad</FormLabel>
                    <FormControl>
                      <Input type="number" step="0.5" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="horas_area"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Cuota de área inicial</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        step="0.1"
                        {...field}
                        onChange={(event) => {
                          field.onChange(event);
                          const areaCuotaEditable: number | undefined = isEdit
                            ? Number(actividad?.area_id)
                            : areasSeleccionadas.length === 1
                              ? areasSeleccionadas[0]
                              : undefined;
                          if (areaCuotaEditable !== undefined && Number.isInteger(areaCuotaEditable) && areaCuotaEditable > 0) {
                            setCuotasPorArea((actual) => ({ ...actual, [areaCuotaEditable]: event.target.value }));
                          }
                        }}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="area_ids"
              render={({ field }) => (
                <FormItem className="space-y-2 rounded-md border p-4">
                  <div>
                    <FormLabel>Áreas que imparten esta actividad</FormLabel>
                    <p className="text-xs text-muted-foreground">
                      {isEdit
                        ? "Esta edición modifica la cuota ya creada para su área."
                        : "Puedes asociar el mismo grupo a varias áreas; se crea una cuota independiente por área con este horario."}
                    </p>
                  </div>
                  {areas.map((area) => {
                    const checked = field.value.includes(area.id);
                    return (
                      <label key={area.id} className="flex cursor-pointer items-center gap-3 rounded px-1 py-1 text-sm hover:bg-muted">
                        <Checkbox
                          checked={checked}
                          disabled={isEdit}
                          onCheckedChange={(valor) => {
                            const siguiente = valor
                              ? [...field.value, area.id]
                              : field.value.filter((id) => id !== area.id);
                            field.onChange(siguiente);
                            setCuotasPorArea(repartirCuotas(siguiente, Number(horasActividad) || 0));
                          }}
                        />
                        <span>{area.codigo} · {area.nombre}</span>
                      </label>
                    );
                  })}
                  {!isEdit && areasSeleccionadas.length > 0 && (
                    <div className="mt-3 space-y-2 border-t pt-3">
                      <p className="text-xs font-medium">Cuota de ordenación por área</p>
                      <p className="text-xs text-muted-foreground">Estas cuotas se suman para formar las horas de actividad y cada una se ordena desde su propia área.</p>
                      {areasSeleccionadas.map((areaId) => {
                        const area = areas.find((item) => item.id === areaId);
                        return (
                          <label key={areaId} className="grid grid-cols-[1fr_110px] items-center gap-3 text-sm">
                            <span>{area?.codigo ?? `Área ${areaId}`} · {area?.nombre ?? ""}</span>
                            <Input
                              type="number"
                              min="0.1"
                              step="0.1"
                              value={cuotasPorArea[areaId] ?? ""}
                              onChange={(event) => setCuotasPorArea((actual) => ({ ...actual, [areaId]: event.target.value }))}
                              aria-label={`Horas de la cuota del área ${area?.codigo ?? areaId}`}
                            />
                          </label>
                        );
                      })}
                      <p className={`text-xs ${Math.abs(areasSeleccionadas.reduce((total, areaId) => total + Number(cuotasPorArea[areaId] ?? 0), 0) - Number(horasActividad || 0)) < 0.01 ? "text-emerald-700" : "text-destructive"}`}>
                        Total de cuotas: {areasSeleccionadas.reduce((total, areaId) => total + Number(cuotasPorArea[areaId] ?? 0), 0).toFixed(1)} h de {Number(horasActividad || 0).toFixed(1)} h
                      </p>
                    </div>
                  )}
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting
                  ? "Procesando..."
                  : isEdit
                  ? "Actualizar Actividad"
                  : "Crear Actividad"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
