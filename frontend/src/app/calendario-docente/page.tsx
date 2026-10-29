"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, RefreshCw, TriangleAlert, UsersRound } from "lucide-react";
import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { getCachedProfessor, getUserRole } from "@/lib/auth";
import {
  CalendarioDocente,
  getCalendarioProfesor,
  getProfesoresPlanificacion,
  ProfesorPlanificacion,
  regenerarPlanificacion,
} from "@/lib/planificacion-docente";
import { useDataSync, useLatestRequest } from "@/hooks/use-data-sync";
import { AvisosCalendario } from "./avisos-calendario";
import { formatearCursoAcademico } from "@/lib/curso-academico";

const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"];

function fechaLocal(valor: string) {
  return new Date(`${valor.slice(0, 10)}T12:00:00`);
}

function isoLocal(fecha: Date) {
  const anio = fecha.getFullYear();
  const mes = String(fecha.getMonth() + 1).padStart(2, "0");
  const dia = String(fecha.getDate()).padStart(2, "0");
  return `${anio}-${mes}-${dia}`;
}

function moverSemana(inicio: string, desplazamiento: number) {
  const fecha = fechaLocal(inicio);
  fecha.setDate(fecha.getDate() + desplazamiento * 7);
  return isoLocal(fecha);
}

function etiquetaFecha(valor: string) {
  return new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "short" }).format(fechaLocal(valor));
}

function etiquetaTipo(tipo: string) {
  return ({ GD: "Teoría", GT: "Grupo de trabajo", GL: "Laboratorio", GA: "Seminario" } as Record<string, string>)[tipo] || tipo;
}

function colorSesion(indice: number) {
  return [
    "border-sky-200 bg-sky-50 text-sky-950",
    "border-violet-200 bg-violet-50 text-violet-950",
    "border-emerald-200 bg-emerald-50 text-emerald-950",
    "border-amber-200 bg-amber-50 text-amber-950",
  ][indice % 4];
}

