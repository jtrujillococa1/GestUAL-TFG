import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { AlertCircle, CheckCircle2, PencilLine, Trash2, X } from "lucide-react";

interface Eleccion {
  actividad_id?: number;
  codigo: string;
  nombre_asignatura?: string | null;
  codigo_grupo: string;
  tipo: string;
  horas: number;
}

interface BorradorActualProps {
  seleccion: Eleccion[];
  horasConfirmadas?: number;
  horasSeleccionadas: number;
  cargaDocente: number;
  horasRestantes: number;
  turnoCompleto: boolean;
  esMiTurno: boolean;
  bloqueada?: boolean;
  revisionesPendientes?: Array<{
    id: number;
    actividad_id: number;
    horas_devuelta: number;
    motivo: string;
    nombre_asignatura?: string | null;
    codigo: string;
    grupo?: string | null;
  }>;
  onEliminar: (actividadId: number | undefined, codigo: string, codigo_grupo: string, tipo: string) => void;
  onLimpiar: () => void;
  onCambiarActividadDevuelta?: (actividadId: number) => void;
  onConfirmar: () => void;
}

export function BorradorActual({
  seleccion,
  horasConfirmadas = 0,
  horasSeleccionadas,
  cargaDocente,
  horasRestantes,
  turnoCompleto,
  esMiTurno,
  bloqueada = false,
  revisionesPendientes = [],
  onEliminar,
  onLimpiar,
  onCambiarActividadDevuelta,
  onConfirmar,
}: BorradorActualProps) {
  const horasAdjudicadas = horasConfirmadas + horasSeleccionadas;
  const progreso = cargaDocente > 0 ? Math.round((horasAdjudicadas / cargaDocente) * 100) : 0;

  return (
    <Card className="border-none shadow-sm">
      <CardHeader>
        <div className="flex justify-between items-start">
          <div>
            <CardTitle>Mi Borrador</CardTitle>
            <CardDescription>
              {seleccion.length} {seleccion.length === 1 ? "actividad" : "actividades"} seleccionadas
            </CardDescription>
          </div>
          {seleccion.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={onLimpiar}
              disabled={!esMiTurno || bloqueada}
            >
              <Trash2 className="w-4 h-4 mr-1" />
              Limpiar
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {revisionesPendientes.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
            <div className="flex gap-2">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <div className="min-w-0">
                <p className="font-semibold">Revisión prioritaria</p>
                <p className="mt-1 text-xs leading-relaxed text-amber-900">
                  Estas líneas requieren una corrección. Si siguen preseleccionadas, puedes confirmarlas de nuevo o sustituirlas por otra actividad.
                </p>
                <div className="mt-3 space-y-2">
                  {revisionesPendientes.map((revision) => {
                    const actividadDevueltaEnBorrador = seleccion.some((item) => item.actividad_id === revision.actividad_id);
                    return (
                      <div key={revision.id} className="rounded-md border border-amber-200/80 bg-white/70 p-2.5">
                        <p className="text-xs font-semibold">{revision.nombre_asignatura || revision.codigo}{revision.grupo ? ` · ${revision.grupo}` : ""} · {revision.horas_devuelta.toFixed(1)} h</p>
                        {revision.motivo && <p className="mt-1 text-xs text-amber-900"><span className="font-medium">Motivo:</span> {revision.motivo}</p>}
                        {actividadDevueltaEnBorrador && onCambiarActividadDevuelta && (
                          <Button
                            variant="outline"
                            size="sm"
                            className="mt-2 h-8 border-amber-300 bg-white text-xs hover:bg-amber-100"
                            onClick={() => onCambiarActividadDevuelta(revision.actividad_id)}
                            disabled={!esMiTurno || bloqueada}
                          >
                            <PencilLine className="mr-1.5 h-3.5 w-3.5" />Cambiar esta actividad
                          </Button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Progreso */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Progreso</span>
            <span className="font-semibold">{progreso}%</span>
          </div>
          <Progress value={progreso} className="h-2" />
          <p className="text-xs text-muted-foreground">
            {horasConfirmadas > 0
              ? `${horasAdjudicadas}h adjudicadas (${horasConfirmadas}h confirmadas + ${horasSeleccionadas}h en borrador) de ${cargaDocente}h (${horasRestantes}h restantes)`
              : `${horasSeleccionadas}h de ${cargaDocente}h (${horasRestantes}h restantes)`}
          </p>
        </div>

        {/* Lista de selección */}
        {seleccion.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <p>No has seleccionado ninguna actividad aún</p>
          </div>
        ) : (
          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {seleccion.map((item, idx) => (
              <div
                key={idx}
                className="flex justify-between items-center p-3 bg-muted/30 rounded-lg"
              >
                <div>
                  <p className="font-medium text-sm">
                    {item.nombre_asignatura || item.codigo} - {item.codigo_grupo}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {item.tipo} • {item.horas}h
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onEliminar(item.actividad_id, item.codigo, item.codigo_grupo, item.tipo)}
                  disabled={!esMiTurno || bloqueada}
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            ))}
          </div>
        )}

        {/* Botón confirmar */}
        {seleccion.length > 0 && (
          <Button
            className="w-full"
            onClick={onConfirmar}
            disabled={!turnoCompleto || !esMiTurno || bloqueada}
          >
            <CheckCircle2 className="w-4 h-4 mr-2" />
            {turnoCompleto ? "Confirmar Turno" : `Faltan ${horasRestantes}h`}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
