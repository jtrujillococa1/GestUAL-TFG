"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { CheckCircle2, GitCompareArrows, RefreshCw, ShieldCheck, TriangleAlert, XCircle } from "lucide-react";
import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { decidirPropuestaConflicto, generarPropuestaConflicto, getPropuestasConflicto, PropuestaConflicto } from "@/lib/conflictos";
import { eleccionService } from "@/lib/eleccion-service";
import { canManageArea } from "@/lib/auth";
import { useLatestRequest } from "@/hooks/use-data-sync";

type TurnoArea = {
  area: { id: number; codigo: string; nombre: string };
  profesor_actual?: string | null;
  ordenacion_terminada: boolean;
  cerrada: boolean;
};

function etiquetaEstado(estado: PropuestaConflicto["estado"]) {
  const clases: Record<PropuestaConflicto["estado"], string> = {
    PENDIENTE: "border-amber-300 bg-amber-50 text-amber-900",
    APROBADA: "border-emerald-300 bg-emerald-50 text-emerald-900",
    RECHAZADA: "border-slate-300 bg-slate-50 text-slate-800",
    OBSOLETA: "border-rose-300 bg-rose-50 text-rose-900",
  };
  return <Badge variant="outline" className={clases[estado]}>{estado[0]}{estado.slice(1).toLowerCase()}</Badge>;
}

