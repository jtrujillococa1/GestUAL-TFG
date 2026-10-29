import { Fragment } from "react";
import { AlertTriangle, CalendarDays, Clock3 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type EleccionHorario = {
  actividad_id?: number;
  codigo: string;
  nombre_asignatura?: string | null;
  codigo_grupo: string;
  grupo?: string;
  tipo: string;
  horas: number;
  dias?: string | null;
  horario?: string | null;
  horario_detallado?: Array<{ fecha?: string; dia: string; inicio: string; fin: string }>;
  requiere_horario?: boolean;
  turno?: string | null;
  duracion?: string | null;
};

type Bloque = EleccionHorario & { dia: string; franja: string; fechas?: string[]; periodo_detallado?: "C1" | "C2" };

const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"];
const ALIAS_DIAS: Record<string, string> = {
  lun: "Lunes", lunes: "Lunes", mar: "Martes", martes: "Martes",
  mie: "Miércoles", "mié": "Miércoles", miercoles: "Miércoles", "miércoles": "Miércoles",
  jue: "Jueves", jueves: "Jueves", vie: "Viernes", viernes: "Viernes",
};

function normalizarDia(valor: string) {
  return ALIAS_DIAS[valor.trim().toLocaleLowerCase("es")];
}

function bloquesDeActividad(item: EleccionHorario): Bloque[] {
  const bloques: Bloque[] = [];
  const sesionesDetalladas = item.horario_detallado ?? [];
  if (sesionesDetalladas.length > 0) {
    const agrupados = new Map<string, Bloque>();
    sesionesDetalladas.forEach((sesion) => {
      const dia = normalizarDia(sesion.dia);
      if (!dia || !sesion.inicio || !sesion.fin) return;
      const periodo_detallado = sesion.fecha && Number(sesion.fecha.slice(5, 7)) <= 8 ? "C2" : "C1";
      const franja = `${sesion.inicio.padStart(5, "0")}-${sesion.fin.padStart(5, "0")}`;
      const clave = `${dia}-${franja}-${periodo_detallado}`;
      const actual = agrupados.get(clave) ?? { ...item, dia, franja, fechas: [], periodo_detallado };
      if (sesion.fecha && !actual.fechas?.includes(sesion.fecha)) actual.fechas?.push(sesion.fecha);
      agrupados.set(clave, actual);
    });
    return [...agrupados.values()];
  }
  const explicitos = /([A-Za-zÁÉÍÓÚáéíóúÑñ]+)\s+(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})/g;
  for (const coincidencia of item.horario?.matchAll(explicitos) ?? []) {
    const dia = normalizarDia(coincidencia[1]);
    if (dia) bloques.push({ ...item, dia, franja: `${coincidencia[2].padStart(5, "0")}-${coincidencia[3].padStart(5, "0")}` });
  }
  if (bloques.length) return bloques;

  const franja = item.horario?.match(/(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})/);
  if (!franja) return [];
  for (const valor of (item.dias ?? "").split(/[,/;·]/)) {
    const dia = normalizarDia(valor);
    if (dia) bloques.push({ ...item, dia, franja: `${franja[1].padStart(5, "0")}-${franja[2].padStart(5, "0")}` });
  }
  return bloques;
}

function etiquetaTipo(tipo: string) {
  const etiquetas: Record<string, string> = {
    GD: "Teoría", GT: "Prácticas", GL: "Laboratorio", GA: "Seminario",
  };
  return etiquetas[tipo] ?? tipo;
}

function minutos(valor: string) {
  const [hora, minuto] = valor.split(":").map(Number);
  return hora * 60 + minuto;
}

function franjasSeSolapan(primera: string, segunda: string) {
  const [inicioPrimera, finPrimera] = primera.split("-");
  const [inicioSegunda, finSegunda] = segunda.split("-");
  return minutos(inicioPrimera) < minutos(finSegunda) && minutos(inicioSegunda) < minutos(finPrimera);
}

function duracionNormalizada(valor?: string | null) {
  const texto = (valor ?? "").trim().toLocaleLowerCase("es");
  if (["1", "c1", "1c", "1q", "primer cuatrimestre", "primero"].includes(texto)) return "C1";
  if (["2", "c2", "2c", "2q", "segundo cuatrimestre", "segundo"].includes(texto)) return "C2";
  if (["a", "anual", "curso completo", "todo el curso"].includes(texto)) return "ANUAL";
  return texto || null;
}

