import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Clock, User, ShieldCheck } from "lucide-react";

interface EleccionHeaderProps {
  profesorActual: string | null;
  ordenacionTerminada: boolean;
  nombreProfesor: string;
  esGestor?: boolean;
}

export function EleccionHeader({ profesorActual, ordenacionTerminada, nombreProfesor, esGestor }: EleccionHeaderProps) {
  const esMiTurno = !esGestor && profesorActual === nombreProfesor && !ordenacionTerminada;
  const turnoActivo = esGestor ? !!profesorActual && !ordenacionTerminada : esMiTurno;

  return (
    <Card className="border-none shadow-sm bg-gradient-to-r from-primary/5 to-primary/10">
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-primary/10 rounded-xl">
              {turnoActivo ? (
                esGestor ? (
                  <ShieldCheck className="w-6 h-6 text-primary" />
                ) : (
                  <User className="w-6 h-6 text-primary" />
                )
              ) : (
                <Clock className="w-6 h-6 text-muted-foreground" />
              )}
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">
                {ordenacionTerminada ? "Ordenación finalizada" : "Turno actual"}
              </p>
              <p className="text-xl font-bold">
                {ordenacionTerminada ? "Proceso completado" : profesorActual || "Calculando..."}
              </p>
            </div>
          </div>

          {esMiTurno && (
            <Badge className="bg-green-500 hover:bg-green-600 text-white">
              Es tu turno
            </Badge>
          )}

          {esGestor && !!profesorActual && !ordenacionTerminada && (
            <Badge className="bg-blue-500 hover:bg-blue-600 text-white">
              Modo Gestor
            </Badge>
          )}

          {!esMiTurno && !esGestor && !ordenacionTerminada && profesorActual && (
            <Badge variant="outline" className="border-amber-300 text-amber-700 bg-amber-50">
              En espera
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
