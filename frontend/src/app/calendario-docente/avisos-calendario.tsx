import { IncidenciaPlanificacion } from '@/lib/planificacion-docente';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export function AvisosCalendario({ incidencias }: { incidencias: IncidenciaPlanificacion[] }) {
  const sinFranja = incidencias.filter(item => item.requiere_horario === false);
  const pendientes = incidencias.filter(item => item.requiere_horario !== false);
  return <>
    {pendientes.length > 0 && <Card className="border-amber-200 bg-amber-50/60 shadow-sm">
      <CardHeader>
        <CardTitle className="text-lg text-amber-950">Carga y horario pendientes de conciliar · {pendientes.length} actividades</CardTitle>
        <CardDescription className="text-amber-900">Cada profesor ve todas las sesiones registradas del grupo, aunque solo tenga adjudicada una parte. La diferencia con la carga no significa necesariamente que falten clases: puede haber docencia sin franja fija o datos pendientes de confirmar.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">{pendientes.map(item => <div key={item.id} className="rounded-md border border-amber-200 bg-background/70 p-3 text-sm">
        <p className="font-medium">{item.nombre_asignatura || item.codigo} · {item.grupo}</p>
        <dl className="mt-2 grid gap-x-5 gap-y-2 sm:grid-cols-2 lg:grid-cols-4">
          <div><dt className="text-muted-foreground">Total de la actividad</dt><dd>{item.horas_actividad.toFixed(1)} h</dd></div>
          <div><dt className="text-muted-foreground">Adjudicadas a este profesor</dt><dd>{(item.horas_adjudicadas ?? 0).toFixed(1)} h</dd></div>
          {item.estado === 'AJUSTE_PENDIENTE' && <>
            <div><dt className="text-muted-foreground">Representadas en el calendario</dt><dd>{Math.max(0, item.horas_actividad - item.horas).toFixed(1)} h</dd></div>
            <div><dt className="text-muted-foreground">Diferencia pendiente de aclarar</dt><dd>{item.horas.toFixed(1)} h</dd></div>
          </>}
        </dl>
        <p className="mt-2 text-amber-900">{item.estado === 'AJUSTE_PENDIENTE' ? 'Contrasta el horario y la modalidad en la guía docente antes de añadir sesiones. No se han inventado fechas, repartido semanas ni alterado las adjudicaciones.' : item.observacion}</p>
      </div>)}</CardContent>
    </Card>}
    {sinFranja.length > 0 && <Card className="shadow-sm">
      <CardHeader><CardTitle className="text-lg">Docencia sin horario fijo</CardTitle><CardDescription>Estas actividades están adjudicadas, pero no ocupan una franja semanal. No son errores de calendario ni provocan solapes.</CardDescription></CardHeader>
      <CardContent className="space-y-2">{sinFranja.map(item => <div key={item.id} className="rounded-md border p-3 text-sm"><p className="font-medium">{item.nombre_asignatura || item.codigo} · {item.grupo}</p><p className="mt-1 text-muted-foreground">{(item.horas_adjudicadas ?? 0).toFixed(1)} h adjudicadas a este profesor · {item.horas_actividad.toFixed(1)} h totales de actividad</p></div>)}</CardContent>
    </Card>}
  </>;
}
