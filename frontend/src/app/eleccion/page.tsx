"use client";

import { useEffect, useState, useMemo, useRef } from "react";
import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { useToast } from "@/hooks/use-toast";
import { getCachedUser, getCachedProfessor } from "@/lib/auth";
import { eleccionService } from "@/lib/eleccion-service";
import { apiFetch } from '@/lib/api-client';
import { EleccionHeader } from "./components/EleccionHeader";
import { EstadisticasCards } from "./components/EstadisticasCards";
import { OpcionesDisponibles } from "./components/OpcionesDisponibles";
import { BorradorActual } from "./components/BorradorActual";
import { HorarioSeleccionado } from "./components/HorarioSeleccionado";
import { ModalConfirmacion } from "./components/ModalConfirmacion";
import { ColaOrdenacion } from "./components/ColaOrdenacion";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CalendarDays, ShieldCheck } from "lucide-react";
import { useDataSync, useLatestRequest } from "@/hooks/use-data-sync";

type TurnoArea = {
  en_preparacion?: boolean;
  area: { id: number; codigo: string; nombre: string };
  profesor_actual: string | null;
  ordenacion_terminada: boolean;
  version: number;
  cerrada: boolean;
  cerrado_en?: string | null;
  puede_gestionar_turno: boolean;
  profesores_pendientes: Array<{
    id: number;
    nombre: string;
    apellidos: string;
    categoria: string;
    horas_restantes: number;
  }>;
};

const TAMANO_BLOQUE_OPCIONES = 8;