export default function CalendarioDocentePage() {
  const { toast } = useToast();
  const [profesores, setProfesores] = useState<ProfesorPlanificacion[]>([]);
  const [profesorId, setProfesorId] = useState<string>("");
  const [calendario, setCalendario] = useState<CalendarioDocente | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [regenerando, setRegenerando] = useState(false);
  const beginCalendarioRequest = useLatestRequest();
  const rol = getUserRole();
  const puedeRegenerar = rol === "Admin";
  const puedeElegirProfesor = ["Admin", "Responsable de departamento", "Responsable de área"].includes(rol);

  const cargarCalendario = useCallback(async (
    id: number,
    opciones: { cursoAcademico?: string; semana?: string } = {},
  ) => {
    const isCurrent = beginCalendarioRequest();
    if (isCurrent()) {
      setCargando(true);
      setError(null);
    }
    try {
      const siguienteCalendario = await getCalendarioProfesor(id, opciones);
      if (!isCurrent()) return;
      setCalendario(siguienteCalendario);
    } catch (causa) {
      if (!isCurrent()) return;
      setError(causa instanceof Error ? causa.message : "No se ha podido cargar el calendario docente.");
    } finally {
      if (isCurrent()) setCargando(false);
    }
  }, [beginCalendarioRequest]);

  useEffect(() => {
    let activo = true;
    async function inicializar() {
      try {
        const visibles = await getProfesoresPlanificacion();
        if (!activo) return;
        setProfesores(visibles);
        const propio = getCachedProfessor()?.id;
        const seleccionado = visibles.some((profesor) => profesor.id === propio) ? propio : visibles[0]?.id;
        if (!seleccionado) {
          setError("No hay profesorado visible para consultar su calendario.");
          setCargando(false);
          return;
        }
        setProfesorId(String(seleccionado));
        await cargarCalendario(seleccionado);
      } catch (causa) {
        if (activo) {
          setError(causa instanceof Error ? causa.message : "No se ha podido preparar la planificación.");
          setCargando(false);
        }
      }
    }
    void inicializar();
    return () => { activo = false; };
  }, [cargarCalendario]);

  // Una aprobación en otra pestaña debe verse al regresar al calendario,
  // conservando el profesor, el curso y la semana que se estaban consultando.
  useDataSync(async () => {
    if (!profesorId || regenerando) return;
    await cargarCalendario(Number(profesorId), {
      cursoAcademico: calendario?.curso_academico,
      semana: calendario?.semana_inicio,
    });
  });

  const fechas = useMemo(() => {
    if (!calendario) return [];
    const inicio = fechaLocal(calendario.semana_inicio);
    return DIAS.map((dia, indice) => {
      const fecha = new Date(inicio);
      fecha.setDate(inicio.getDate() + indice);
      const iso = isoLocal(fecha);
      const festivo = calendario.dias_no_lectivos.find((item) => item.fecha.slice(0, 10) === iso);
      return { dia, iso, fecha: etiquetaFecha(iso), festivo };
    });
  }, [calendario]);

  const franjas = useMemo(() => {
    const valores = new Set((calendario?.sesiones ?? []).map((sesion) => `${sesion.hora_inicio.slice(0, 5)}–${sesion.hora_fin.slice(0, 5)}`));
    return [...valores].sort((a, b) => a.localeCompare(b));
  }, [calendario]);
  const sesionesPorCelda = useMemo(() => {
    const sesiones = new Map<string, CalendarioDocente["sesiones"]>();
    for (const sesion of calendario?.sesiones ?? []) {
      const franja = `${sesion.hora_inicio.slice(0, 5)}–${sesion.hora_fin.slice(0, 5)}`;
      const clave = `${sesion.fecha.slice(0, 10)}|${franja}`;
      const existentes = sesiones.get(clave);
      if (existentes) existentes.push(sesion);
      else sesiones.set(clave, [sesion]);
    }
    return sesiones;
  }, [calendario?.sesiones]);
  const franjasVisibles = franjas.length > 0 ? franjas : (calendario?.dias_no_lectivos.length ? ["Todo el día"] : []);

  const cambiarProfesor = (id: string) => {
    setProfesorId(id);
    void cargarCalendario(Number(id));
  };
  const cambiarSemana = (direccion: number) => {
    if (!calendario || !profesorId) return;
    void cargarCalendario(Number(profesorId), {
      cursoAcademico: calendario.curso_academico,
      semana: moverSemana(calendario.semana_inicio, direccion),
    });
  };
  const cambiarCurso = (cursoAcademico: string) => {
    if (!profesorId) return;
    void cargarCalendario(Number(profesorId), { cursoAcademico });
  };
  const regenerar = async () => {
    setRegenerando(true);
    try {
      const resultado = await regenerarPlanificacion();
      toast({ title: "Planificación actualizada", description: `${resultado.actividades} actividades y ${resultado.sesiones} sesiones recalculadas.` });
      if (profesorId) await cargarCalendario(Number(profesorId), {
        cursoAcademico: calendario?.curso_academico,
        semana: calendario?.semana_inicio,
      });
    } catch (causa) {
      toast({ title: "No se pudo regenerar", description: causa instanceof Error ? causa.message : "Inténtalo de nuevo.", variant: "destructive" });
    } finally {
      setRegenerando(false);
    }
  };

  return (
    <div className="min-h-screen bg-muted/30">
      <Header />
      <Sidebar />
      <main className="px-4 pb-10 pt-24 lg:ml-64 lg:px-8">
        <div className="mx-auto max-w-7xl space-y-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <h1 className="flex items-center gap-2 text-2xl font-bold text-primary"><CalendarDays className="h-6 w-6" />Calendario docente semanal</h1>
              <p className="mt-1 text-sm text-muted-foreground">Horario oficial completo de las actividades adjudicadas, respetando días no lectivos.</p>
            </div>
            {puedeRegenerar && <Button variant="outline" onClick={() => void regenerar()} disabled={regenerando}>
              <RefreshCw className={`mr-2 h-4 w-4 ${regenerando ? "animate-spin" : ""}`} />{regenerando ? "Actualizando…" : "Regenerar planificación"}
            </Button>}
          </div>

          <Card className="border-none shadow-sm">
            <CardContent className="flex flex-col gap-3 pt-6 md:flex-row md:items-end md:justify-between">
              <div className="grid gap-3 sm:grid-cols-2">
                {(puedeElegirProfesor || profesores.length > 1) && <div className="min-w-64 space-y-1.5">
                  <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Profesor</label>
                  <Select value={profesorId} onValueChange={cambiarProfesor} disabled={cargando}>
                    <SelectTrigger><SelectValue placeholder="Selecciona un profesor" /></SelectTrigger>
                    <SelectContent>{profesores.map((profesor) => <SelectItem key={profesor.id} value={String(profesor.id)}>{profesor.apellidos}, {profesor.nombre}</SelectItem>)}</SelectContent>
                  </Select>
                </div>}
                <div className="min-w-40 space-y-1.5">
                  <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Curso</label>
                  <Select value={calendario?.curso_academico ?? ""} onValueChange={cambiarCurso} disabled={!calendario || cargando}>
                    <SelectTrigger><SelectValue placeholder="Curso" /></SelectTrigger>
                    <SelectContent>{(calendario?.cursos_disponibles ?? []).map((curso) => <SelectItem key={curso} value={curso}>{formatearCursoAcademico(curso)}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              </div>
              {calendario && <div className="flex items-center gap-2">
                <Button variant="outline" size="icon" onClick={() => cambiarSemana(-1)} aria-label="Semana anterior"><ChevronLeft className="h-4 w-4" /></Button>
                <span className="min-w-48 text-center text-sm font-medium">{etiquetaFecha(calendario.semana_inicio)} – {etiquetaFecha(calendario.semana_fin)}</span>
                <Button variant="outline" size="icon" onClick={() => cambiarSemana(1)} aria-label="Semana siguiente"><ChevronRight className="h-4 w-4" /></Button>
              </div>}
            </CardContent>
          </Card>

          {cargando && <div className="space-y-4"><Skeleton className="h-28" /><Skeleton className="h-96" /></div>}
          {!cargando && error && <Card><CardContent className="py-10 text-center"><TriangleAlert className="mx-auto mb-3 h-7 w-7 text-destructive" /><p className="text-sm text-destructive">{error}</p></CardContent></Card>}
          {!cargando && calendario && <>
            <Card className="border-none shadow-sm">
              <CardHeader className="pb-3"><CardTitle className="text-lg">{calendario.profesor.apellidos}, {calendario.profesor.nombre}</CardTitle><CardDescription>{calendario.profesor.categoria}{calendario.profesor.areas.length ? ` · ${calendario.profesor.areas.map((area) => area.codigo).join(", ")}` : ""}</CardDescription></CardHeader>
              <CardContent className="flex flex-wrap gap-2"><Badge variant="secondary">{calendario.sesiones.length} sesiones esta semana</Badge>{calendario.dias_no_lectivos.map((dia) => <Badge key={`${dia.fecha}-${dia.nombre}`} variant="outline" className="border-amber-300 bg-amber-50 text-amber-900">{etiquetaFecha(dia.fecha)} · {dia.nombre}</Badge>)}</CardContent>
            </Card>

            <Card className="border-none shadow-sm">
              <CardHeader><CardTitle className="text-lg">Horario de la semana</CardTitle><CardDescription>Cada bloque muestra el horario oficial de la actividad. Si la comparte con otros docentes, todos ven las mismas franjas; el reparto de semanas se acuerda después.</CardDescription></CardHeader>
              <CardContent className="overflow-x-auto">
                {franjasVisibles.length === 0 ? <div className="rounded-md border border-dashed py-12 text-center text-sm text-muted-foreground"><UsersRound className="mx-auto mb-2 h-5 w-5" />No hay sesiones planificadas para esta semana.</div> : <div className="min-w-[880px] overflow-hidden rounded-md border">
                  <div className="grid grid-cols-[100px_repeat(5,minmax(150px,1fr))] text-sm">
                    <div className="bg-muted p-3 font-medium">Hora</div>
                    {fechas.map(({ dia, fecha, festivo }) => <div key={dia} className={`p-3 text-center font-medium ${festivo ? "bg-red-100 text-red-950" : "bg-muted"}`}><p>{dia}</p><p className={`text-xs font-normal ${festivo ? "text-red-800" : "text-muted-foreground"}`}>{fecha}</p>{festivo && <p className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-red-800">Festivo</p>}</div>)}
                    {franjasVisibles.map((franja) => <div key={franja} className="contents">
                      <div className="border-t p-3 font-medium text-muted-foreground">{franja}</div>
                      {fechas.map(({ iso, festivo }, indice) => {
                        const sesiones = sesionesPorCelda.get(`${iso}|${franja}`) ?? [];
                        return <div key={`${franja}-${iso}`} className={`min-h-32 border-l border-t p-2 ${festivo ? "bg-red-50/80" : ""}`}>{festivo && sesiones.length === 0 && <p className="pt-8 text-center text-[11px] font-medium text-red-700">No lectivo</p>}{sesiones.map((sesion, orden) => <div key={sesion.id} className={`mb-2 rounded-md border p-2 text-xs ${colorSesion(indice + orden)}`}>
                          <p className="font-semibold leading-tight">{sesion.nombre_asignatura || sesion.codigo}</p>
                          <p className="mt-1">{etiquetaTipo(sesion.tipo)} · {sesion.grupo || `Grupo ${sesion.codigo_grupo}`}</p>
                          <p className="mt-1 opacity-80">{sesion.horas.toFixed(1)} h de clase · Actividad: {sesion.horas_actividad.toFixed(1)} h</p>
                          {sesion.es_horario_referencia && <p className="mt-1 font-medium opacity-80">Horario completo de la actividad · Adjudicadas: {(sesion.horas_adjudicadas ?? 0).toFixed(1)} h</p>}
                        </div>)}</div>;
                      })}
                    </div>)}
                  </div>
                </div>}
              </CardContent>
            </Card>

            <AvisosCalendario incidencias={calendario.incidencias} />
          </>}
        </div>
      </main>
    </div>
  );
}
