import { useEffect, useMemo, useState } from "react";
import { apiFetch } from '@/lib/api-client';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { AlertCircle, CalendarDays, Clock3, FilterX, Plus, Search, SlidersHorizontal } from "lucide-react";
import { formatearHoras } from "@/lib/horas";

interface Opcion {
  opcion: {
    actividad_id?: number;
    codigo: string;
    nombre_asignatura?: string;
    codigo_grupo: string;
    tipo: string;
    grupo: string;
    horas: number;
    turno?: string;
    duracion?: string;
    idioma?: string;
    dias?: string;
    horario?: string;
    requiere_horario?: boolean;
  };
  horas_restantes: number;
  horas_maximas_actividad: number;
  categoria: string;
  riesgo_nivel: string;
  riesgo: number | null;
  riesgo_impacto?: number | null;
  riesgo_motivos?: string[];
  riesgo_desglose?: Record<string, number>;
  viable: boolean;
  motivo_no_viable?: string | null;
  bloqueada_por_solape?: boolean;
  prioridad_asignatura?: number | null;
}

interface OpcionesDisponiblesProps {
  nombreProfesor?: string | null;
  areaId?: number | null;
  opciones: Opcion[];
  loading: boolean;
  esMiTurno: boolean;
  bloqueada?: boolean;
  onAgregar: (opcion: Opcion) => void;
  cargandoMasOpciones?: boolean;
  errorCarga?: boolean;
  onReintentar?: () => void;
}

const DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"];