export default function EleccionPage() {
  const { toast } = useToast();
  const user = getCachedUser();
  const profesor = getCachedProfessor();

  // Nombre completo propio en formato "Apellidos, Nombre"
  const nombrePropio = useMemo(() => {
    if (!profesor) return null;
    return `${profesor.apellidos}, ${profesor.nombre}`;
  }, [profesor]);

  // Admin y responsables gestionan en nombre del profesor en turno
  const esGestor = user?.rol === "Admin"
    || user?.rol === "Responsable de área"
    || user?.rol === "Responsable de departamento";

  const [turnos, setTurnos] = useState<TurnoArea[]>([]);
  const [areaSeleccionada, setAreaSeleccionada] = useState<number | null>(null);
  const [loadingTurnos, setLoadingTurnos] = useState(true);
  const [errorTurnos, setErrorTurnos] = useState<string | null>(null);
  const [opciones, setOpciones] = useState<any[]>([]);
  const [borrador, setBorrador] = useState<any>({
    seleccion: [],
    horas_confirmadas: 0,
    horas_seleccionadas: 0,
    carga_docente: 0,
    horas_restantes: 0,
    turno_completo: false,
  });
  const [loadingOpciones, setLoadingOpciones] = useState(false);
  const [cargandoMasOpciones, setCargandoMasOpciones] = useState(false);
  const [errorOpciones, setErrorOpciones] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showHorario, setShowHorario] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [mutatingBorrador, setMutatingBorrador] = useState(false);
  const [inicioArea, setInicioArea] = useState<{area: number; estado: 'validando' | 'iniciada' | 'error'; mensaje: string} | null>(null);
  const inicioAreaLock = useRef(false);
  const [areaAction, setAreaAction] = useState<"cerrar" | "reabrir" | null>(null);
  const [cierrePendiente, setCierrePendiente] = useState<TurnoArea | null>(null);
  const [errorCierre, setErrorCierre] = useState<string | null>(null);
  const borradorMutationLock = useRef(false);
  const confirmMutationLock = useRef(false);
  const areaActionLock = useRef(false);
  const opcionesController = useRef<AbortController | null>(null);
  const beginTurnosRequest = useLatestRequest();
  const beginOpcionesRequest = useLatestRequest();
  const beginBorradorRequest = useLatestRequest();

  const turnoActivo = useMemo(
    () => turnos.find((turno) => turno.area.id === areaSeleccionada) || null,
    [turnos, areaSeleccionada],
  );
  const profesorActual = turnoActivo?.profesor_actual || null;
  const ordenacionTerminada = turnoActivo?.ordenacion_terminada ?? false;
  const areaCerrada = turnoActivo?.cerrada ?? false;
  const puedeGestionarTurno = turnoActivo?.puede_gestionar_turno ?? false;

  // Gestores manejan el turno activo del área seleccionada; los profesores,
  // únicamente su turno dentro de su área docente.
  const nombreGestionado = useMemo(() => {
    if (esGestor) return puedeGestionarTurno ? profesorActual : null;
    return nombrePropio;
  }, [esGestor, puedeGestionarTurno, profesorActual, nombrePropio]);

  // Gestores tienen turno activo cuando hay alguien en cola; profesores solo cuando es su turno
  const esMiTurno = useMemo(() => {
    if (ordenacionTerminada || areaCerrada || !profesorActual) return false;
    return puedeGestionarTurno;
  }, [profesorActual, ordenacionTerminada, areaCerrada, puedeGestionarTurno]);

  // Carga inicial de todas las colas a las que el usuario tiene acceso.
  useEffect(() => {
    loadTurnos();
  }, []);

  // Recargar borrador cuando cambia quién se gestiona
  useEffect(() => {
    if (nombreGestionado && areaSeleccionada) {
      loadBorrador(nombreGestionado, areaSeleccionada);
    }
  }, [nombreGestionado, areaSeleccionada]);

  // Recargar opciones cuando cambia el estado del turno
  useEffect(() => {
    if (esMiTurno && nombreGestionado && areaSeleccionada) {
      loadOpciones(nombreGestionado, areaSeleccionada);
    } else {
      beginOpcionesRequest();
      opcionesController.current?.abort();
      setOpciones([]);
      setCargandoMasOpciones(false);
      setLoadingOpciones(false);
      setErrorOpciones(false);
    }
    return () => { opcionesController.current?.abort(); };
  }, [esMiTurno, nombreGestionado, areaSeleccionada]);

  const loadTurnos = async () => {
    const isCurrent = beginTurnosRequest();
    if (isCurrent()) {
      setLoadingTurnos(true);
      setErrorTurnos(null);
    }
    try {
      const data: TurnoArea[] = await eleccionService.getTurnosActivos();
      if (!Array.isArray(data)) {
        throw new Error("La respuesta de las colas de ordenación no es válida");
      }
      if (!isCurrent()) return;
      setTurnos(data);
      setAreaSeleccionada((actual) => {
        if (actual && data.some((turno) => turno.area.id === actual)) return actual;
        const gestionable = data.find((turno) => turno.puede_gestionar_turno);
        return (gestionable || data[0])?.area.id || null;
      });
    } catch (error: any) {
      if (!isCurrent()) return;
      const mensaje = error.message || "No se han podido cargar las áreas de ordenación";
      setTurnos([]);
      setAreaSeleccionada(null);
      setErrorTurnos(mensaje);
      toast({ title: "Error al cargar la ordenación", description: mensaje, variant: "destructive" });
    } finally {
      if (isCurrent()) setLoadingTurnos(false);
    }
  };

  const loadOpciones = async (nombre: string, areaId: number) => {
    const isCurrent = beginOpcionesRequest();
    opcionesController.current?.abort();
    const controller = new AbortController();
    opcionesController.current = controller;
    setOpciones([]);
    setErrorOpciones(false);
    setCargandoMasOpciones(false);
    setLoadingOpciones(true);
    try {
      // Una sola petición en vuelo: mostrar pronto el primer bloque sin
      // multiplicar los cálculos simultáneos del solver ni sus timeouts.
      let acumuladas: any[] = [];
      while (isCurrent() && !controller.signal.aborted) {
        const data = await eleccionService.getOpciones(nombre, areaId, acumuladas.length, TAMANO_BLOQUE_OPCIONES, controller.signal);
        if (!isCurrent() || controller.signal.aborted) return;
        acumuladas = [...acumuladas, ...data];
        setOpciones(acumuladas);
        setLoadingOpciones(false);
        if (data.length < TAMANO_BLOQUE_OPCIONES) break;
        setCargandoMasOpciones(true);
      }
    } catch (error: any) {
      if (!isCurrent() || controller.signal.aborted) return;
      setErrorOpciones(true);
      toast({ title: "Error", description: error.message, variant: "destructive" });
    } finally {
      if (isCurrent()) {
        setCargandoMasOpciones(false);
        setLoadingOpciones(false);
      }
    }
  };

  const reintentarOpciones = () => {
    if (nombreGestionado && areaSeleccionada) void loadOpciones(nombreGestionado, areaSeleccionada);
  };

  const loadBorrador = async (nombre: string, areaId: number) => {
    const isCurrent = beginBorradorRequest();
    try {
      const data = await eleccionService.getBorrador(nombre, areaId);
      if (!isCurrent()) return;
      setBorrador(data);
    } catch (error: any) {
      if (!isCurrent()) return;
      console.warn("Borrador no disponible:", error.message);
    }
  };

  useDataSync(loadTurnos);

  const sincronizarTrasConflicto = async (error: any) => {
    const mensaje = String(error?.message ?? "").toLocaleLowerCase("es");
    if (!mensaje.includes("cambió en otra sesión") && !mensaje.includes("está cerrada")) return;
    await loadTurnos();
  };

  const handleAgregarOpcion = async (opcion: any) => {
    if (!nombreGestionado || !areaSeleccionada || borradorMutationLock.current) return;
    borradorMutationLock.current = true;
    setMutatingBorrador(true);
    opcionesController.current?.abort();
    try {
      await eleccionService.addToBorrador(
        nombreGestionado,
        opcion.opcion.actividad_id,
        opcion.opcion.codigo,
        opcion.opcion.codigo_grupo,
        opcion.opcion.tipo,
        opcion.opcion.horas,
        areaSeleccionada,
        borrador.version ?? turnoActivo?.version,
      );
      await Promise.all([
        loadBorrador(nombreGestionado, areaSeleccionada),
        void loadOpciones(nombreGestionado, areaSeleccionada),
      ]);
      toast({ title: "Añadido al borrador" });
    } catch (error: any) {
      await sincronizarTrasConflicto(error);
      toast({ title: "Error", description: error.message, variant: "destructive" });
    } finally {
      borradorMutationLock.current = false;
      setMutatingBorrador(false);
    }
  };

  const handleEliminarOpcion = async (actividadId: number | undefined, codigo: string, codigo_grupo: string, tipo: string) => {
    if (!nombreGestionado || !areaSeleccionada || borradorMutationLock.current) return;
    borradorMutationLock.current = true;
    setMutatingBorrador(true);
    opcionesController.current?.abort();
    try {
      await eleccionService.removeFromBorrador(
        nombreGestionado, actividadId, codigo, codigo_grupo, tipo, areaSeleccionada,
        borrador.version ?? turnoActivo?.version,
      );
      await Promise.all([
        loadBorrador(nombreGestionado, areaSeleccionada),
        void loadOpciones(nombreGestionado, areaSeleccionada),
      ]);
      toast({ title: "Eliminado del borrador" });
    } catch (error: any) {
      await sincronizarTrasConflicto(error);
      toast({ title: "Error", description: error.message, variant: "destructive" });
    } finally {
      borradorMutationLock.current = false;
      setMutatingBorrador(false);
    }
  };

  const handleCambiarActividadDevuelta = async (actividadId: number) => {
    if (!nombreGestionado || !areaSeleccionada || borradorMutationLock.current) return;
    const actividadDevuelta = borrador.seleccion?.find((item: any) => item.actividad_id === actividadId);
    if (!actividadDevuelta) {
      toast({ title: "La actividad ya no está en el borrador", description: "Actualiza la pantalla para ver las alternativas disponibles.", variant: "destructive" });
      return;
    }

    borradorMutationLock.current = true;
    setMutatingBorrador(true);
    opcionesController.current?.abort();
    try {
      await eleccionService.removeFromBorrador(
        nombreGestionado,
        actividadDevuelta.actividad_id,
        actividadDevuelta.codigo,
        actividadDevuelta.codigo_grupo,
        actividadDevuelta.tipo,
        areaSeleccionada,
        borrador.version ?? turnoActivo?.version,
      );
      await Promise.all([
        loadBorrador(nombreGestionado, areaSeleccionada),
        void loadOpciones(nombreGestionado, areaSeleccionada),
      ]);
      toast({ title: "Actividad devuelta liberada", description: "Ya puedes seleccionar una alternativa para completar esta revisión." });
    } catch (error: any) {
      await sincronizarTrasConflicto(error);
      toast({ title: "No se pudo preparar el cambio", description: error.message, variant: "destructive" });
    } finally {
      borradorMutationLock.current = false;
      setMutatingBorrador(false);
    }
  };

  const handleLimpiarBorrador = async () => {
    if (!nombreGestionado || !areaSeleccionada || borradorMutationLock.current) return;
    borradorMutationLock.current = true;
    setMutatingBorrador(true);
    opcionesController.current?.abort();
    try {
      await eleccionService.clearBorrador(nombreGestionado, areaSeleccionada, borrador.version ?? turnoActivo?.version);
      await Promise.all([
        loadBorrador(nombreGestionado, areaSeleccionada),
        void loadOpciones(nombreGestionado, areaSeleccionada),
      ]);
      toast({ title: "Borrador limpiado" });
    } catch (error: any) {
      await sincronizarTrasConflicto(error);
      toast({ title: "Error", description: error.message, variant: "destructive" });
    } finally {
      borradorMutationLock.current = false;
      setMutatingBorrador(false);
    }
  };

  const handleConfirmarTurno = async () => {
    if (confirmMutationLock.current) return;
    confirmMutationLock.current = true;
    setConfirming(true);
    try {
      if (!areaSeleccionada) return;
      await eleccionService.confirmarTurno(areaSeleccionada, borrador.version ?? turnoActivo?.version);
      toast({ title: "✅ Turno confirmado", description: "La selección ha sido guardada" });
      setShowConfirmModal(false);
      await loadTurnos();
    } catch (error: any) {
      await sincronizarTrasConflicto(error);
      toast({ title: "Error", description: error.message, variant: "destructive" });
    } finally {
      confirmMutationLock.current = false;
      setConfirming(false);
    }
  };

  const handleCerrarArea = async () => {
    if (!cierrePendiente || areaActionLock.current) return;
    areaActionLock.current = true;
    setAreaAction("cerrar");
    setErrorCierre(null);
    try {
      const resultado = await eleccionService.cerrarArea(cierrePendiente.area.id, cierrePendiente.version);
      setCierrePendiente(null);
      toast({
        title: "Ordenación cerrada",
        description: resultado.advertencias?.[0] || "El área queda bloqueada y preparada para exportación.",
      });
      await loadTurnos();
    } catch (error: any) {
      setErrorCierre(error.message || "No se ha podido validar el cierre. Inténtalo de nuevo.");
      toast({ title: "No se ha podido cerrar", description: error.message, variant: "destructive" });
    } finally {
      areaActionLock.current = false;
      setAreaAction(null);
    }
  };

  const handleReabrirArea = async () => {
    if (!areaSeleccionada || !turnoActivo || areaActionLock.current) return;
    const motivo = window.prompt("Indica el motivo de la reapertura:");
    if (!motivo) return;
    areaActionLock.current = true;
    setAreaAction("reabrir");
    try {
      await eleccionService.reabrirArea(areaSeleccionada, motivo, turnoActivo.version);
      toast({ title: "Ordenación reabierta", description: "La reapertura ha quedado registrada en el historial." });
      await loadTurnos();
    } catch (error: any) {
      toast({ title: "No se ha podido reabrir", description: error.message, variant: "destructive" });
    } finally {
      areaActionLock.current = false;
      setAreaAction(null);
    }
  };

  return (
    <div className="min-h-screen">
      <Header />
      <Sidebar />
      <main className="lg:pl-64 pt-16">
        <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-6">

          {loadingTurnos && (
            <div className="rounded-lg border bg-white p-3 text-sm text-muted-foreground">
              Cargando las colas de ordenación por área…
            </div>
          )}

          {errorTurnos && (
            <div className="flex flex-col gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-destructive">No se han podido cargar las áreas: {errorTurnos}</p>
              <Button variant="outline" size="sm" onClick={loadTurnos}>Reintentar</Button>
            </div>
          )}

          {!loadingTurnos && !errorTurnos && turnos.length === 0 && (
            <div className="flex flex-col gap-3 rounded-lg border bg-white p-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-muted-foreground">No tienes áreas con una cola de ordenación docente disponible.</p>
              <Button variant="outline" size="sm" onClick={loadTurnos}>Actualizar</Button>
            </div>
          )}

          {turnos.length > 0 && (
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between rounded-lg border bg-white p-3">
              <div>
                <p className="text-sm font-semibold">Área cuya ordenación quieres gestionar</p>
                <p className="text-xs text-muted-foreground">
                  Elige una de las colas de tu departamento. Las áreas distintas pueden tener turnos activos simultáneamente.
                </p>
              </div>
              <Select
                value={areaSeleccionada ? String(areaSeleccionada) : undefined}
                onValueChange={(valor) => setAreaSeleccionada(Number(valor))}
              >
                <SelectTrigger className="w-full sm:w-[360px]">
                  <SelectValue placeholder="Selecciona un área" />
                </SelectTrigger>
                <SelectContent>
                  {turnos.map((turno) => (
                    <SelectItem key={turno.area.id} value={String(turno.area.id)}>
                      {turno.area.codigo} · {turno.area.nombre} — {turno.en_preparacion ? "en preparación" : turno.ordenacion_terminada ? "finalizada" : turno.profesor_actual || "sin docentes"}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {inicioArea?.area === areaSeleccionada && <div role={inicioArea.estado === 'error' ? 'alert' : 'status'} aria-live="polite" className="rounded-lg border bg-blue-50 p-4 text-sm">{inicioArea.mensaje}</div>}
          {turnoActivo?.en_preparacion && <div className="rounded-lg border bg-blue-50 p-4 space-y-2">
            <p className="font-semibold">Área en preparación</p>
            <p className="text-sm">Completa actividades, cuotas, profesorado, disponibilidad y prioridades. Los avisos y elecciones comenzarán cuando un gestor valide el inicio.</p>
            {esGestor && <Button disabled={mutatingBorrador} onClick={async () => {
              if (!areaSeleccionada || inicioAreaLock.current) return;
              const area = areaSeleccionada;
              inicioAreaLock.current = true;
              setInicioArea({area, estado: 'validando', mensaje: 'Validando los datos y comprobando la viabilidad. Espera mientras se inicia la ordenación…'});
              setMutatingBorrador(true);
              try {
                await apiFetch(`/areas/${area}/iniciar`, { method: 'POST' });
                setInicioArea({area, estado: 'iniciada', mensaje: 'Ordenación iniciada correctamente. Ya puedes gestionar el turno y consultar las opciones disponibles.'});
                toast({ title: 'Ordenación iniciada', description: 'Los datos se han validado correctamente.' });
                await loadTurnos();
              }
              catch (e) {
                const mensaje = e instanceof Error ? e.message : 'Revisa los datos';
                setInicioArea({area, estado: 'error', mensaje: `No se ha podido completar la operación: ${mensaje}. Actualiza el estado antes de volver a intentarlo.`});
                toast({ title: 'No se pudo completar el inicio', description: mensaje, variant: 'destructive' });
              }
              finally { inicioAreaLock.current = false; setMutatingBorrador(false); }
            }}>{inicioArea?.area === areaSeleccionada && inicioArea.estado === 'validando' ? 'Validando e iniciando…' : 'Validar datos e iniciar ordenación'}</Button>}
          </div>}

          {esGestor && turnoActivo && !turnoActivo.en_preparacion && (
            <div className={`flex flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between ${areaCerrada ? "border-emerald-300 bg-emerald-50" : "bg-white"}`}>
              <div>
                <p className="text-sm font-semibold">
                  {areaCerrada ? "Ordenación cerrada" : "Control de cierre"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {areaCerrada
                    ? "El área está bloqueada. Una reapertura requiere un motivo y queda registrada."
                    : ordenacionTerminada
                      ? "La cola ha terminado. Puedes validar y cerrar el área para preparar la exportación final."
                      : `Versión ${turnoActivo.version}: el área se cerrará cuando termine la cola y todas sus cuotas estén cubiertas.`}
                </p>
              </div>
              {areaCerrada ? (
                <Button variant="outline" size="sm" onClick={handleReabrirArea} disabled={areaAction !== null}>
                  {areaAction === "reabrir" ? "Reabriendo…" : "Reabrir con motivo"}
                </Button>
              ) : ordenacionTerminada ? (
                <Button size="sm" onClick={() => { setErrorCierre(null); setCierrePendiente(turnoActivo); }} disabled={areaAction !== null}>
                  {areaAction === "cerrar" ? "Cerrando…" : "Validar y cerrar área"}
                </Button>
              ) : null}
            </div>
          )}

          {esGestor && profesorActual && !ordenacionTerminada && (
            <div className={`flex items-center gap-2 p-3 border rounded-lg text-sm font-medium ${puedeGestionarTurno ? "bg-blue-50 border-blue-200 text-blue-700" : "bg-amber-50 border-amber-200 text-amber-800"}`}>
              <ShieldCheck className="w-4 h-4 flex-shrink-0" />
              {puedeGestionarTurno ? (
                <>Gestionando {turnoActivo?.area.codigo} · turno de <strong className="ml-1">{profesorActual}</strong></>
              ) : (
                <>El turno de {turnoActivo?.area.codigo} para <strong className="ml-1">{profesorActual}</strong> no pertenece a tu ámbito de gestión.</>
              )}
            </div>
          )}

          {!turnoActivo?.en_preparacion && <EleccionHeader
            profesorActual={profesorActual}
            ordenacionTerminada={ordenacionTerminada}
            nombreProfesor={nombrePropio || ""}
            esGestor={esGestor}
          />}

          {!ordenacionTerminada && !esMiTurno && turnoActivo && (
            <ColaOrdenacion
              area={turnoActivo.area}
              pendientes={turnoActivo.profesores_pendientes ?? []}
              nombrePropio={nombrePropio}
            />
          )}

          <EstadisticasCards
            horasSeleccionadas={(borrador.horas_confirmadas ?? 0) + borrador.horas_seleccionadas}
            horasConfirmadas={borrador.horas_confirmadas}
            cargaDocente={borrador.carga_docente}
            horasRestantes={borrador.horas_restantes}
            turnoCompleto={borrador.turno_completo}
          />

          <div className="flex justify-end">
            <Button variant="outline" onClick={() => setShowHorario(true)}>
              <CalendarDays className="mr-2 h-4 w-4" />Ver horario semanal del borrador
            </Button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <OpcionesDisponibles
                nombreProfesor={nombreGestionado}
                areaId={areaSeleccionada}
                opciones={opciones}
                loading={loadingOpciones}
                esMiTurno={esMiTurno}
                bloqueada={mutatingBorrador}
                onAgregar={handleAgregarOpcion}
                cargandoMasOpciones={cargandoMasOpciones}
                errorCarga={errorOpciones}
                onReintentar={reintentarOpciones}
              />
            </div>
            <div>
              <BorradorActual
                seleccion={borrador.seleccion}
                horasConfirmadas={borrador.horas_confirmadas}
                horasSeleccionadas={borrador.horas_seleccionadas}
                cargaDocente={borrador.carga_docente}
                horasRestantes={borrador.horas_restantes}
                turnoCompleto={borrador.turno_completo}
                esMiTurno={esMiTurno}
                bloqueada={mutatingBorrador || confirming}
                revisionesPendientes={borrador.revisiones_pendientes}
                onEliminar={handleEliminarOpcion}
                onLimpiar={handleLimpiarBorrador}
                onCambiarActividadDevuelta={handleCambiarActividadDevuelta}
                onConfirmar={() => setShowConfirmModal(true)}
              />
            </div>
          </div>

          <HorarioSeleccionado
            seleccion={borrador.seleccion}
            open={showHorario}
            onOpenChange={setShowHorario}
          />

          <Dialog open={cierrePendiente !== null} onOpenChange={(open) => { if (!open && !areaActionLock.current) setCierrePendiente(null); }}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Validar y cerrar área</DialogTitle>
                <DialogDescription>Se comprobarán las cuotas y adjudicaciones de {cierrePendiente?.area.nombre}. Si todo es correcto, la ordenación quedará cerrada y solo se podrá consultar hasta que un gestor la reabra.</DialogDescription>
              </DialogHeader>
              {areaAction === 'cerrar' && <p role="status" className="text-sm">Validando datos y cerrando la ordenación…</p>}
              {errorCierre && <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{errorCierre}</p>}
              <DialogFooter>
                <Button variant="outline" onClick={() => setCierrePendiente(null)} disabled={areaAction !== null}>Cancelar</Button>
                <Button onClick={handleCerrarArea} disabled={areaAction !== null}>{areaAction === 'cerrar' ? 'Validando…' : 'Confirmar cierre'}</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <ModalConfirmacion
            open={showConfirmModal}
            onClose={() => setShowConfirmModal(false)}
            onConfirm={handleConfirmarTurno}
            loading={confirming}
          />
        </div>
      </main>
    </div>
  );
}
