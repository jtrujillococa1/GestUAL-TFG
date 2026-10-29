"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Building2,
  Layers,
  Loader2,
  RotateCcw,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getAreas } from "@/lib/areas";
import { getDepartamentos } from "@/lib/departamentos";
import {
  type AlcanceResetOrdenacion,
  resetOrdenacionPorAlcance,
} from "@/lib/eleccion-service";
import { toast } from "@/hooks/use-toast";

type Departamento = { id: number; codigo: string; nombre: string };
type Area = { id: number; codigo: string; nombre: string; departamento_id: number };

const CONFIRMACION = "RESETEAR";

/** Acción destructiva acotada, visible exclusivamente en el panel de admin. */
export function ResetOrdenacionAlcanceDialog({ onReset }: { onReset?: () => void }) {
  const [open, setOpen] = useState(false);
  const [tipo, setTipo] = useState<AlcanceResetOrdenacion>("area");
  const [objetivoId, setObjetivoId] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [cargandoDatos, setCargandoDatos] = useState(false);
  const [datosCargados, setDatosCargados] = useState(false);
  const [reiniciando, setReiniciando] = useState(false);
  const [departamentos, setDepartamentos] = useState<Departamento[]>([]);
  const [areas, setAreas] = useState<Area[]>([]);

  useEffect(() => {
    if (!open || datosCargados) return;
    let active = true;
    setCargandoDatos(true);
    Promise.all([getDepartamentos(), getAreas()])
      .then(([datosDepartamentos, datosAreas]) => {
        if (!active) return;
        setDepartamentos(datosDepartamentos);
        setAreas(datosAreas);
      })
      .catch((error) => {
        if (!active) return;
        toast({
          title: "No se pudo cargar el alcance",
          description: error instanceof Error ? error.message : "Inténtalo de nuevo.",
          variant: "destructive",
        });
      })
      .finally(() => {
        if (!active) return;
        setCargandoDatos(false);
        setDatosCargados(true);
      });
    return () => { active = false; };
  }, [open, datosCargados]);

  const objetivos = tipo === "area" ? areas : departamentos;
  const objetivo = useMemo(
    () => objetivos.find((item) => item.id === Number(objetivoId)),
    [objetivos, objetivoId],
  );
  const areasAfectadas = tipo === "departamento"
    ? areas.filter((area) => area.departamento_id === Number(objetivoId)).length
    : objetivoId ? 1 : 0;
  const confirmado = confirmacion.trim() === CONFIRMACION && Boolean(objetivoId);

  const cerrar = (forzar = false) => {
    if (reiniciando && !forzar) return;
    setOpen(false);
    setObjetivoId("");
    setConfirmacion("");
    setTipo("area");
    setDatosCargados(false);
    setDepartamentos([]);
    setAreas([]);
  };

  const reiniciar = async () => {
    if (!confirmado) return;
    setReiniciando(true);
    try {
      const resultado = await resetOrdenacionPorAlcance(tipo, Number(objetivoId));
      toast({ title: "Ordenación reiniciada", description: resultado.mensaje });
      cerrar(true);
      onReset?.();
    } catch (error) {
      toast({
        title: "No se pudo reiniciar la ordenación",
        description: error instanceof Error ? error.message : "Inténtalo de nuevo.",
        variant: "destructive",
      });
    } finally {
      setReiniciando(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(nuevoEstado) => (nuevoEstado ? setOpen(true) : cerrar())}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="border-destructive/40 text-destructive hover:bg-destructive/5 hover:text-destructive">
          <RotateCcw className="mr-2 h-4 w-4" /> Reiniciar ordenación
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" /> Reinicio acotado de ordenación
          </DialogTitle>
          <DialogDescription>
            Elige exactamente qué cola quieres reiniciar. Solo se eliminarán sus borradores y sus asignaciones confirmadas; las demás áreas permanecerán intactas.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="grid grid-cols-2 gap-3">
            <Button
              type="button"
              variant={tipo === "area" ? "default" : "outline"}
              onClick={() => { setTipo("area"); setObjetivoId(""); }}
              className="justify-start"
            >
              <Layers className="mr-2 h-4 w-4" /> Un área
            </Button>
            <Button
              type="button"
              variant={tipo === "departamento" ? "default" : "outline"}
              onClick={() => { setTipo("departamento"); setObjetivoId(""); }}
              className="justify-start"
            >
              <Building2 className="mr-2 h-4 w-4" /> Un departamento
            </Button>
          </div>

          <div className="space-y-2">
            <Label>{tipo === "area" ? "Área a reiniciar" : "Departamento a reiniciar"}</Label>
            <Select value={objetivoId} onValueChange={setObjetivoId} disabled={cargandoDatos}>
              <SelectTrigger><SelectValue placeholder={cargandoDatos ? "Cargando opciones…" : "Selecciona una opción"} /></SelectTrigger>
              <SelectContent>
                {objetivos.map((item) => (
                  <SelectItem key={item.id} value={String(item.id)}>
                    {item.codigo} · {item.nombre}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {objetivo && (
            <div className="rounded-lg border border-destructive/25 bg-destructive/5 p-3 text-sm">
              <p className="font-semibold text-destructive">Alcance: {objetivo.codigo} · {objetivo.nombre}</p>
              <p className="mt-1 text-muted-foreground">
                {tipo === "area"
                  ? "Se reiniciará una única cola de área."
                  : `Se reiniciarán ${areasAfectadas} ${areasAfectadas === 1 ? "área" : "áreas"} del departamento.`}
              </p>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="confirmacion-reset">Confirmación</Label>
            <Input
              id="confirmacion-reset"
              value={confirmacion}
              onChange={(event) => setConfirmacion(event.target.value)}
              placeholder={`Escribe ${CONFIRMACION} para continuar`}
              className="font-mono"
              onKeyDown={(event) => event.key === "Enter" && confirmado && reiniciar()}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => cerrar()} disabled={reiniciando}>Cancelar</Button>
          <Button variant="destructive" onClick={reiniciar} disabled={!confirmado || reiniciando}>
            {reiniciando ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RotateCcw className="mr-2 h-4 w-4" />}
            Reiniciar alcance
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
