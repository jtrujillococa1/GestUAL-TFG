"use client";

import { ChangeEvent, useRef, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiFetch } from "@/lib/api-client";
import {
  ArrowRight,
  BookOpen,
  Building2,
  CalendarClock,
  CheckCircle2,
  FileSpreadsheet,
  Layers,
  ShieldCheck,
  UsersRound,
} from "lucide-react";

type Resumen = {
  filas_csv: number;
  departamentos: string[];
  cursos_academicos: string[];
  areas: string[];
  actividades_por_area: number;
  profesores_origen: number;
  lineas_resultado_referencia: number;
  horarios_sinteticos: number;
  horarios_pendientes_de_confirmar: number;
  profesores_con_horas_de_reparto_variables: number;
  requiere_revision_humana: string[];
};

type Plan = {
  departamentos: { codigo: string; nombre: string; estado: string }[];
  areas: { codigo: string; nombre: string; departamento_codigo: string; estado: string }[];
  actividades: Record<string, number>;
  profesores_a_crear_sin_asignacion: number;
  lineas_resultado_referencia: number;
  repartos_confirmados_a_crear: number;
  modo: string;
  importacion_habilitada: boolean;
  motivo_bloqueo: string;
};

type ResultadoEscenario = {
  ok: boolean;
  lote_id: number;
  curso_academico: string;
  departamentos: number;
  areas: number;
  actividades: number;
  profesores: number;
  repartos_confirmados: number;
  mensaje: string;
  cuentas_responsables: {
    nombre: string;
    email: string;
    rol: "responsable_departamento" | "responsable_area";
    area_codigo: string;
  }[];
};

function mensajeDeError(causa: unknown, mensajePorDefecto: string): string {
  if (causa instanceof Error && causa.message) return causa.message;
  const detalle = (causa as { response?: { data?: { detail?: unknown } } })
    .response?.data?.detail;

  if (typeof detalle === "string") return detalle;
  if (Array.isArray(detalle)) {
    const mensajes = detalle
      .map((elemento) => typeof elemento?.msg === "string" ? elemento.msg : null)
      .filter((mensaje): mensaje is string => mensaje !== null);
    if (mensajes.length > 0) return mensajes.join(" ");
  }
  return mensajePorDefecto;
}

