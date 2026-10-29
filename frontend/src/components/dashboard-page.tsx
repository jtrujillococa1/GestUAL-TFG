"use client";

import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getDashboardData } from "@/lib/dashboard";
import { getCachedUser } from "@/lib/auth";
import { ResetOrdenacionAlcanceDialog } from "@/components/admin/reset-ordenacion-alcance-dialog";
import {
  BarChart, Users, BookOpen, Building2, Award, TrendingUp,
  AlertCircle, Clock, Zap, Loader2, RefreshCw, Scale, ArrowRight,
  Layers, LayoutDashboard, ChevronDown, ChevronUp
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { formatearHoras } from "@/lib/horas";
import { useDataSync, useLatestRequest } from "@/hooks/use-data-sync";
export default function DashboardPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const beginRequest = useLatestRequest();
  const user = getCachedUser();

  const loadDashboard = useCallback(async (isRefresh = false) => {
    const isCurrent = beginRequest();
    try {
      if (isCurrent()) {
        if (isRefresh) setRefreshing(true);
        else setLoading(true);
        setError(null);
      }
      
      const dashboardData = await getDashboardData();
      if (!isCurrent()) return;
      setData(dashboardData);
    } catch (error) {
      if (!isCurrent()) return;
      console.error("Error cargando dashboard:", error);
      setError(error instanceof Error ? error.message : "Error desconocido");
    } finally {
      if (isCurrent()) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [beginRequest]);

  const syncDashboard = useCallback(() => loadDashboard(true), [loadDashboard]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  useDataSync(syncDashboard);

  if (loading) {
    return (
      <div className="min-h-screen">
        <Header />
        <Sidebar />
        <main className="lg:pl-64 pt-16">
          <div className="p-8 flex items-center gap-3 text-muted-foreground">
            <Loader2 className="w-5 h-5 animate-spin" /> Cargando dashboard...
          </div>
        </main>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen">
        <Header />
        <Sidebar />
        <main className="lg:pl-64 pt-16">
          <div className="p-8 flex items-center justify-center">
            <div className="space-y-3 text-center">
              <p className="text-destructive">{error || "Error al cargar los datos"}</p>
              <Button variant="outline" size="sm" onClick={() => loadDashboard()}>Reintentar</Button>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F8FAFC]">
      <Header />
      <Sidebar />
      <main className="lg:pl-64 pt-16">
        {data.rol === "admin" ? (
          <DashboardAdmin data={data} refreshing={refreshing} onRefresh={() => loadDashboard(true)} />
        ) : data.rol === "responsable_departamento" ? (
          <DashboardDepartamento data={data} refreshing={refreshing} onRefresh={() => loadDashboard(true)} />
        ) : (
          <DashboardArea data={data} user={user} refreshing={refreshing} onRefresh={() => loadDashboard(true)} />
        )}
      </main>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// COMPONENTES COMUNES
// ═══════════════════════════════════════════════════════════════

function StatCard({ label, value, icon: Icon, color, bg }: any) {
  return (
    <Card className="border-none shadow-sm hover:shadow-md transition-all duration-300 overflow-hidden group">
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[10px] font-bold uppercase text-muted-foreground tracking-widest mb-1 group-hover:text-primary transition-colors">
              {label}
            </p>
            <p className="text-3xl font-black text-primary">{value}</p>
          </div>
          <div className={cn(bg, color, "p-4 rounded-2xl shadow-inner group-hover:scale-110 transition-transform")}>
            <Icon className="w-6 h-6" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════
// DASHBOARD ADMIN
// ═══════════════════════════════════════════════════════════════

function DashboardAdmin({ data, refreshing, onRefresh }: { data: any; refreshing: boolean; onRefresh: () => void }) {
  const [departamentosAbiertos, setDepartamentosAbiertos] = useState<number[]>([]);
  const alternarDepartamento = (departamentoId: number) => {
    setDepartamentosAbiertos((actuales) => (
      actuales.includes(departamentoId)
        ? actuales.filter((id) => id !== departamentoId)
        : [...actuales, departamentoId]
    ));
  };
  const stats = [
    { label: "Departamentos", value: data.resumen.total_departamentos, icon: Building2, color: "text-blue-600", bg: "bg-blue-50" },
    { label: "Áreas", value: data.resumen.total_areas, icon: Award, color: "text-indigo-600", bg: "bg-indigo-50" },
    { label: "Profesores", value: data.resumen.total_profesores, icon: Users, color: "text-purple-600", bg: "bg-purple-50" },
    { label: "Actividades", value: data.resumen.total_actividades, icon: BookOpen, color: "text-emerald-600", bg: "bg-emerald-50" },
  ];

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-6 md:space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-primary rounded-lg">
              <LayoutDashboard className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-2xl md:text-3xl font-black tracking-tight text-primary">Panel de Control Global</h1>
          </div>
          <p className="text-sm md:text-base text-muted-foreground font-medium">Gestión estratégica de la ordenación universitaria</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onRefresh} disabled={refreshing} className="bg-white">
            <RefreshCw className={cn("w-4 h-4 mr-2", refreshing && "animate-spin")} /> Sincronizar
          </Button>
          <ResetOrdenacionAlcanceDialog onReset={onRefresh} />
          <Link href="/eleccion">
            <Button size="sm" className="bg-primary hover:bg-primary/90 shadow-xl shadow-primary/20">
              Gestión de Turnos <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </Link>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
        {stats.map((stat) => (
          <StatCard key={stat.label} {...stat} />
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 md:gap-8">
        {/* Progreso Principal */}
        <Card className="lg:col-span-2 border-none shadow-sm overflow-hidden bg-white">
          <CardHeader className="pb-2 border-b border-gray-50">
            <div className="flex justify-between items-center">
              <div>
                <CardTitle className="text-lg font-bold text-primary">Estado de la Ordenación</CardTitle>
                <CardDescription className="font-medium">
                  {formatearHoras(data.resumen.horas_asignadas)}h de {formatearHoras(data.resumen.total_horas_actividades)}h asignadas globalmente
                </CardDescription>
              </div>
              <div className="text-right">
                <span className="text-3xl font-black text-primary">{data.resumen.progreso_ordenacion}%</span>
                <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-tighter">completado</p>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-8 pt-6">
            <div className="space-y-3">
              <Progress value={data.resumen.progreso_ordenacion} className="h-4 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-primary to-indigo-600 transition-all duration-1000" />
              </Progress>
              <div className="flex justify-between text-[10px] font-black uppercase text-muted-foreground tracking-widest px-1">
                <span>Fase Inicial</span>
                <span className="text-primary">Objetivo Institucional</span>
              </div>
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-6 bg-gradient-to-br from-gray-50 to-white rounded-3xl border border-gray-100 shadow-inner group">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-blue-100 rounded-xl text-blue-600">
                    <Scale className="w-5 h-5" />
                  </div>
                  <p className="text-[10px] font-black uppercase text-muted-foreground tracking-widest">Capacidad Docente</p>
                </div>
                <p className="text-3xl font-black text-primary">{formatearHoras(data.resumen.total_horas_profesores)}h</p>
              </div>
              <div className="p-6 bg-gradient-to-br from-emerald-50/50 to-white rounded-3xl border border-emerald-100/50 shadow-inner">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-emerald-100 rounded-xl text-emerald-600">
                    <Zap className="w-5 h-5" />
                  </div>
                  <p className="text-[10px] font-black uppercase text-emerald-700 tracking-widest">Asignación Real</p>
                </div>
                <p className="text-3xl font-black text-emerald-700">{formatearHoras(data.resumen.horas_asignadas)}h</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Info Lateral */}
        <Card className="border-none shadow-sm bg-primary text-white overflow-hidden relative">
          <div className="absolute top-0 right-0 p-8 opacity-10 pointer-events-none">
            <Building2 className="w-32 h-32" />
          </div>
          <CardHeader>
            <CardTitle className="text-lg font-bold flex items-center gap-2">
              <AlertCircle className="w-5 h-5" />
              Resumen Ejecutivo
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="p-4 bg-white/10 backdrop-blur-md rounded-2xl border border-white/20">
              <p className="text-sm font-medium leading-relaxed">
                El proceso de ordenación docente para el próximo curso académico se encuentra en una fase avanzada. 
                Actualmente contamos con {data.resumen.total_profesores} docentes participando.
              </p>
            </div>
            <div className="flex items-center gap-4 p-4">
              <div className="flex -space-x-2">
                {[1,2,3].map(i => (
                  <div key={i} className="w-8 h-8 rounded-full border-2 border-primary bg-gray-200" />
                ))}
              </div>
              <p className="text-[10px] font-bold uppercase tracking-widest">Equipos Directivos Activos</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Desglose de Departamentos */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 px-1">
          <Building2 className="w-5 h-5 text-primary" />
          <h2 className="text-xl font-black text-primary uppercase tracking-tight">Estructura Orgánica</h2>
        </div>
        
        <div className="grid grid-cols-1 gap-6">
          {data.departamentos.map((depto: any) => (
            <Card key={depto.id} className="border-none shadow-sm overflow-hidden bg-white hover:ring-1 hover:ring-primary/10 transition-all">
              <div className="flex flex-col md:flex-row">
                <div className="md:w-64 bg-gray-50 p-6 border-r border-gray-100 flex flex-col justify-between">
                  <div>
                    <Badge variant="outline" className="mb-2 bg-white text-[10px] font-bold tracking-widest uppercase">Dept. {depto.codigo}</Badge>
                    <h3 className="text-lg font-black text-primary leading-tight">{depto.nombre}</h3>
                  </div>
                  <div className="mt-4 space-y-2">
                    <div className="flex justify-between text-[10px] font-bold uppercase text-muted-foreground">
                      <span>Áreas</span>
                      <span className="text-primary">{depto.num_areas}</span>
                    </div>
                    <div className="flex justify-between text-[10px] font-bold uppercase text-muted-foreground">
                      <span>Docentes</span>
                      <span className="text-primary">{depto.num_profesores}</span>
                    </div>
                  </div>
                </div>
                
                <div className="flex-1 p-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 items-center">
                  <div className="space-y-2">
                    <p className="text-[10px] font-black uppercase text-muted-foreground tracking-widest">Capacidad</p>
                    <p className="text-xl font-bold">{formatearHoras(depto.horas_profesores)}h</p>
                  </div>
                  <div className="space-y-2">
                    <p className="text-[10px] font-black uppercase text-muted-foreground tracking-widest">Demanda</p>
                    <p className="text-xl font-bold">{formatearHoras(depto.horas_actividades)}h</p>
                  </div>
                  <div className="lg:col-span-2 space-y-3">
                    <div className="flex justify-between items-end">
                      <p className="text-[10px] font-black uppercase text-muted-foreground tracking-widest">Carga Asignada</p>
                      <span className="text-xs font-bold text-primary">{(depto.horas_asignadas / depto.horas_actividades * 100 || 0).toFixed(0)}%</span>
                    </div>
                    <Progress value={(depto.horas_asignadas / depto.horas_actividades * 100 || 0)} className="h-2" />
                  </div>
                </div>
              </div>
              <div className="border-t border-gray-100 bg-gray-50/40 px-6 py-3">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => alternarDepartamento(depto.id)}
                  className="w-full justify-between text-primary hover:bg-white"
                >
                  <span>Ver ordenación por áreas</span>
                  {departamentosAbiertos.includes(depto.id)
                    ? <ChevronUp className="h-4 w-4" />
                    : <ChevronDown className="h-4 w-4" />}
                </Button>
              </div>
              {departamentosAbiertos.includes(depto.id) && (
                <CardContent className="grid grid-cols-1 gap-3 bg-white p-4 md:grid-cols-2 lg:grid-cols-3">
                  {(depto.areas ?? []).map((area: any) => (
                    <div key={area.id} className="rounded-xl border border-gray-100 bg-gray-50/60 p-4">
                      <div className="mb-3 flex items-start justify-between gap-3">
                        <div>
                          <Badge variant="outline" className="mb-1 text-[10px]">{area.codigo}</Badge>
                          <p className="font-bold text-primary">{area.nombre}</p>
                        </div>
                        <span className="text-sm font-black text-primary">{area.progreso}%</span>
                      </div>
                      <Progress value={area.progreso} className="mb-3 h-2" />
                      <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                        <span>{formatearHoras(area.horas_asignadas)}h / {formatearHoras(area.horas_actividades)}h</span>
                        <span className="text-right">{formatearHoras(area.horas_pendientes)}h pendientes</span>
                        <span>{area.num_profesores} profesores</span>
                        <span className="text-right">{area.num_actividades} actividades</span>
                      </div>
                    </div>
                  ))}
                  {(depto.areas ?? []).length === 0 && (
                    <p className="text-sm text-muted-foreground">No hay áreas en este departamento.</p>
                  )}
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// DASHBOARD RESPONSABLE DEPARTAMENTO
// ═══════════════════════════════════════════════════════════════

function DashboardDepartamento({ data, refreshing, onRefresh }: { data: any; refreshing: boolean; onRefresh: () => void }) {
  const balance = data.resumen.total_horas_profesores - data.resumen.total_horas_actividades;
  const nombreDepartamento = String(data.departamento.nombre || "").trim();
  const tituloDepartamento = /^departamento\s+de\s+/i.test(nombreDepartamento)
    ? nombreDepartamento
    : `Departamento de ${nombreDepartamento}`;
  const stats = [
    { label: "Áreas Activas", value: data.resumen.total_areas, icon: Award, color: "text-blue-600", bg: "bg-blue-50" },
    { label: "Claustro", value: data.resumen.total_profesores, icon: Users, color: "text-purple-600", bg: "bg-purple-50" },
    { label: "Actividades", value: data.resumen.total_actividades, icon: BookOpen, color: "text-indigo-600", bg: "bg-indigo-50" },
    { 
      label: "Balance Neto", 
      value: `${balance > 0 ? "+" : ""}${balance.toFixed(1)}h`, 
      icon: Scale, 
      color: balance >= 0 ? "text-emerald-600" : "text-destructive", 
      bg: balance >= 0 ? "bg-emerald-50" : "bg-red-50" 
    },
  ];

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-6 md:space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-primary rounded-2xl shadow-lg shadow-primary/20">
              <Building2 className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-2xl md:text-3xl font-black tracking-tight text-primary">
              {tituloDepartamento}
            </h1>
          </div>
          <p className="text-sm md:text-base text-muted-foreground font-medium pl-1">Supervisión y control de áreas departamentales</p>
        </div>
        <Button variant="outline" size="sm" onClick={onRefresh} disabled={refreshing} className="bg-white shadow-sm">
          <RefreshCw className={cn("w-4 h-4 mr-2", refreshing && "animate-spin")} /> Refrescar
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
        {stats.map((stat) => (
          <StatCard key={stat.label} {...stat} />
        ))}
      </div>

      {/* Desglose por área */}
      <div className="space-y-6">
        <div className="flex items-center justify-between px-1">
          <h2 className="text-lg font-black text-primary uppercase tracking-widest flex items-center gap-2">
            <Layers className="w-5 h-5" />
            Control de Áreas
          </h2>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {data.areas.map((area: any) => (
            <Card key={area.id} className="border-none shadow-sm overflow-hidden bg-white hover:shadow-md transition-all group">
              <CardHeader className="bg-gray-50/50 border-b border-gray-100 pb-4">
                <div className="flex justify-between items-start">
                  <div className="space-y-1">
                    <CardTitle className="text-lg font-black text-primary">{area.nombre}</CardTitle>
                    <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Código: {area.id}</p>
                  </div>
                  <Badge className="bg-primary/10 text-primary border-none text-[10px] font-black uppercase tracking-widest px-3">
                    {area.progreso}% Asignado
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="p-6 space-y-6">
                <div className="grid grid-cols-2 gap-6">
                  <div className="space-y-1">
                    <p className="text-[10px] font-black uppercase text-muted-foreground tracking-widest">Capacidad de Área</p>
                    <p className="text-2xl font-black text-primary">{formatearHoras(area.horas_profesores)}h</p>
                  </div>
                  <div className="space-y-1 text-right">
                    <p className="text-[10px] font-black uppercase text-muted-foreground tracking-widest">Demanda Real</p>
                    <p className="text-2xl font-black text-primary">{formatearHoras(area.horas_actividades)}h</p>
                  </div>
                </div>

                <div className="space-y-3 pt-2">
                  <div className="flex justify-between text-[10px] font-black uppercase text-muted-foreground tracking-widest">
                    <span>Progreso Global</span>
                    <span className="text-primary">{formatearHoras(area.horas_asignadas)}h / {formatearHoras(area.horas_actividades)}h</span>
                  </div>
                  <Progress value={area.progreso} className="h-2.5 shadow-inner" />
                </div>
                
                <div className="flex items-center gap-4 pt-4 border-t border-gray-50">
                  <div className="flex items-center gap-1.5 text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                    <Users className="w-3.5 h-3.5" /> {area.num_profesores} Profs.
                  </div>
                  <div className="flex items-center gap-1.5 text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                    <BookOpen className="w-3.5 h-3.5" /> {area.num_actividades} Activs.
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// DASHBOARD ÁREA
// ═══════════════════════════════════════════════════════════════

function DashboardArea({ data, user, refreshing, onRefresh }: { data: any; user: any; refreshing: boolean; onRefresh: () => void }) {
  if (!data.area) {
    return <div className="p-8 text-center text-muted-foreground">No hay datos de área disponibles.</div>;
  }

  const stats = [
    { label: "Colegas", value: data.resumen.total_profesores, icon: Users, color: "text-blue-600", bg: "bg-blue-50" },
    { label: "Actividades", value: data.resumen.total_actividades, icon: BookOpen, color: "text-purple-600", bg: "bg-purple-50" },
    { label: "Capacidad", value: `${formatearHoras(data.resumen.total_horas_profesores)}h`, icon: Scale, color: "text-indigo-600", bg: "bg-indigo-50" },
    { label: "Demanda", value: `${formatearHoras(data.resumen.total_horas_actividades)}h`, icon: TrendingUp, color: "text-emerald-600", bg: "bg-emerald-50" },
  ];

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-6 md:space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-primary rounded-2xl shadow-lg shadow-primary/20">
              <Layers className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-2xl md:text-3xl font-black tracking-tight text-primary">
              {/^[áa]rea\b/i.test(data.area.nombre.trim())
                ? data.area.nombre.trim()
                : `Área de ${data.area.nombre.trim()}`}
            </h1>
          </div>
          <p className="text-sm md:text-base text-muted-foreground font-medium pl-1">
            {user?.rol === "Profesor" ? "Tu espacio de ordenación" : "Gestión operativa del área"}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onRefresh} className="bg-white">
            <RefreshCw className={cn("w-4 h-4", refreshing && "animate-spin")} />
          </Button>
          {user?.rol !== "PSI" && (
            <Link href="/eleccion">
              <Button size="sm" className="bg-primary hover:bg-primary/90 shadow-xl shadow-primary/20">
                Acceder a Elección <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
        {stats.map((stat) => (
          <StatCard key={stat.label} {...stat} />
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Progreso del Área */}
        <Card className="lg:col-span-2 border-none shadow-sm overflow-hidden bg-white">
          <CardHeader className="pb-2 border-b border-gray-50">
            <div className="flex justify-between items-center">
              <div>
                <CardTitle className="text-lg font-bold text-primary">Estado de Asignación del Área</CardTitle>
                <CardDescription className="font-medium">
                  {formatearHoras(data.resumen.horas_asignadas)}h de {formatearHoras(data.resumen.total_horas_actividades)}h cubiertas
                </CardDescription>
              </div>
              <Badge className="bg-emerald-50 text-emerald-700 border-none font-black text-xs px-4 py-1">
                {data.resumen.progreso_ordenacion}% CUBIERTO
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-6">
            <div className="space-y-6">
              <div className="space-y-2">
                <Progress value={data.resumen.progreso_ordenacion} className="h-3 rounded-full" />
                <div className="flex justify-between text-[10px] font-black uppercase text-muted-foreground tracking-widest">
                  <span>Pendiente</span>
                  <span className="text-primary">Finalizado</span>
                </div>
              </div>

              {/* Listado de profesores en el área */}
              {data.profesores && (
                <div className="space-y-4 pt-4">
                  <h3 className="text-[10px] font-black uppercase text-muted-foreground tracking-widest border-b pb-2">Estado de Colegas</h3>
                  <div className="grid grid-cols-1 gap-3">
                    {data.profesores.map((prof: any) => (
                      <div key={prof.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl hover:bg-white hover:ring-1 hover:ring-primary/10 transition-all group">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs uppercase">
                            {prof.nombre_completo.substring(0, 2)}
                          </div>
                          <div>
                            <p className="text-sm font-bold text-primary">{prof.nombre_completo}</p>
                            <p className="text-[10px] font-bold text-muted-foreground uppercase">{prof.categoria}</p>
                          </div>
                        </div>
                        <div className="text-right flex items-center gap-4">
                          <div className="hidden sm:block">
                            <p className="text-[10px] font-black text-muted-foreground uppercase">Restante</p>
                            <p className="text-sm font-black text-primary">{formatearHoras(prof.horas_restantes)}h</p>
                          </div>
                          <div className="w-16">
                             <Progress value={prof.progreso} className="h-1.5" />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Info y Distribución */}
        <Card className="border-none shadow-sm bg-white overflow-hidden">
          <CardHeader className="border-b border-gray-50 pb-4">
            <CardTitle className="text-lg font-bold text-primary">Distribución de Carga</CardTitle>
            <CardDescription className="text-[10px] font-bold uppercase tracking-widest">Por tipología docente</CardDescription>
          </CardHeader>
          <CardContent className="p-6">
            {data.actividades_por_tipo && (
              <div className="space-y-4">
                {Object.entries(data.actividades_por_tipo).map(([tipo, stats]: [string, any]) => (
                  <div key={tipo} className="space-y-2">
                    <div className="flex justify-between items-center text-[10px] font-bold uppercase">
                      <span className="text-muted-foreground tracking-widest">{tipo}</span>
                      <span className="text-primary">{formatearHoras(stats.horas)}h</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-primary transition-all duration-1000" 
                        style={{ width: `${(stats.horas / data.resumen.total_horas_actividades) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-8 p-4 bg-blue-50 rounded-2xl border border-blue-100">
               <div className="flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-blue-600 shrink-0" />
                  <p className="text-xs text-blue-800 font-medium leading-relaxed">
                    Recuerda que los turnos de ordenación se calculan basándose en la categoría y antigüedad de los docentes del área.
                  </p>
               </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
