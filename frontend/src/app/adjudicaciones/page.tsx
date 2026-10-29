"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { BookOpenCheck, FileSpreadsheet, FileText, Filter, RotateCcw, Search, UsersRound, X } from "lucide-react";
import {
  ActividadAdjudicada,
  AdjudicacionesResponse,
  descargarAdjudicacionesConfirmadas,
  devolverAdjudicacion,
  getAdjudicacionesConfirmadas,
  getLabelTipoActividad,
} from "@/lib/actividades";
import { useDataSync, useLatestRequest } from "@/hooks/use-data-sync";
import { canManageArea } from "@/lib/auth";
import { useToast } from "@/hooks/use-toast";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

function nombreDocente(docente: ActividadAdjudicada["docentes"][number]) {
  return `${docente.apellidos}, ${docente.nombre}`;
}

function normalizarBusqueda(valor: string) {
  return valor.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es");
}

export default function AdjudicacionesPage() {
  const [datos, setDatos] = useState<AdjudicacionesResponse | null>(null);
  const [busqueda, setBusqueda] = useState("");
  const [areaFilter, setAreaFilter] = useState("all");
  const [profesorFilter, setProfesorFilter] = useState("all");
  const [tipoFilter, setTipoFilter] = useState("all");
  const [coberturaFilter, setCoberturaFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [formatoDescarga, setFormatoDescarga] = useState<"xlsx" | "pdf" | null>(null);
  const [revision, setRevision] = useState<{
    actividad: ActividadAdjudicada;
    docente: ActividadAdjudicada["docentes"][number];
  } | null>(null);
  const [motivoRevision, setMotivoRevision] = useState("");
  const [devolviendo, setDevolviendo] = useState(false);
  const { toast } = useToast();
  const beginLoad = useLatestRequest();
  const hasLoaded = useRef(false);

  const cargar = useCallback(async () => {
    const isCurrent = beginLoad();
    if (!hasLoaded.current) setLoading(true);
    if (isCurrent()) setError(null);
    try {
      const respuesta = await getAdjudicacionesConfirmadas();
      if (!isCurrent()) return;
      setDatos(respuesta);
      hasLoaded.current = true;
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "No se han podido cargar las adjudicaciones.");
    } finally {
      if (isCurrent()) setLoading(false);
    }
  }, [beginLoad]);

  useEffect(() => { void cargar(); }, [cargar]);
  useDataSync(cargar);

  const opcionesFiltro = useMemo(() => {
    const areas = new Map<number, { id: number; etiqueta: string }>();
    const profesores = new Map<number, { id: number; etiqueta: string }>();

    for (const actividad of datos?.actividades ?? []) {
      if (actividad.area_id) {
        const etiquetaArea = [actividad.area_codigo, actividad.area_nombre].filter(Boolean).join(" · ") || "Área sin nombre";
        areas.set(actividad.area_id, { id: actividad.area_id, etiqueta: etiquetaArea });
      }
      for (const docente of actividad.docentes) {
        profesores.set(docente.profesor_id, { id: docente.profesor_id, etiqueta: nombreDocente(docente) });
      }
    }

    return {
      areas: [...areas.values()].sort((primera, segunda) => primera.etiqueta.localeCompare(segunda.etiqueta, "es")),
      profesores: [...profesores.values()].sort((primero, segundo) => primero.etiqueta.localeCompare(segundo.etiqueta, "es")),
      tipos: [...new Set((datos?.actividades ?? []).map((actividad) => actividad.tipo).filter(Boolean))].sort(),
    };
  }, [datos]);

  const actividades = useMemo(() => {
    const texto = normalizarBusqueda(busqueda.trim());
    return (datos?.actividades ?? []).filter((actividad) => {
      const contenido = normalizarBusqueda([
        actividad.nombre_asignatura, actividad.codigo, actividad.grupo, actividad.codigo_grupo,
        actividad.area_codigo, actividad.area_nombre, actividad.tipo,
        ...actividad.docentes.flatMap((docente) => [nombreDocente(docente), docente.categoria]),
      ].filter(Boolean).join(" "));
      const coincideBusqueda = !texto || contenido.includes(texto);
      const coincideArea = areaFilter === "all" || String(actividad.area_id) === areaFilter;
      const coincideProfesor = profesorFilter === "all" || actividad.docentes.some((docente) => String(docente.profesor_id) === profesorFilter);
      const coincideTipo = tipoFilter === "all" || actividad.tipo === tipoFilter;
      const completa = actividad.horas_pendientes <= 0.01;
      const coincideCobertura = coberturaFilter === "all"
        || (coberturaFilter === "completa" && completa)
        || (coberturaFilter === "parcial" && !completa);

      return coincideBusqueda && coincideArea && coincideProfesor && coincideTipo && coincideCobertura;
    });
  }, [areaFilter, busqueda, coberturaFilter, datos, profesorFilter, tipoFilter]);

  const filtrosActivos = [areaFilter, profesorFilter, tipoFilter, coberturaFilter].filter((filtro) => filtro !== "all").length;
  const hayCriterios = filtrosActivos > 0 || Boolean(busqueda.trim());
  const limpiarCriterios = () => {
    setBusqueda("");
    setAreaFilter("all");
    setProfesorFilter("all");
    setTipoFilter("all");
    setCoberturaFilter("all");
  };

  const resumen = useMemo(() => ({
    actividades: datos?.actividades.length ?? 0,
    cubiertas: (datos?.actividades ?? []).filter((actividad) => actividad.horas_pendientes <= 0.01).length,
    docentes: new Set((datos?.actividades ?? []).flatMap((actividad) => actividad.docentes.map((docente) => docente.profesor_id))).size,
  }), [datos]);

  const esVistaPropia = datos?.visibilidad === "PROPIA";
  const puedeRevisar = canManageArea();

  const descargar = async (formato: "xlsx" | "pdf") => {
    setFormatoDescarga(formato);
    try {
      await descargarAdjudicacionesConfirmadas(formato);
      toast({ title: `Exportación ${formato.toUpperCase()} preparada`, description: "Incluye únicamente adjudicaciones confirmadas de tu ámbito." });
    } catch (err) {
      toast({ title: "No se pudo generar la exportación", description: err instanceof Error ? err.message : "Inténtalo de nuevo.", variant: "destructive" });
    } finally {
      setFormatoDescarga(null);
    }
  };

  const confirmarDevolucion = async () => {
    if (!revision || !revision.actividad.area_id || motivoRevision.trim().length < 3) return;
    setDevolviendo(true);
    try {
      const resultado = await devolverAdjudicacion(
        revision.actividad.id,
        revision.docente.profesor_id,
        revision.actividad.area_id,
        motivoRevision.trim(),
      );
      toast({
        title: "Adjudicación devuelta a revisión",
        description: `${resultado.profesor} pasa a tener el turno prioritario para corregir ${resultado.actividad}.${resultado.reabierta ? " El área se ha reabierto." : ""}`,
      });
      setRevision(null);
      setMotivoRevision("");
      await cargar();
    } catch (err) {
      toast({ title: "No se pudo devolver la adjudicación", description: err instanceof Error ? err.message : "Inténtalo de nuevo.", variant: "destructive" });
    } finally {
      setDevolviendo(false);
    }
  };

  return (
    <div className="min-h-screen">
      <Header />
      <Sidebar />
      <main className="lg:pl-64 pt-16">
        <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-8">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-primary md:text-3xl">
                {esVistaPropia ? "Mis adjudicaciones" : "Adjudicaciones confirmadas"}
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {esVistaPropia
                  ? "Consulta los grupos y horas que tienes confirmados."
                  : "Consulta qué docentes han quedado asignados a cada actividad."}
                {" "}Los borradores no se muestran aquí.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" size="sm" className="gap-2" disabled={formatoDescarga !== null} onClick={() => void descargar("xlsx")}><FileSpreadsheet className="h-4 w-4" />{formatoDescarga === "xlsx" ? "Generando…" : "Excel"}</Button>
              <Button variant="outline" size="sm" className="gap-2" disabled={formatoDescarga !== null} onClick={() => void descargar("pdf")}><FileText className="h-4 w-4" />{formatoDescarga === "pdf" ? "Generando…" : "PDF"}</Button>
              <Badge variant="outline" className="w-fit gap-2 px-3 py-1.5 text-xs text-primary">
                <BookOpenCheck className="h-4 w-4" /> Solo adjudicaciones confirmadas
              </Badge>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <Card className="border-none shadow-sm"><CardContent className="pt-6"><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Actividades visibles</p><p className="mt-1 text-2xl font-bold text-primary">{resumen.actividades}</p></CardContent></Card>
            <Card className="border-none shadow-sm"><CardContent className="pt-6"><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Cuotas cubiertas</p><p className="mt-1 text-2xl font-bold text-emerald-700">{resumen.cubiertas}</p></CardContent></Card>
            <Card className="border-none shadow-sm"><CardContent className="pt-6"><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Docentes con adjudicación</p><p className="mt-1 text-2xl font-bold text-primary">{resumen.docentes}</p></CardContent></Card>
          </div>

          <Card className="border-none shadow-sm">
            <CardHeader className="gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <CardTitle className="text-lg">Actividad y profesorado</CardTitle>
                <CardDescription>Las horas se muestran sobre la cuota de la actividad dentro de su área.</CardDescription>
              </div>
              <div className="flex w-full flex-col gap-2 sm:flex-row md:w-auto">
                <div className="relative w-full sm:w-80">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={busqueda}
                    onChange={(event) => setBusqueda(event.target.value)}
                    className="pl-9"
                    placeholder="Buscar por asignatura, grupo o profesor"
                    aria-label="Buscar adjudicaciones"
                  />
                </div>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button variant="outline" className="gap-2 whitespace-nowrap">
                      <Filter className="h-4 w-4" /> Filtros{filtrosActivos > 0 ? ` (${filtrosActivos})` : ""}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent align="end" className="w-[min(24rem,calc(100vw-2rem))] p-4">
                    <div className="space-y-4">
                      <div>
                        <p className="text-sm font-semibold text-primary">Filtrar adjudicaciones</p>
                        <p className="mt-1 text-xs text-muted-foreground">Combina filtros para localizar rápidamente una línea que revisar.</p>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div className="space-y-1.5">
                          <Label htmlFor="filtro-area" className="text-xs">Área</Label>
                          <Select value={areaFilter} onValueChange={setAreaFilter}>
                            <SelectTrigger id="filtro-area" className="h-9 text-xs"><SelectValue placeholder="Todas las áreas" /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">Todas las áreas</SelectItem>
                              {opcionesFiltro.areas.map((area) => <SelectItem key={area.id} value={String(area.id)}>{area.etiqueta}</SelectItem>)}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-1.5">
                          <Label htmlFor="filtro-profesor" className="text-xs">Profesor</Label>
                          <Select value={profesorFilter} onValueChange={setProfesorFilter}>
                            <SelectTrigger id="filtro-profesor" className="h-9 text-xs"><SelectValue placeholder="Todo el profesorado" /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">Todo el profesorado</SelectItem>
                              {opcionesFiltro.profesores.map((profesor) => <SelectItem key={profesor.id} value={String(profesor.id)}>{profesor.etiqueta}</SelectItem>)}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-1.5">
                          <Label htmlFor="filtro-tipo" className="text-xs">Tipo de grupo</Label>
                          <Select value={tipoFilter} onValueChange={setTipoFilter}>
                            <SelectTrigger id="filtro-tipo" className="h-9 text-xs"><SelectValue placeholder="Todos los tipos" /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">Todos los tipos</SelectItem>
                              {opcionesFiltro.tipos.map((tipo) => <SelectItem key={tipo} value={tipo}>{tipo} · {getLabelTipoActividad(tipo)}</SelectItem>)}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-1.5">
                          <Label htmlFor="filtro-cobertura" className="text-xs">Cobertura</Label>
                          <Select value={coberturaFilter} onValueChange={setCoberturaFilter}>
                            <SelectTrigger id="filtro-cobertura" className="h-9 text-xs"><SelectValue placeholder="Cualquier cobertura" /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">Cualquier cobertura</SelectItem>
                              <SelectItem value="completa">Completamente cubierta</SelectItem>
                              <SelectItem value="parcial">Con horas pendientes</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      {hayCriterios && <Button variant="ghost" size="sm" className="h-8 gap-1.5 px-2 text-xs" onClick={limpiarCriterios}><X className="h-3.5 w-3.5" />Limpiar búsqueda y filtros</Button>}
                    </div>
                  </PopoverContent>
                </Popover>
              </div>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              {loading ? <p className="py-10 text-center text-sm text-muted-foreground">Cargando adjudicaciones…</p>
                : error ? <div className="space-y-3 py-8 text-center"><p className="text-sm text-destructive">{error}</p><Button variant="outline" onClick={cargar}>Reintentar</Button></div>
                : <><p className="mb-3 text-xs text-muted-foreground">Mostrando {actividades.length} de {datos?.actividades.length ?? 0} actividades confirmadas de tu ámbito.</p><Table>
                    <TableHeader><TableRow><TableHead className="min-w-[230px]">Actividad</TableHead><TableHead className="min-w-[180px]">Área y cobertura</TableHead><TableHead className="min-w-[280px]">Profesorado asignado</TableHead>{puedeRevisar && <TableHead className="min-w-[150px]">Revisión</TableHead>}</TableRow></TableHeader>
                    <TableBody>
                      {actividades.map((actividad) => {
                        const cobertura = actividad.horas_totales > 0 ? Math.min(100, (actividad.horas_asignadas / actividad.horas_totales) * 100) : 0;
                        return <TableRow key={actividad.id}>
                          <TableCell><p className="font-semibold text-primary">{actividad.nombre_asignatura || actividad.codigo}</p><p className="mt-1 text-xs text-muted-foreground">Código {actividad.codigo} · {actividad.grupo} · {actividad.tipo}</p></TableCell>
                          <TableCell><p className="text-xs font-medium text-muted-foreground">{actividad.area_codigo || "Sin área"}</p><div className="mt-2 flex items-center gap-2"><Progress value={cobertura} className="h-2 w-24" /><span className="text-xs font-semibold">{actividad.horas_asignadas.toFixed(1)} / {actividad.horas_totales.toFixed(1)} h</span></div>{actividad.horas_pendientes > 0.01 && <p className="mt-1 text-xs text-amber-700">Faltan {actividad.horas_pendientes.toFixed(1)} h</p>}</TableCell>
                          <TableCell>{actividad.docentes.length > 0 ? <div className="space-y-2">{actividad.docentes.map((docente) => <div key={docente.profesor_id} className="flex items-center justify-between gap-3 rounded-md bg-muted/60 px-3 py-2"><span className="text-sm font-medium">{nombreDocente(docente)}<span className="ml-2 text-xs font-normal text-muted-foreground">{docente.categoria}</span></span><Badge variant="secondary">{docente.horas_asignadas.toFixed(1)} h</Badge></div>)}</div> : <p className="flex items-center gap-2 text-sm text-muted-foreground"><UsersRound className="h-4 w-4" />Sin docentes adjudicados todavía</p>}</TableCell>
                          {puedeRevisar && <TableCell>{actividad.docentes.length > 0 ? <div className="space-y-2">{actividad.docentes.map((docente) => <Button key={docente.profesor_id} variant="outline" size="sm" className="w-full gap-1.5" onClick={() => { setRevision({ actividad, docente }); setMotivoRevision(""); }}><RotateCcw className="h-3.5 w-3.5" />Devolver</Button>)}</div> : <span className="text-xs text-muted-foreground">—</span>}</TableCell>}
                        </TableRow>;
                      })}
                      {actividades.length === 0 && <TableRow><TableCell colSpan={puedeRevisar ? 4 : 3} className="py-10 text-center text-sm text-muted-foreground">No hay actividades que coincidan con la búsqueda.</TableCell></TableRow>}
                    </TableBody>
                  </Table></>}
            </CardContent>
          </Card>

          <AlertDialog open={revision !== null} onOpenChange={(abierto) => { if (!abierto && !devolviendo) setRevision(null); }}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Devolver adjudicación para revisión</AlertDialogTitle>
                <AlertDialogDescription>
                  {revision ? <>Solo se devolverán las {revision.docente.horas_asignadas.toFixed(1)} h de <strong>{nombreDocente(revision.docente)}</strong> en <strong>{revision.actividad.nombre_asignatura || revision.actividad.codigo}</strong>. Pasarán a su borrador y tendrá turno prioritario; el resto del área no se reinicia.</> : null}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <Textarea value={motivoRevision} onChange={(event) => setMotivoRevision(event.target.value)} placeholder="Motivo de la corrección (mínimo 3 caracteres)" disabled={devolviendo} />
              <AlertDialogFooter>
                <AlertDialogCancel disabled={devolviendo}>Cancelar</AlertDialogCancel>
                <AlertDialogAction disabled={devolviendo || motivoRevision.trim().length < 3} onClick={(event) => { event.preventDefault(); void confirmarDevolucion(); }}>
                  <RotateCcw className="mr-2 h-4 w-4" />{devolviendo ? "Devolviendo…" : "Devolver a revisión"}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </main>
    </div>
  );
}
