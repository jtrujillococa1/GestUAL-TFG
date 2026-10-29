import { Card, CardContent } from "@/components/ui/card";
import { BookOpen, Clock, CheckCircle2, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";

interface EstadisticasCardsProps {
  horasSeleccionadas: number;
  horasConfirmadas?: number;
  cargaDocente: number;
  horasRestantes: number;
  turnoCompleto: boolean;
}

export function EstadisticasCards({ 
  horasSeleccionadas, 
  horasConfirmadas = 0,
  cargaDocente, 
  horasRestantes, 
  turnoCompleto 
}: EstadisticasCardsProps) {
  const progreso = cargaDocente > 0 ? Math.round((horasSeleccionadas / cargaDocente) * 100) : 0;

  const stats = [
    {
      label: "Carga Docente",
      value: `${cargaDocente}h`,
      icon: BookOpen,
      color: "text-blue-600",
      bg: "bg-blue-50",
    },
    {
      label: horasConfirmadas > 0 ? "Horas adjudicadas" : "Horas seleccionadas",
      value: `${horasSeleccionadas}h`,
      icon: Clock,
      color: "text-purple-600",
      bg: "bg-purple-50",
    },
    {
      label: "Horas Restantes",
      value: `${horasRestantes}h`,
      icon: turnoCompleto ? CheckCircle2 : TrendingUp,
      color: turnoCompleto ? "text-green-600" : "text-amber-600",
      bg: turnoCompleto ? "bg-green-50" : "bg-amber-50",
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {stats.map((stat) => (
        <Card key={stat.label} className="border-none shadow-sm hover:ring-1 hover:ring-primary/10 transition-all">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  {stat.label}
                </p>
                <p className="text-2xl font-bold mt-1">{stat.value}</p>
              </div>
              <div className={cn(stat.bg, stat.color, "p-3 rounded-xl")}>
                <stat.icon className="w-5 h-5" />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