function duracionesCompatibles(primera?: string | null, segunda?: string | null) {
  const d1 = duracionNormalizada(primera);
  const d2 = duracionNormalizada(segunda);
  return !d1 || !d2 || d1 === "ANUAL" || d2 === "ANUAL" || d1 === d2;
}

function claveActividad(item: EleccionHorario) {
  return String(item.actividad_id ?? `${item.codigo}-${item.tipo}-${item.codigo_grupo}`);
}

function claveBloque(bloque: Bloque) {
  return `${claveActividad(bloque)}-${bloque.dia}-${bloque.franja}-${bloque.periodo_detallado ?? ""}`;
}

function coincidenEnFecha(primero: Bloque, segundo: Bloque) {
  if (!primero.fechas?.length || !segundo.fechas?.length) return true;
  return primero.fechas.some((fecha) => segundo.fechas?.includes(fecha));
}

function calcularSolapes(bloques: Bloque[]) {
  const bloquesConSolape = new Set<string>();
  const solapes = new Set<string>();
  bloques.forEach((bloque, indice) => {
    bloques.slice(indice + 1).forEach((otro) => {
      if (
        bloque.dia === otro.dia
        && claveActividad(bloque) !== claveActividad(otro)
        && coincidenEnFecha(bloque, otro)
        && duracionesCompatibles(bloque.duracion, otro.duracion)
        && franjasSeSolapan(bloque.franja, otro.franja)
      ) {
        bloquesConSolape.add(claveBloque(bloque));
        bloquesConSolape.add(claveBloque(otro));
        solapes.add([claveBloque(bloque), claveBloque(otro)].sort().join("|"));
      }
    });
  });
  return { bloquesConSolape, total: solapes.size };
}

function etiquetaPeriodo(duracion?: string | null) {
  const periodo = duracionNormalizada(duracion);
  if (periodo === "ANUAL") return "Anual";
  if (periodo === "C1") return "1.º cuatrimestre";
  if (periodo === "C2") return "2.º cuatrimestre";
  return duracion || "Periodo sin especificar";
}

function TablaHorario({ titulo, bloques }: { titulo: string; bloques: Bloque[] }) {
  const franjas = [...new Set(bloques.map((bloque) => bloque.franja))].sort((a, b) => a.localeCompare(b));
  const { bloquesConSolape, total: totalSolapes } = calcularSolapes(bloques);

  if (bloques.length === 0) return null;

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-foreground">{titulo}</h3>
        <span className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">{bloques.length} sesiones</span>
      </div>
      {totalSolapes > 0 && (
        <div role="alert" className="flex items-start gap-2 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <p><strong>{totalSolapes} solape{totalSolapes === 1 ? "" : "s"} detectado{totalSolapes === 1 ? "" : "s"} en este cuatrimestre.</strong> Elimina o cambia una de las actividades marcadas antes de confirmar el turno.</p>
        </div>
      )}
      <div className="overflow-x-auto rounded-md border">
        <div className="min-w-[760px] grid grid-cols-[90px_repeat(5,minmax(130px,1fr))] text-sm">
          <div className="bg-muted p-3 font-medium">Hora</div>
          {DIAS.map((dia) => <div key={dia} className="bg-muted p-3 text-center font-medium">{dia}</div>)}
          {franjas.map((franja) => (
            <Fragment key={franja}>
              <div className="border-t p-3 font-medium text-muted-foreground">{franja}</div>
              {DIAS.map((dia) => {
                const items = bloques.filter((bloque) => bloque.franja === franja && bloque.dia === dia);
                const haySolape = items.some((item) => bloquesConSolape.has(claveBloque(item)));
                return <div key={`${franja}-${dia}`} className={`min-h-24 border-l border-t p-2 ${haySolape ? "bg-red-50/60" : ""}`}>
                  {items.map((item) => {
                    const enSolape = bloquesConSolape.has(claveBloque(item));
                    return <div key={claveBloque(item)} className={`mb-1 rounded p-2 text-xs ${enSolape ? "border border-red-300 bg-red-100 text-red-950" : "bg-blue-50 text-blue-950"}`}>
                      <p className="font-semibold">{item.nombre_asignatura || item.codigo}</p>
                      <p>{etiquetaTipo(item.tipo)} · {item.grupo || `Grupo ${item.codigo_grupo}`}</p>
                      <p>{item.periodo_detallado === "C1" ? "1.º cuatrimestre" : item.periodo_detallado === "C2" ? "2.º cuatrimestre" : etiquetaPeriodo(item.duracion)} · {item.horas} h adjudicadas</p>
                    </div>;
                  })}
                </div>;
              })}
            </Fragment>
          ))}
        </div>
      </div>
    </section>
  );
}

