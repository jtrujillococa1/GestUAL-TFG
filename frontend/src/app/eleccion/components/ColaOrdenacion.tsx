import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle2, Clock3, ListOrdered, UserRound } from "lucide-react";

type ProfesorEnCola = {
  id: number;
  nombre: string;
  apellidos: string;
  categoria: string;
  horas_restantes: number;
};

type ColaOrdenacionProps = {
  area: { codigo: string; nombre: string };
  pendientes: ProfesorEnCola[];
  nombrePropio: string | null;
};

function nombreCompleto(profesor: ProfesorEnCola): string {
  return `${profesor.apellidos}, ${profesor.nombre}`;
}

/** Muestra la prioridad efectiva de la cola calculada por el backend. */
export function ColaOrdenacion({ area, pendientes, nombrePropio }: ColaOrdenacionProps) {
  const posicionPropia = nombrePropio
    ? pendientes.findIndex((profesor) => nombreCompleto(profesor) === nombrePropio)
    : -1;
  const personasDelante = posicionPropia >= 0 ? posicionPropia : 0;

  return (
    <Card className="border-none shadow-sm">
      <CardHeader className="border-b bg-muted/30 pb-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-lg text-primary">
              <ListOrdered className="h-5 w-5" /> Cola de ordenación
            </CardTitle>
            <CardDescription className="mt-1">
              {area.codigo} · {area.nombre} · {pendientes.length} {pendientes.length === 1 ? "turno pendiente" : "turnos pendientes"}
            </CardDescription>
          </div>
          {posicionPropia >= 0 ? (
            <Badge className="w-fit bg-amber-100 text-amber-800 hover:bg-amber-100">
              <Clock3 className="mr-1 h-3.5 w-3.5" />
              {personasDelante === 0
                ? "Tu turno está activo"
                : `${personasDelante} ${personasDelante === 1 ? "persona delante" : "personas delante"}`}
            </Badge>
          ) : nombrePropio ? (
            <Badge variant="outline" className="w-fit border-emerald-200 bg-emerald-50 text-emerald-700">
              <CheckCircle2 className="mr-1 h-3.5 w-3.5" /> Sin turno pendiente
            </Badge>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {posicionPropia >= 0 && personasDelante > 0 && (
          <p className="border-b bg-amber-50/60 px-5 py-3 text-sm text-amber-900">
            Tu posición es la <strong>#{posicionPropia + 1}</strong>. Cuando finalicen los turnos anteriores, podrás seleccionar tus actividades en esta área.
          </p>
        )}
        <ol className="max-h-80 divide-y overflow-y-auto">
          {pendientes.map((profesor, indice) => {
            const esPropio = nombrePropio === nombreCompleto(profesor);
            const esActual = indice === 0;
            return (
              <li key={profesor.id} className={`flex items-center gap-3 px-5 py-3 text-sm ${esPropio ? "bg-primary/5" : ""}`}>
                <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${esActual ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>
                  {indice + 1}
                </span>
                <UserRound className={`h-4 w-4 shrink-0 ${esPropio ? "text-primary" : "text-muted-foreground"}`} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-foreground">
                    {nombreCompleto(profesor)} {esPropio && <span className="text-primary">(tú)</span>}
                  </p>
                  <p className="text-xs text-muted-foreground">{profesor.categoria} · {profesor.horas_restantes} h pendientes</p>
                </div>
                {esActual && <Badge variant="outline" className="border-primary/20 bg-primary/5 text-primary">Turno actual</Badge>}
              </li>
            );
          })}
        </ol>
      </CardContent>
    </Card>
  );
}