export default function ConflictosPage() {
  const { toast } = useToast();
  const [turnos, setTurnos] = useState<TurnoArea[]>([]);
  const [areaId, setAreaId] = useState("");
  const [propuestas, setPropuestas] = useState<PropuestaConflicto[]>([]);
  const [cargando, setCargando] = useState(true);
  const [generando, setGenerando] = useState(false);
  const [avisoBusqueda, setAvisoBusqueda] = useState<string | null>(null);
  const [decidiendo, setDecidiendo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decision, setDecision] = useState<{
    propuesta: PropuestaConflicto;
    aprobar: boolean;
    areaId: number;
    areaCodigo: string;
  } | null>(null);
  const [motivo, setMotivo] = useState("");
  const [ultimaAprobacion, setUltimaAprobacion] = useState<{ area: string; profesor: string } | null>(null);
  const areaIdActual = useRef(areaId);
  const beginCargaRequest = useLatestRequest();
  const beginPropuestasRequest = useLatestRequest();

  const cargarPropuestas = useCallback(async (id: number) => {
    const isCurrent = beginPropuestasRequest();
    if (isCurrent()) setError(null);
    try {
      const siguientes = await getPropuestasConflicto(id);
      if (!isCurrent()) return;
      setPropuestas(siguientes);
    } catch (causa) {
      if (!isCurrent()) return;
      setError(causa instanceof Error ? causa.message : "No se han podido cargar los conflictos.");
    }
  }, [beginPropuestasRequest]);

  const cargar = useCallback(async () => {
    const isCurrent = beginCargaRequest();
    if (isCurrent()) setCargando(true);
    try {
      const disponibles = await eleccionService.getTurnosActivos() as TurnoArea[];
      if (!isCurrent()) return;
      // Tras aprobar una propuesta el área puede quedar terminada y, por lo
      // tanto, salir de las colas activas. Se conserva temporalmente en la
      // vista para mostrar el resultado aprobado en vez de saltar sin aviso a
      // otra área distinta.
      const areaAnterior = areaId
        ? turnos.find((turno) => String(turno.area.id) === areaId)
        : undefined;
      const conservaAreaAnterior = Boolean(
        areaAnterior && !disponibles.some((turno) => turno.area.id === areaAnterior.area.id),
      );
      const turnosVisibles = conservaAreaAnterior
        ? [...disponibles, { ...areaAnterior!, profesor_actual: null, ordenacion_terminada: true }]
        : disponibles;
      setTurnos(turnosVisibles);
      const seleccionado = areaId && turnosVisibles.some((turno) => String(turno.area.id) === areaId)
        ? Number(areaId) : turnosVisibles[0]?.area.id;
      if (seleccionado) {
        areaIdActual.current = String(seleccionado);
        setAreaId(String(seleccionado));
        await cargarPropuestas(seleccionado);
      } else {
        setPropuestas([]);
      }
    } catch (causa) {
      if (!isCurrent()) return;
      setError(causa instanceof Error ? causa.message : "No se ha podido preparar el apartado de conflictos.");
    } finally {
      if (isCurrent()) setCargando(false);
    }
  }, [areaId, beginCargaRequest, cargarPropuestas, turnos]);

  useEffect(() => { void cargar(); }, []); // Solo se inicializa al abrir la pantalla.

  const turno = useMemo(() => turnos.find((item) => String(item.area.id) === areaId), [turnos, areaId]);
  const pendiente = propuestas.find((propuesta) => propuesta.estado === "PENDIENTE");
  const puedeGenerar = Boolean(turno?.profesor_actual) && !turno?.cerrada && !decidiendo;

  const seleccionarArea = (valor: string) => {
    setAvisoBusqueda(null);
    setUltimaAprobacion(null);
    setPropuestas([]);
    areaIdActual.current = valor;
    setAreaId(valor);
    void cargarPropuestas(Number(valor));
  };

  const generar = async () => {
    if (!areaId || generando || decidiendo) return;
    setAvisoBusqueda(null);
    const areaSolicitada = Number(areaId);
    const profesorSolicitado = turno?.profesor_actual ?? "el profesor en turno";
    setGenerando(true);
    try {
      const propuesta = await generarPropuestaConflicto(areaSolicitada);
      toast({
        title: "Propuesta calculada",
        description: `${propuesta.propuesta.impacto.movimientos} movimiento(s) para desbloquear a ${propuesta.profesor_bloqueado ?? profesorSolicitado}. No se ha modificado ninguna adjudicación.`,
      });
      // Si se cambió de área durante el cálculo, la respuesta no debe
      // sustituir la lista que el usuario ya está consultando.
      if (areaIdActual.current === String(areaSolicitada)) {
        await cargarPropuestas(areaSolicitada);
      }
    } catch (causa) {
      if (areaIdActual.current === String(areaSolicitada)) setAvisoBusqueda(causa instanceof Error ? causa.message : 'No se ha podido completar la búsqueda. Puedes volver a intentarlo.');
      toast({ title: "No se ha generado una propuesta", description: causa instanceof Error ? causa.message : "El área no tiene una solución automática.", variant: "destructive" });
    } finally {
      setGenerando(false);
    }
  };

  const decidir = async () => {
    if (!decision || decidiendo) return;
    if (!decision.aprobar && motivo.trim().length < 3) return;
    const areaDecision = decision.areaId;
    setDecidiendo(true);
    try {
      const resultado = await decidirPropuestaConflicto(areaDecision, decision.propuesta.id, decision.aprobar, motivo.trim() || undefined);
      if (decision.aprobar && !resultado.advertencia_calendario) {
        setUltimaAprobacion({
          area: decision.areaCodigo,
          profesor: decision.propuesta.profesor_bloqueado,
        });
      } else if (decision.aprobar) {
        setUltimaAprobacion(null);
        setAvisoBusqueda(resultado.advertencia_calendario ?? null);
      }
      toast({
        title: decision.aprobar ? "Propuesta aprobada" : "Propuesta rechazada",
        variant: resultado.advertencia_calendario ? "destructive" : "default",
        description: resultado.advertencia_calendario || (decision.aprobar
          ? "La ordenación del área se ha actualizado y el calendario se recalculará con el nuevo reparto."
          : "La ordenación no se ha modificado."),
      });
      setDecision(null);
      setMotivo("");
      await cargar();
    } catch (causa) {
      toast({ title: "No se ha podido registrar la decisión", description: causa instanceof Error ? causa.message : "Recarga el área e inténtalo de nuevo.", variant: "destructive" });
    } finally {
      setDecidiendo(false);
    }
  };

  if (!canManageArea()) {
    return <div className="min-h-screen"><Header /><Sidebar /><main className="pt-24 lg:ml-64"><Alert className="mx-auto max-w-xl"><TriangleAlert className="h-4 w-4" /><AlertTitle>Acceso restringido</AlertTitle><AlertDescription>Este apartado está reservado a responsables y administración.</AlertDescription></Alert></main></div>;
  }

  return (
    <div className="min-h-screen bg-muted/30">
      <Header /><Sidebar />
      <main className="px-4 pb-10 pt-24 lg:ml-64 lg:px-8">
        <div className="mx-auto max-w-6xl space-y-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div><h1 className="flex items-center gap-2 text-2xl font-bold text-primary"><GitCompareArrows className="h-6 w-6" />Conflictos de ordenación</h1><p className="mt-1 text-sm text-muted-foreground">Propone intercambios entre profesorado del mismo área cuando el turno actual ya no tiene alternativas viables.</p></div>
            <Button variant="outline" onClick={() => void cargar()} disabled={cargando}><RefreshCw className={`mr-2 h-4 w-4 ${cargando ? "animate-spin" : ""}`} />Actualizar</Button>
          </div>

          <Card className="border-none shadow-sm"><CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-end md:justify-between"><div className="min-w-72 space-y-1.5"><Label>Área</Label><Select value={areaId} onValueChange={seleccionarArea} disabled={cargando || turnos.length === 0}><SelectTrigger><SelectValue placeholder="Selecciona un área" /></SelectTrigger><SelectContent>{turnos.map((item) => <SelectItem key={item.area.id} value={String(item.area.id)}>{item.area.codigo} · {item.area.nombre}</SelectItem>)}</SelectContent></Select></div><div className="rounded-md bg-muted px-4 py-3 text-sm"><p className="text-muted-foreground">Turno actual</p><p className="font-semibold text-primary">{turno?.profesor_actual || (turno?.cerrada ? "Área cerrada" : "Sin turnos pendientes")}</p></div></CardContent></Card>

          {turno?.profesor_actual && <Alert className="border-blue-200 bg-blue-50/70"><ShieldCheck className="h-4 w-4 text-blue-800" /><AlertTitle className="text-blue-950">Resolución siempre supervisada</AlertTitle><AlertDescription className="text-blue-900">El solver no aplica cambios. Busca primero la alternativa con menos profesores implicados y menos horas modificadas; después respeta las prioridades declaradas en los perfiles. Puedes seguir buscando alternativas distintas, incluso si implican a más docentes. Solo tendrá efecto si la aprueba un responsable o el administrador.</AlertDescription></Alert>}

          {ultimaAprobacion && <Alert className="border-emerald-300 bg-emerald-50/80"><CheckCircle2 className="h-4 w-4 text-emerald-800" /><AlertTitle className="text-emerald-950">Reorganización aplicada correctamente</AlertTitle><AlertDescription className="text-emerald-900">{ultimaAprobacion.area} se ha recalculado para {ultimaAprobacion.profesor}. Las adjudicaciones confirmadas y el calendario docente ya reflejan el nuevo reparto.<span className="mt-3 flex flex-wrap gap-2"><Button asChild size="sm" variant="outline" className="border-emerald-300 bg-white"><Link href="/adjudicaciones">Ver adjudicaciones</Link></Button><Button asChild size="sm" variant="outline" className="border-emerald-300 bg-white"><Link href="/calendario-docente">Ver calendario docente</Link></Button></span></AlertDescription></Alert>}

          <Card className="border-none shadow-sm"><CardHeader className="md:flex-row md:items-center md:justify-between"><div><CardTitle className="text-lg">Buscar solución para el turno bloqueado</CardTitle><CardDescription>Busca una alternativa distinta cada vez. Conserva las anteriores para compararlas; rechazar una no aplica cambios ni inicia otra búsqueda automáticamente.</CardDescription></div><Button onClick={() => void generar()} disabled={!puedeGenerar || generando}>{generando ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <GitCompareArrows className="mr-2 h-4 w-4" />}{generando ? "Calculando…" : propuestas.length ? "Buscar más alternativas" : "Generar propuesta"}</Button></CardHeader><CardContent>{avisoBusqueda && <p role="status" className="mb-3 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{avisoBusqueda}</p>}{pendiente && <p className="text-sm text-amber-800">Puedes comparar varias propuestas pendientes. Al aprobar una, las demás quedarán obsoletas.</p>}{!turno?.profesor_actual && <p className="text-sm text-muted-foreground">Selecciona un área con un turno pendiente para poder analizar un bloqueo.</p>}</CardContent></Card>

          {cargando ? <div className="space-y-4"><Skeleton className="h-36" /><Skeleton className="h-56" /></div> : error ? <Alert variant="destructive"><TriangleAlert className="h-4 w-4" /><AlertTitle>No se han podido cargar los conflictos</AlertTitle><AlertDescription>{error}</AlertDescription></Alert> : propuestas.length === 0 ? <Card className="border-dashed"><CardContent className="py-12 text-center text-sm text-muted-foreground">Todavía no hay propuestas de intercambio para esta área.</CardContent></Card> : <div className="space-y-4">{[...propuestas].sort((a, b) => Number(b.estado === "PENDIENTE") - Number(a.estado === "PENDIENTE") || a.propuesta.impacto.profesores_afectados - b.propuesta.impacto.profesores_afectados || a.propuesta.impacto.horas_reasignadas - b.propuesta.impacto.horas_reasignadas || a.id - b.id).map((propuesta) => <Card key={propuesta.id} className="border-none shadow-sm"><CardHeader className="gap-3 md:flex-row md:items-start md:justify-between"><div><CardTitle className="text-lg">Alternativa para {propuesta.profesor_bloqueado}</CardTitle><CardDescription className="mt-1">{propuesta.propuesta.impacto.movimientos} movimiento(s) · {propuesta.propuesta.impacto.profesores_afectados} profesor(es) afectados · {propuesta.propuesta.impacto.horas_reasignadas.toFixed(1)} h reasignadas</CardDescription></div>{etiquetaEstado(propuesta.estado)}</CardHeader><CardContent className="space-y-4"><p className="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">{propuesta.propuesta.impacto.criterio ?? "Intercambio calculado con las restricciones del área."}</p><div className="space-y-2">{propuesta.propuesta.movimientos.map((movimiento, indice) => <div key={`${movimiento.actividad_id}-${indice}`} className="rounded-md border bg-muted/30 p-3 text-sm"><p className="font-semibold text-primary">{movimiento.asignatura} · {movimiento.grupo}</p><p className="mt-1 text-muted-foreground"><strong className="font-medium text-foreground">{movimiento.desde}</strong> cede {movimiento.horas.toFixed(1)} h a <strong className="font-medium text-foreground">{movimiento.hacia}</strong>{movimiento.prioridad_destino ? <> · prioridad {movimiento.prioridad_destino} del docente receptor</> : <> · asignatura sin prioridad declarada por el docente receptor</>}.</p></div>)}</div><p className="text-xs text-muted-foreground">Personas implicadas: {propuesta.propuesta.afectados.map((item) => item.profesor).join(", ")}.</p>{propuesta.estado === "PENDIENTE" && <div className="flex flex-wrap gap-2 border-t pt-4"><Button onClick={() => { if (!areaId) return; setDecision({ propuesta, aprobar: true, areaId: Number(areaId), areaCodigo: turno?.area.codigo ?? `Área ${areaId}` }); setMotivo(""); }}><CheckCircle2 className="mr-2 h-4 w-4" />Aprobar y aplicar</Button><Button variant="outline" onClick={() => { if (!areaId) return; setDecision({ propuesta, aprobar: false, areaId: Number(areaId), areaCodigo: turno?.area.codigo ?? `Área ${areaId}` }); setMotivo(""); }}><XCircle className="mr-2 h-4 w-4" />Rechazar</Button></div>}{propuesta.estado === "RECHAZADA" && propuesta.motivo_rechazo && <p className="text-sm text-muted-foreground">Motivo del rechazo: {propuesta.motivo_rechazo}</p>}</CardContent></Card>)}</div>}
        </div>
      </main>

      <AlertDialog open={decision !== null} onOpenChange={(abierto) => { if (!abierto && !decidiendo) setDecision(null); }}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>{decision?.aprobar ? "Aprobar propuesta de intercambio" : "Rechazar propuesta"}</AlertDialogTitle><AlertDialogDescription>{decision?.aprobar ? "Se sustituirá el reparto confirmado de esta área por el plan mostrado. El cambio queda registrado y se regenerará el calendario docente." : "La ordenación no cambiará. Indica por qué no debe aplicarse esta alternativa."}</AlertDialogDescription></AlertDialogHeader>{!decision?.aprobar && <Textarea value={motivo} onChange={(event) => setMotivo(event.target.value)} placeholder="Motivo del rechazo (mínimo 3 caracteres)" disabled={decidiendo} />}<AlertDialogFooter><AlertDialogCancel disabled={decidiendo}>Cancelar</AlertDialogCancel><AlertDialogAction disabled={decidiendo || (!decision?.aprobar && motivo.trim().length < 3)} onClick={(event) => { event.preventDefault(); void decidir(); }}>{decision?.aprobar ? "Aprobar propuesta" : "Rechazar propuesta"}</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
    </div>
  );
}