export default function ImportacionPage() {
  const [fichero, setFichero] = useState<File | null>(null);
  const [resumen, setResumen] = useState<Resumen | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [passwordTemporal, setPasswordTemporal] = useState("");
  const [confirmado, setConfirmado] = useState(false);
  const [resultado, setResultado] = useState<ResultadoEscenario | null>(null);
  const requestId = useRef(0);

  const seleccionar = (evento: ChangeEvent<HTMLInputElement>) => {
    requestId.current += 1;
    setFichero(evento.target.files?.[0] ?? null);
    setResumen(null);
    setPlan(null);
    setResultado(null);
    setPasswordTemporal("");
    setConfirmado(false);
    setError(null);
  };

  const crearEscenario = async () => {
    if (!fichero || !plan?.importacion_habilitada || !confirmado) return;
    if (passwordTemporal.length < 12) {
      setError("La contraseña temporal debe tener al menos 12 caracteres.");
      return;
    }
    const currentRequest = ++requestId.current;
    setCargando(true);
    setError(null);
    try {
      const datos = new FormData();
      datos.append("fichero", fichero);
      datos.append("password_temporal", passwordTemporal);
      datos.append("confirmar", "true");
      const respuesta = await apiFetch<ResultadoEscenario>("/importacion/crear-escenario-prueba", {
        method: "POST",
        body: datos,
      });
      if (currentRequest !== requestId.current) return;
      setResultado(respuesta);
      setPasswordTemporal("");
    } catch (causa) {
      if (currentRequest !== requestId.current) return;
      setError(mensajeDeError(causa, "No se pudo crear el escenario de prueba."));
    } finally {
      if (currentRequest === requestId.current) setCargando(false);
    }
  };

  const generarPlan = async () => {
    if (!fichero) return;
    const currentRequest = ++requestId.current;
    setCargando(true);
    setError(null);
    try {
      const datos = new FormData();
      datos.append("fichero", fichero);
      const respuesta = await apiFetch<Plan>("/importacion/planificar", {
        method: "POST",
        body: datos,
        notifyDataChange: false,
      });
      if (currentRequest !== requestId.current) return;
      setPlan(respuesta);
    } catch (causa) {
      if (currentRequest !== requestId.current) return;
      setError(mensajeDeError(causa, "No se pudo generar el plan."));
    } finally {
      if (currentRequest === requestId.current) setCargando(false);
    }
  };

  const previsualizar = async () => {
    if (!fichero) return;
    const currentRequest = ++requestId.current;
    setCargando(true);
    setError(null);
    try {
      const datos = new FormData();
      datos.append("fichero", fichero);
      const respuesta = await apiFetch<Resumen>("/importacion/previsualizar", {
        method: "POST",
        body: datos,
        notifyDataChange: false,
      });
      if (currentRequest !== requestId.current) return;
      setResumen(respuesta);
    } catch (causa) {
      if (currentRequest !== requestId.current) return;
      setError(mensajeDeError(causa, "No se pudo validar el CSV."));
    } finally {
      if (currentRequest === requestId.current) setCargando(false);
    }
  };

  const pasosFlujo = [
    {
      numero: "01", titulo: "Departamento", descripcion: "Crea el departamento y designa a quien lo coordina.", href: "/departamentos", accion: "Gestionar departamentos", icono: Building2, color: "bg-blue-50 text-blue-700 border-blue-100",
    },
    {
      numero: "02", titulo: "Áreas y responsables", descripcion: "Asocia cada área al departamento y asigna sus responsables.", href: "/areas", accion: "Configurar áreas", icono: Layers, color: "bg-indigo-50 text-indigo-700 border-indigo-100",
    },
    {
      numero: "03", titulo: "Profesorado y cuentas", descripcion: "Da de alta perfiles, áreas de pertenencia y cargas de elección.", href: "/profesores", accion: "Añadir profesorado", icono: UsersRound, color: "bg-violet-50 text-violet-700 border-violet-100",
    },
    {
      numero: "04", titulo: "Actividades y horario", descripcion: "Añade asignaturas, grupos de teoría o prácticas y sus franjas semanales.", href: "/actividades", accion: "Crear actividades", icono: CalendarClock, color: "bg-emerald-50 text-emerald-700 border-emerald-100",
    },
    {
      numero: "05", titulo: "Ordenación docente", descripcion: "Abre las colas de área para que el profesorado elija sus actividades.", href: "/eleccion", accion: "Ir a ordenación", icono: CheckCircle2, color: "bg-amber-50 text-amber-700 border-amber-100",
    },
  ];

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <Sidebar />
      <main className="lg:pl-64 pt-16 p-6 space-y-6">
        <div className="max-w-3xl">
          <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-primary">Preparación del curso</p>
          <h1 className="text-2xl font-black text-primary md:text-3xl">Carga manual de datos</h1>
          <p className="mt-2 text-muted-foreground">Configura el catálogo directamente en la aplicación. El CSV es solo una utilidad opcional de migración o de pruebas, nunca el paso normal para iniciar una ordenación.</p>
        </div>
        <Card className="overflow-hidden border-primary/10 shadow-sm">
          <CardHeader className="border-b bg-gradient-to-r from-primary/[0.06] via-primary/[0.02] to-transparent pb-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 text-xl text-primary"><ShieldCheck className="h-5 w-5" /> Flujo real recomendado</CardTitle>
                <CardDescription className="mt-2 max-w-2xl">Sigue estas etapas en orden. Cada una deja lista la información que necesitará la siguiente y evita crear docentes o actividades sin ámbito de ordenación.</CardDescription>
              </div>
              <div className="rounded-full border border-primary/15 bg-white px-3 py-1 text-xs font-semibold text-primary">5 pasos · datos manuales</div>
            </div>
          </CardHeader>
          <CardContent className="p-4 md:p-6">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              {pasosFlujo.map((paso) => {
                const Icono = paso.icono;
                return (
                  <Link key={paso.numero} href={paso.href} className="group relative rounded-xl border bg-card p-4 transition-all hover:-translate-y-0.5 hover:border-primary/35 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
                    <div className="mb-4 flex items-start justify-between gap-3">
                      <div className={`rounded-lg border p-2 ${paso.color}`}><Icono className="h-5 w-5" /></div>
                      <span className="text-xs font-black tracking-wider text-muted-foreground">{paso.numero}</span>
                    </div>
                    <h2 className="font-bold text-primary">{paso.titulo}</h2>
                    <p className="mt-1.5 min-h-14 text-xs leading-relaxed text-muted-foreground">{paso.descripcion}</p>
                    <span className="mt-4 flex items-center gap-1 text-xs font-semibold text-primary">{paso.accion}<ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" /></span>
                  </Link>
                );
              })}
            </div>
            <div className="mt-5 flex gap-3 rounded-lg bg-muted/60 p-3 text-sm text-muted-foreground">
              <BookOpen className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <p>El resultado final del curso será la ordenación confirmada. No asignes profesores a grupos al dar de alta el catálogo: esa relación se crea en el paso 5.</p>
            </div>
          </CardContent>
        </Card>
        <Card className="border-dashed">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2 text-base"><FileSpreadsheet className="h-5 w-5 text-primary" /> Importación CSV opcional</CardTitle>
            <CardDescription>Úsala únicamente para migrar o crear un escenario de prueba desde un catálogo ya estructurado. Las adjudicaciones profesor–grupo no se importan.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center">
            <Input type="file" accept=".csv,text/csv" onChange={seleccionar} disabled={cargando} />
            <Button onClick={previsualizar} disabled={!fichero || cargando}>
              {cargando ? "Validando…" : "Previsualizar"}
            </Button>
            <Button variant="outline" onClick={generarPlan} disabled={!fichero || cargando}>
              Generar plan
            </Button>
          </CardContent>
        </Card>
        {error && <p className="rounded-md border border-destructive p-4 text-destructive">{error}</p>}
        {resumen && (
          <Card>
            <CardHeader><CardTitle>Resultado de la validación</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  ["Filas", resumen.filas_csv], ["Actividades por área", resumen.actividades_por_area],
                  ["Profesores de origen", resumen.profesores_origen], ["Líneas de resultado", resumen.lineas_resultado_referencia],
                ].map(([etiqueta, valor]) => <div key={String(etiqueta)} className="rounded-md bg-muted p-3"><p className="text-sm text-muted-foreground">{etiqueta}</p><p className="text-xl font-semibold">{valor}</p></div>)}
              </div>
              <p><strong>Departamento:</strong> {resumen.departamentos.join(", ")}</p>
              <p><strong>Curso académico:</strong> {resumen.cursos_academicos.join(", ")}</p>
              <p><strong>Áreas:</strong> {resumen.areas.join(", ")}</p>
              <p className="text-amber-700"><strong>Horarios sintéticos:</strong> {resumen.horarios_sinteticos}. Se usarán para visualizar y detectar solapes, pero siguen pendientes de confirmación oficial.</p>
              <p className="text-amber-700"><strong>Cargas docentes:</strong> para la prueba se sumarán las horas de reparto de cada profesor; {resumen.profesores_con_horas_de_reparto_variables} profesores tienen líneas con importes distintos.</p>
              <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {resumen.requiere_revision_humana.map((aviso) => <li key={aviso}>{aviso}</li>)}
              </ul>
            </CardContent>
          </Card>
        )}
        {plan && (
          <Card>
            <CardHeader><CardTitle>Plan de importación</CardTitle><CardDescription>Revisa el alcance antes de crear el escenario.</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-md bg-muted p-3"><p className="text-sm text-muted-foreground">Departamentos</p><p>{plan.departamentos.filter((x) => x.estado === "CREAR").length} por crear · {plan.departamentos.filter((x) => x.estado === "CONFLICTO").length} conflictos</p></div>
                <div className="rounded-md bg-muted p-3"><p className="text-sm text-muted-foreground">Áreas</p><p>{plan.areas.filter((x) => x.estado === "CREAR").length} por crear · {plan.areas.filter((x) => x.estado === "CONFLICTO").length} conflictos</p></div>
                <div className="rounded-md bg-muted p-3"><p className="text-sm text-muted-foreground">Actividades</p><p>{plan.actividades.CREAR ?? 0} por crear · {plan.actividades.EXISTENTE ?? 0} existentes</p></div>
              </div>
              <p><strong>Profesores a crear:</strong> {plan.profesores_a_crear_sin_asignacion} (sin grupos asignados).</p>
              <p><strong>Repartos confirmados a crear:</strong> {plan.repartos_confirmados_a_crear}. Los grupos se adjudican durante la ordenación.</p>
              <p className="text-amber-700"><strong>Al crear el escenario:</strong> {plan.motivo_bloqueo}</p>
              {plan.importacion_habilitada && !resultado && (
                <div className="space-y-3 rounded-md border border-amber-500/40 bg-amber-50 p-4">
                  <p className="text-sm">Usa una contraseña temporal para las cuentas generadas. Guárdala de forma segura: no se mostrará ni se conservará aquí.</p>
                  <Input
                    type="password"
                    autoComplete="new-password"
                    minLength={12}
                    value={passwordTemporal}
                    onChange={(evento) => setPasswordTemporal(evento.target.value)}
                    placeholder="Contraseña temporal (mínimo 12 caracteres)"
                  />
                  <label className="flex items-start gap-2 text-sm">
                    <input
                      className="mt-1"
                      type="checkbox"
                      checked={confirmado}
                      onChange={(evento) => setConfirmado(evento.target.checked)}
                    />
                    <span>Confirmo que es un entorno de prueba y que se crearán las cuentas, el catálogo y los horarios sintéticos indicados.</span>
                  </label>
                  <Button onClick={crearEscenario} disabled={cargando || !confirmado || passwordTemporal.length < 12}>
                    {cargando ? "Creando escenario…" : "Crear escenario de prueba"}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        )}
        {resultado && (
          <Card>
            <CardHeader><CardTitle>Escenario de prueba creado</CardTitle><CardDescription>{resultado.mensaje}</CardDescription></CardHeader>
            <CardContent className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  ["Actividades", resultado.actividades], ["Profesores", resultado.profesores],
                  ["Áreas", resultado.areas], ["Repartos confirmados", resultado.repartos_confirmados],
                ].map(([etiqueta, valor]) => <div key={String(etiqueta)} className="rounded-md bg-muted p-3"><p className="text-sm text-muted-foreground">{etiqueta}</p><p className="text-xl font-semibold">{valor}</p></div>)}
              </div>
              <p className="text-sm text-muted-foreground">Lote {resultado.lote_id} · curso {resultado.curso_academico}. Los grupos no se han asociado a ningún profesor.</p>
              <div className="rounded-md border p-3 text-sm">
                <p className="mb-2 font-medium">Cuentas para comprobar permisos</p>
                <ul className="space-y-1">
                  {resultado.cuentas_responsables.map((cuenta) => (
                    <li key={cuenta.email}>{cuenta.email} · {cuenta.rol === "responsable_departamento" ? "responsable de departamento" : `responsable del área ${cuenta.area_codigo}`}</li>
                  ))}
                </ul>
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