export function HorarioSeleccionado({
  seleccion,
  open,
  onOpenChange,
}: {
  seleccion: EleccionHorario[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const bloques = seleccion.flatMap(bloquesDeActividad);
  const actividadConHorario = new Set(bloques.map(claveActividad));
  const sinHorarioFijo = seleccion.filter((item) => item.requiere_horario === false);
  const pendientes = seleccion.filter(
    (item) => item.requiere_horario !== false && !actividadConHorario.has(claveActividad(item)),
  );
  const horas = seleccion.reduce((total, item) => total + Number(item.horas || 0), 0);
  const bloquesPrimerCuatrimestre = bloques.filter((bloque) => {
    if (bloque.periodo_detallado) return bloque.periodo_detallado === "C1";
    const periodo = duracionNormalizada(bloque.duracion);
    return periodo === "C1" || periodo === "ANUAL";
  });
  const bloquesSegundoCuatrimestre = bloques.filter((bloque) => {
    if (bloque.periodo_detallado) return bloque.periodo_detallado === "C2";
    const periodo = duracionNormalizada(bloque.duracion);
    return periodo === "C2" || periodo === "ANUAL";
  });
  const bloquesSinPeriodo = bloques.filter((bloque) => !bloque.periodo_detallado && !["C1", "C2", "ANUAL"].includes(duracionNormalizada(bloque.duracion) ?? ""));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-[min(1200px,96vw)] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><CalendarDays className="h-5 w-5" />Horario semanal del borrador</DialogTitle>
          <DialogDescription>{horas.toFixed(1)} h preseleccionadas. Las franjas se separan por cuatrimestre para distinguir correctamente los solapes.</DialogDescription>
        </DialogHeader>
        {bloques.length > 0 ? (
          <div className="space-y-8">
            <TablaHorario titulo="Primer cuatrimestre" bloques={bloquesPrimerCuatrimestre} />
            <TablaHorario titulo="Segundo cuatrimestre" bloques={bloquesSegundoCuatrimestre} />
            <TablaHorario titulo="Periodo sin especificar" bloques={bloquesSinPeriodo} />
          </div>
        ) : (
          <p className="rounded-md bg-muted p-4 text-sm text-muted-foreground">Aún no hay grupos con sesiones semanales definidas.</p>
        )}
        {pendientes.length > 0 && (
          <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <p className="mb-2 flex items-center gap-2 font-medium"><Clock3 className="h-4 w-4" />Horario pendiente de definir</p>
            <ul className="space-y-1">
              {pendientes.map((item) => <li key={item.actividad_id ?? `${item.codigo}-${item.tipo}-${item.codigo_grupo}`}>
                {item.nombre_asignatura || item.codigo} · {etiquetaTipo(item.tipo)} · {item.grupo || `Grupo ${item.codigo_grupo}`} · {item.horas} h
              </li>)}
            </ul>
          </div>
        )}
        {sinHorarioFijo.length > 0 && (
          <div className="rounded-md border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900">
            <p className="mb-2 flex items-center gap-2 font-medium"><Clock3 className="h-4 w-4" />Sin horario semanal fijo</p>
            <p className="mb-2 text-xs">Estas actividades se muestran fuera de la cuadrícula y no generan solapes, porque no reservan una franja presencial.</p>
            <ul className="space-y-1">
              {sinHorarioFijo.map((item) => <li key={item.actividad_id ?? `${item.codigo}-${item.tipo}-${item.codigo_grupo}`}>
                {item.nombre_asignatura || item.codigo} · {etiquetaTipo(item.tipo)} · {item.grupo || `Grupo ${item.codigo_grupo}`} · {item.horas} h
              </li>)}
            </ul>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