function SelectorHoras({ opcion, disabled, onAgregar, nombreProfesor, areaId }: { opcion: Opcion; disabled: boolean; onAgregar: (opcion: Opcion) => void; nombreProfesor?: string | null; areaId?: number | null }) {
  const maximo = opcion.opcion.horas;
  const [texto, setTexto] = useState(String(maximo));
  const normalizado = texto.replace(",", ".");
  const horas = Number(normalizado);
  const valido = /^\d+(\.\d)?$/.test(normalizado) && horas >= 0.1 && horas <= maximo;
  const [evaluada, setEvaluada] = useState<Opcion | null>(null);
  const [error, setError] = useState('');
  const actual = horas === maximo ? opcion : evaluada?.opcion.horas === horas ? evaluada : null;
  useEffect(() => {
    setEvaluada(null); setError('');
    if (!valido || horas === maximo || !nombreProfesor || !areaId) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const resultado = await apiFetch<Opcion>(`/evaluar-horas/${encodeURIComponent(nombreProfesor)}`, {
          method: 'POST', notifyDataChange: false, signal: controller.signal,
          body: { ...opcion.opcion, area_id: areaId, horas },
        });
        if (!controller.signal.aborted) setEvaluada(resultado);
      } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'No se pudo evaluar'); }
    }, 400);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [horas, maximo, valido, nombreProfesor, areaId, opcion]);
  const tonoRiesgo = actual?.riesgo_nivel === 'BAJO' ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : actual?.riesgo_nivel === 'MODERADO' ? 'border-amber-200 bg-amber-50 text-amber-900' : actual?.riesgo_nivel === 'PENDIENTE' ? 'border-slate-200 bg-slate-50 text-slate-700' : 'border-red-200 bg-red-50 text-red-900';
  return <div className="w-full space-y-3">
    <div className="flex flex-wrap items-end gap-3 rounded-lg bg-muted/20 p-3">
    <label className="text-xs font-semibold text-muted-foreground">
      Horas a elegir
      <Input type="number" inputMode="decimal" min="0.1" max={maximo} step="0.1"
        value={texto} onChange={(event) => setTexto(event.target.value)} disabled={disabled}
        aria-invalid={!valido} className="mt-1.5 h-10 w-28 bg-background text-base font-semibold text-foreground" />
    </label>
    <p className="min-w-32 flex-1 pb-1 text-xs leading-5 text-muted-foreground">Máximo seleccionable: <span className="font-semibold text-foreground">{formatearHoras(maximo)} h</span><br />Incrementos de 0,1 h</p>
    <Button className="h-10 gap-1.5 px-5" disabled={disabled || !valido || !actual?.viable} onClick={() => onAgregar({ ...opcion, opcion: { ...opcion.opcion, horas } })}>
      <Plus className="h-4 w-4" />Agregar
    </Button>
    </div>
    {!valido && <span className="text-xs text-destructive">Introduce de 0,1 a {formatearHoras(maximo)} h con un máximo de un decimal.</span>}
    {valido && !actual && !error && <span className="text-xs">Evaluando esta cantidad…</span>}
    {error && <span role="alert" className="text-xs text-destructive">{error}</span>}
    {valido && actual && <div className={`rounded-lg border p-3 text-xs leading-relaxed ${tonoRiesgo}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold">Estado del área tras elegir</span>
        <span className="font-semibold">{actual.riesgo_nivel === 'PENDIENTE' ? 'Pendiente de verificación' : `${actual.riesgo}/100 · ${actual.riesgo_nivel}`}</span>
      </div>
      <p className="mt-1">{formatearHoras(horas)} h evaluadas · Te quedarían <strong>{formatearHoras(actual.horas_restantes)} h</strong></p>
      <details className="mt-2 border-t border-current/15 pt-2">
        <summary className="cursor-pointer font-medium focus-visible:outline focus-visible:outline-2">Ver explicación del riesgo</summary>
        {actual.viable && <p className="mt-2">Viabilidad comprobada. {actual.riesgo_impacto == null ? 'Efecto no determinado.' : actual.riesgo_impacto > 0 ? `Esta elección aumenta la fragilidad en ${actual.riesgo_impacto} puntos.` : actual.riesgo_impacto < 0 ? `Esta elección reduce la fragilidad en ${Math.abs(actual.riesgo_impacto)} puntos.` : 'Esta elección mantiene la fragilidad del área.'}</p>}
        <p className="mt-1">{actual.viable ? actual.riesgo_motivos?.join(' ') : actual.motivo_no_viable}</p>
      </details>
    </div>}
  </div>;
}

function textoNormalizado(valor?: string): string {
  return String(valor ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es");
}

function opcionCoincideConDia(opcion: Opcion, dia: string): boolean {
  if (opcion.opcion.requiere_horario === false) return true;
  const horario = `${opcion.opcion.dias ?? ""} ${opcion.opcion.horario ?? ""}`;
  return textoNormalizado(horario).includes(textoNormalizado(dia));
}

export function OpcionesDisponibles({
  nombreProfesor,
  areaId,
  opciones,
  loading,
  esMiTurno,
  bloqueada = false,
  onAgregar,
  cargandoMasOpciones = false,
  errorCarga = false,
  onReintentar,
}: OpcionesDisponiblesProps) {
  const [textoBusqueda, setTextoBusqueda] = useState("");
  const [diasSeleccionados, setDiasSeleccionados] = useState<string[]>([]);
  const [turnoFiltro, setTurnoFiltro] = useState("todos");
  const [tipoFiltro, setTipoFiltro] = useState("todos");
  const [viabilidadFiltro, setViabilidadFiltro] = useState("viables");

  const turnosDisponibles = useMemo(
    () => Array.from(new Set(opciones.map((opcion) => opcion.opcion.turno).filter((turno): turno is string => Boolean(turno)))).sort(),
    [opciones],
  );
  const tiposDisponibles = useMemo(
    () => Array.from(new Set(opciones.map((opcion) => opcion.opcion.tipo).filter(Boolean))).sort(),
    [opciones],
  );
  const opcionesFiltradas = useMemo(() => {
    const busqueda = textoNormalizado(textoBusqueda);
    return opciones.filter((opcion) => {
      const textoOpcion = textoNormalizado([
        opcion.opcion.nombre_asignatura, opcion.opcion.grupo, opcion.opcion.tipo,
        opcion.opcion.codigo_grupo,
        // El código continúa siendo una ayuda de búsqueda, pero el nombre
        // determina el orden y el encabezado que ve el profesorado.
        opcion.opcion.codigo,
      ].filter(Boolean).join(" "));
      const coincideTexto = !busqueda || textoOpcion.includes(busqueda);
      const coincideDias = diasSeleccionados.length === 0 || diasSeleccionados.some((dia) => opcionCoincideConDia(opcion, dia));
      const coincideTurno = turnoFiltro === "todos" || opcion.opcion.turno === turnoFiltro;
      const coincideTipo = tipoFiltro === "todos" || opcion.opcion.tipo === tipoFiltro;
      const coincideViabilidad = viabilidadFiltro === "todas"
        || (viabilidadFiltro === "viables" && opcion.viable)
        || (viabilidadFiltro === "no-viables" && !opcion.viable);
      return coincideTexto && coincideDias && coincideTurno && coincideTipo && coincideViabilidad;
    });
  }, [opciones, textoBusqueda, diasSeleccionados, turnoFiltro, tipoFiltro, viabilidadFiltro]);

  const asignaturas = useMemo(() => {
    const opcionesPorAsignatura = opcionesFiltradas.reduce<Record<string, Opcion[]>>((grupos, opcion) => {
      const nombre = opcion.opcion.nombre_asignatura?.trim() || opcion.opcion.codigo;
      const clave = `${nombre}::${opcion.opcion.codigo}`;
      (grupos[clave] ??= []).push(opcion);
      return grupos;
    }, {});

    return Object.entries(opcionesPorAsignatura).sort(([, opcionesA], [, opcionesB]) => {
      const prioridadA = Math.min(...opcionesA.map((opcion) => opcion.prioridad_asignatura ?? Number.MAX_SAFE_INTEGER));
      const prioridadB = Math.min(...opcionesB.map((opcion) => opcion.prioridad_asignatura ?? Number.MAX_SAFE_INTEGER));
      if (prioridadA !== prioridadB) return prioridadA - prioridadB;
      const nombreA = opcionesA[0]?.opcion.nombre_asignatura || opcionesA[0]?.opcion.codigo || "";
      const nombreB = opcionesB[0]?.opcion.nombre_asignatura || opcionesB[0]?.opcion.codigo || "";
      return nombreA.localeCompare(nombreB, "es");
    });
  }, [opcionesFiltradas]);
  const hayFiltros = Boolean(textoBusqueda)
    || diasSeleccionados.length > 0
    || turnoFiltro !== "todos"
    || tipoFiltro !== "todos"
    || viabilidadFiltro !== "viables";
  const filtrosActivos = [
    Boolean(textoBusqueda),
    diasSeleccionados.length > 0,
    turnoFiltro !== "todos",
    tipoFiltro !== "todos",
    viabilidadFiltro !== "viables",
  ].filter(Boolean).length;

  const limpiarFiltros = () => {
    setTextoBusqueda("");
    setDiasSeleccionados([]);
    setTurnoFiltro("todos");
    setTipoFiltro("todos");
    setViabilidadFiltro("viables");
  };

  const alternarDia = (dia: string) => {
    setDiasSeleccionados((actuales) => actuales.includes(dia)
      ? actuales.filter((valor) => valor !== dia)
      : [...actuales, dia]);
  };

  const getRiesgoBadgeColor = (nivel: string) => {
    switch (nivel) {
      case "CRITICO": return "bg-red-200 text-red-800 border-red-300";
      case "ALTO":    return "bg-red-100 text-red-700 border-red-200";
      case "MODERADO": return "bg-amber-100 text-amber-700 border-amber-200";
      default:        return "bg-green-100 text-green-700 border-green-200";
    }
  };

  const getCategoriaColor = (categoria: string) => {
    switch (categoria) {
      case "COMPLETA_TURNO": return "bg-blue-100 text-blue-700 border-blue-200";
      case "CASI_COMPLETA":  return "bg-indigo-100 text-indigo-700 border-indigo-200";
      default:               return "bg-gray-100 text-gray-600 border-gray-200";
    }
  };

  const getTextoImpactoRiesgo = (impacto?: number) => {
    if (!impacto) return "sin cambios respecto al estado actual";
    return impacto > 0
      ? `+${impacto} frente al estado actual`
      : `${impacto} frente al estado actual`;
  };

  const getTipoActividad = (tipo: string) => {
    const tipos: Record<string, string> = {
      GD: "Teoría (grupo docente)",
      GT: "Grupo de trabajo",
      GL: "Laboratorio",
      GA: "Seminario",
      T: "Teoría",
      P: "Grupo de trabajo",
      L: "Laboratorio",
      S: "Seminario",
    };
    return tipos[tipo] ?? tipo;
  };

  const getHorario = (opcion: Opcion) => {
    if (opcion.opcion.requiere_horario === false) return "Sin horario fijo · no genera solapes";
    const { dias, horario, turno } = opcion.opcion;
    // Evitar «Viernes · Viernes 17:00...» si la franja ya incluye los días.
    const diasEnHorario = dias && horario && textoNormalizado(dias).split(/[,;·|]/).every(dia => textoNormalizado(horario).includes(dia.trim()));
    const partes = [diasEnHorario ? null : dias, horario, turno].filter(Boolean);
    return partes.length > 0 ? partes.join(" · ") : "Horario pendiente de definir";
  };

  return (
    <Card className="border-none shadow-sm">
      <CardHeader>
        <CardTitle>Opciones disponibles</CardTitle>
        <CardDescription>
          {loading
            ? "Cargando opciones..."
            : `${asignaturas.length} asignaturas · ${opcionesFiltradas.length} de ${opciones.length} opciones · ${viabilidadFiltro === 'viables' ? 'Solo viables' : viabilidadFiltro === 'todas' ? 'Viables y no viables' : 'Solo no viables'}`}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {cargandoMasOpciones && <p role="status" className="mb-3 text-sm text-muted-foreground">Completando automáticamente el catálogo… {opciones.length} opciones evaluadas. Los filtros se actualizarán al terminar.</p>}
        {errorCarga && <div role="alert" className="mb-3 rounded border border-destructive p-3 text-sm">No se ha podido cargar el catálogo completo. La lista puede estar incompleta. <Button variant="outline" size="sm" onClick={onReintentar} disabled={bloqueada}>Reintentar carga</Button></div>}
        {esMiTurno && (
          <div className="mb-4 flex items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">Personaliza la lista por disponibilidad y preferencias.</p>
            <Popover>
              <PopoverTrigger asChild>
                <Button variant={hayFiltros ? "default" : "outline"} size="sm" className="shrink-0">
                  <SlidersHorizontal className="mr-2 h-4 w-4" />
                  Filtrar
                  {filtrosActivos > 0 && <Badge className="ml-2 h-5 min-w-5 justify-center bg-white/20 px-1 text-inherit hover:bg-white/20">{filtrosActivos}</Badge>}
                </Button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-[min(92vw,34rem)] p-4">
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div>
                    <p className="flex items-center gap-2 text-sm font-semibold text-primary"><SlidersHorizontal className="h-4 w-4" /> Filtrar opciones</p>
                    <p className="mt-1 text-xs text-muted-foreground">Los filtros no cambian la viabilidad ni las opciones de la ordenación.</p>
                  </div>
                  {hayFiltros && <Button variant="ghost" size="sm" onClick={limpiarFiltros} className="h-8 shrink-0 text-xs"><FilterX className="mr-1 h-3.5 w-3.5" /> Limpiar</Button>}
                </div>

                <div className="space-y-4">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input value={textoBusqueda} onChange={(event) => setTextoBusqueda(event.target.value)} placeholder="Buscar por nombre de asignatura o grupo" className="h-10 pl-9" />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <Select value={turnoFiltro} onValueChange={setTurnoFiltro}>
                      <SelectTrigger className="h-9"><SelectValue placeholder="Turno" /></SelectTrigger>
                      <SelectContent><SelectItem value="todos">Todos los turnos</SelectItem>{turnosDisponibles.map((turno) => <SelectItem key={turno} value={turno}>{turno}</SelectItem>)}</SelectContent>
                    </Select>
                    <Select value={tipoFiltro} onValueChange={setTipoFiltro}>
                      <SelectTrigger className="h-9"><SelectValue placeholder="Tipo" /></SelectTrigger>
                      <SelectContent><SelectItem value="todos">Todos los tipos</SelectItem>{tiposDisponibles.map((tipo) => <SelectItem key={tipo} value={tipo}>{getTipoActividad(tipo)}</SelectItem>)}</SelectContent>
                    </Select>
                    <Select value={viabilidadFiltro} onValueChange={setViabilidadFiltro}>
                      <SelectTrigger className="h-9"><SelectValue placeholder="Viabilidad" /></SelectTrigger>
                      <SelectContent><SelectItem value="todas">Viables y no viables</SelectItem><SelectItem value="viables">Solo viables</SelectItem><SelectItem value="no-viables">Solo no viables</SelectItem></SelectContent>
                    </Select>
                  </div>
                  <div>
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Días de preferencia</p>
                      <p className="text-xs text-muted-foreground">Coincide con cualquiera de los elegidos</p>
                    </div>
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                      {DIAS_SEMANA.map((dia) => (
                        <Button key={dia} type="button" variant={diasSeleccionados.includes(dia) ? "default" : "outline"} onClick={() => alternarDia(dia)} className="h-10 justify-start px-3 text-sm">
                          {dia}
                        </Button>
                      ))}
                    </div>
                  </div>
                </div>
              </PopoverContent>
            </Popover>
          </div>
        )}
        {loading ? (
          <div className="text-center py-8 text-muted-foreground">Cargando...</div>
        ) : opciones.length === 0 ? (
          <div className="text-center py-8">
            <AlertCircle className="w-12 h-12 text-muted-foreground mx-auto mb-2" />
            <p className="text-muted-foreground">No hay opciones disponibles</p>
          </div>
        ) : opcionesFiltradas.length === 0 ? (
          <div className="rounded-lg border border-dashed py-10 text-center">
            <AlertCircle className="mx-auto mb-2 h-9 w-9 text-muted-foreground" />
            <p className="font-medium">No hay opciones con estos filtros</p>
            <p className="mt-1 text-sm text-muted-foreground">En Filtrar puedes incluir las opciones no viables y consultar por qué no se pueden elegir.</p>
            {hayFiltros && <Button variant="outline" size="sm" onClick={limpiarFiltros} className="mt-3">Restablecer filtros</Button>}
          </div>
        ) : (
          <>
            <Accordion type="multiple" className="max-h-[600px] overflow-y-auto rounded-lg border px-4">
              {asignaturas.map(([clave, opcionesAsignatura]) => {
              const primeraOpcion = opcionesAsignatura[0]?.opcion;
              const prioridadAsignatura = opcionesAsignatura[0]?.prioridad_asignatura;
              const nombreAsignatura = primeraOpcion?.nombre_asignatura || primeraOpcion?.codigo || "Asignatura";
              return <AccordionItem key={clave} value={clave}>
                <AccordionTrigger className="hover:no-underline">
                  <span className="flex items-center gap-3 text-left">
                    <span>
                      <span className="block font-semibold">{nombreAsignatura}</span>
                      {primeraOpcion?.nombre_asignatura && <span className="block text-xs font-normal text-muted-foreground">Código {primeraOpcion.codigo}</span>}
                    </span>
                    <span className="text-sm font-normal text-muted-foreground">
                      {opcionesAsignatura.length} {opcionesAsignatura.length === 1 ? "opción" : "opciones"}
                    </span>
                    {prioridadAsignatura && <Badge variant="outline" className="border-primary/30 bg-primary/5 text-xs text-primary">Prioridad {prioridadAsignatura}</Badge>}
                  </span>
                </AccordionTrigger>
                <AccordionContent className="space-y-3">
                  {opcionesAsignatura.map((opcion) => (
                    <div
                      key={opcion.opcion.actividad_id ?? `${opcion.opcion.codigo}-${opcion.opcion.codigo_grupo}-${opcion.opcion.tipo}`}
                      className={`rounded-xl border p-4 shadow-sm ${opcion.viable ? "border-border bg-slate-50 dark:bg-background" : "border-destructive/30 bg-destructive/5"}`}
                    >
                      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                        <div className="space-y-2">
                          <div>
                            <h3 className="font-semibold">{opcion.opcion.grupo}</h3>
                            <p className="text-sm text-muted-foreground">
                              Grupo {opcion.opcion.codigo_grupo} · {getTipoActividad(opcion.opcion.tipo)}
                            </p>
                          </div>
                          <div className="space-y-1 text-sm text-muted-foreground">
                            <p className="flex items-center gap-2">
                              <Clock3 className="h-4 w-4 shrink-0" />
                              {getHorario(opcion)}
                            </p>
                            {opcion.opcion.duracion && (
                              <p className="flex items-center gap-2">
                                <CalendarDays className="h-4 w-4 shrink-0" />
                                {opcion.opcion.duracion === '1Q' ? 'Primer cuatrimestre' : opcion.opcion.duracion === '2Q' ? 'Segundo cuatrimestre' : opcion.opcion.duracion}
                              </p>
                            )}
                          </div>
                        </div>
                        <div className="flex gap-1 flex-wrap sm:justify-end">
                          {opcion.viable && <Badge variant="outline" className={getCategoriaColor(opcion.categoria)}>
                            {opcion.categoria}
                          </Badge>}
                          {!opcion.viable && opcion.horas_maximas_actividad > 0 && (
                            <Badge variant="outline" className={getRiesgoBadgeColor(opcion.riesgo_nivel)}>
                              {opcion.riesgo_nivel === 'PENDIENTE' ? 'Pendiente de verificación' : `Riesgo ${opcion.riesgo}/100 · ${opcion.riesgo_nivel}`}
                            </Badge>
                          )}
                          {!opcion.viable && (
                            <Badge variant={opcion.riesgo_nivel === 'PENDIENTE' ? 'outline' : 'destructive'}>{opcion.riesgo_nivel === 'PENDIENTE' ? 'Resultado no concluyente' : 'No viable'}</Badge>
                          )}
                        </div>
                      </div>

                      <div className="mt-3 space-y-3 border-t pt-3">
                        <div className="text-sm">
                          {opcion.horas_maximas_actividad <= 0 ? (
                            <span className="font-semibold text-destructive">Cuota cubierta · 0 h disponibles</span>
                          ) : <>
                            <span className="text-xs text-muted-foreground">Horas disponibles en esta actividad: <strong className="text-foreground">{formatearHoras(opcion.horas_maximas_actividad)} h</strong></span>
                          </>}
                          {!opcion.viable && (
                            <p className="mt-1 text-xs text-destructive">
                              {opcion.motivo_no_viable ?? "Esta combinación no es viable."}
                            </p>
                          )}
                        </div>
                        {opcion.viable ? <SelectorHoras key={`${opcion.opcion.actividad_id}-${opcion.opcion.horas}-${opcion.horas_restantes}`} opcion={opcion} nombreProfesor={nombreProfesor} areaId={areaId} disabled={!esMiTurno || bloqueada} onAgregar={onAgregar} /> : <Button size="sm" disabled>{opcion.riesgo_nivel === 'PENDIENTE' ? 'Pendiente de verificación' : 'No viable'}</Button>}
                      </div>
                    </div>
                  ))}
                </AccordionContent>
              </AccordionItem>;
              })}
            </Accordion>
          </>
        )}
      </CardContent>
    </Card>
  );
}
