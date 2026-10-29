"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { toast } from "@/hooks/use-toast";
import {
  getCachedUser,
  getCurrentProfessor,
  updateCachedProfessor,
  updateCachedUser,
} from "@/lib/auth";
import {
  formatearFecha,
  getLabelDisponibilidadCuatrimestre,
  updateMiPrioridadesAsignaturas,
  updateMiDisponibilidadCuatrimestre,
} from "@/lib/profesores";
import { getActividades, type ApiActividad } from "@/lib/actividades";
import { getMiUsuario, updateMiUsuario, type UsuarioPerfil } from "@/lib/usuarios";
import type { Professor } from "@/lib/types";
import { ArrowDown, ArrowUp, BookOpen, ListOrdered, Loader2, LockKeyhole, Save, UserRound, X } from "lucide-react";

export default function PerfilPage() {
  const [usuario, setUsuario] = useState<UsuarioPerfil | null>(null);
  const [profesor, setProfesor] = useState<Professor | null>(null);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [nombre, setNombre] = useState("");
  const [apellidos, setApellidos] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [repetirPassword, setRepetirPassword] = useState("");
  const [disponibilidadCuatrimestre, setDisponibilidadCuatrimestre] = useState<"PRIMERO" | "SEGUNDO" | "AMBOS">("AMBOS");
  const [asignaturas, setAsignaturas] = useState<ApiActividad[]>([]);
  const [prioridadesAsignaturas, setPrioridadesAsignaturas] = useState<string[]>([]);

  const cargarPerfil = async () => {
    setCargando(true);
    try {
      const datosUsuario = await getMiUsuario();
      const datosProfesor = await getCurrentProfessor();
      setUsuario(datosUsuario);
      setProfesor(datosProfesor);
      setPrioridadesAsignaturas((datosProfesor?.prioridades_asignaturas ?? []).map((item) => item.codigo));
      setDisponibilidadCuatrimestre(datosProfesor?.disponibilidad_cuatrimestre ?? "AMBOS");
      setNombre(datosUsuario.nombre);
      setApellidos(datosUsuario.apellidos);
      setEmail(datosUsuario.email);
      updateCachedUser({ ...datosUsuario, id: String(datosUsuario.id) });
      updateCachedProfessor(datosProfesor);
      if (datosProfesor) {
        const actividades = await getActividades().catch(() => []);
        setAsignaturas(actividades);
      }
    } catch (error) {
      toast({
        title: "No se pudo cargar tu perfil",
        description: error instanceof Error ? error.message : "Inténtalo de nuevo.",
        variant: "destructive",
      });
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargarPerfil();
  }, []);

  const asignaturasPriorizables = useMemo(() => {
    const areasProfesor = new Set(profesor?.area_ids ?? []);
    const porCodigo = new Map<string, ApiActividad>();
    asignaturas.forEach((actividad) => {
      const areasActividad = actividad.area_ids ?? (actividad.area_id ? [actividad.area_id] : []);
      if (areasActividad.some((areaId) => areasProfesor.has(areaId)) && !porCodigo.has(actividad.codigo)) {
        porCodigo.set(actividad.codigo, actividad);
      }
    });
    return [...porCodigo.values()].sort((a, b) =>
      (a.nombre_asignatura || a.codigo).localeCompare(b.nombre_asignatura || b.codigo, "es"),
    );
  }, [asignaturas, profesor?.area_ids]);
  const asignaturaPorCodigo = useMemo(
    () => new Map(asignaturasPriorizables.map((actividad) => [actividad.codigo, actividad])),
    [asignaturasPriorizables],
  );
  const actualizarPrioridades = (siguientes: string[]) => setPrioridadesAsignaturas([...new Set(siguientes)]);

  const guardar = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!usuario) return;
    if (password && password.length < 12) {
      toast({ title: "Contraseña demasiado corta", description: "Debe tener al menos 12 caracteres.", variant: "destructive" });
      return;
    }
    if (password && password !== repetirPassword) {
      toast({ title: "Las contraseñas no coinciden", variant: "destructive" });
      return;
    }

    const cambios = {
      ...(nombre.trim() !== usuario.nombre ? { nombre: nombre.trim() } : {}),
      ...(apellidos.trim() !== usuario.apellidos ? { apellidos: apellidos.trim() } : {}),
      ...(email.trim() !== usuario.email ? { email: email.trim() } : {}),
      ...(password ? { password } : {}),
    };
    const disponibilidadCambiada = !!profesor
      && disponibilidadCuatrimestre !== profesor.disponibilidad_cuatrimestre;
    const prioridadesActuales = (profesor?.prioridades_asignaturas ?? []).map((item) => item.codigo);
    const prioridadesCambiadas = prioridadesActuales.join("|") !== prioridadesAsignaturas.join("|");
    if (Object.keys(cambios).length === 0 && !disponibilidadCambiada && !prioridadesCambiadas) {
      toast({ title: "No hay cambios que guardar" });
      return;
    }

    setGuardando(true);
    try {
      const actualizado = Object.keys(cambios).length > 0
        ? await updateMiUsuario(usuario.id, cambios)
        : usuario;
      if (disponibilidadCambiada) {
        await updateMiDisponibilidadCuatrimestre(disponibilidadCuatrimestre);
      }
      if (prioridadesCambiadas) {
        await updateMiPrioridadesAsignaturas(prioridadesAsignaturas);
      }
      setUsuario(actualizado);
      setNombre(actualizado.nombre);
      setApellidos(actualizado.apellidos);
      setEmail(actualizado.email);
      setPassword("");
      setRepetirPassword("");
      updateCachedUser({ ...actualizado, id: String(actualizado.id) });
      const perfilDocente = await getCurrentProfessor();
      setProfesor(perfilDocente);
      updateCachedProfessor(perfilDocente);
      toast({ title: "Perfil actualizado", description: "Tus datos personales se han guardado correctamente." });
    } catch (error) {
      toast({
        title: "No se pudo guardar el perfil",
        description: error instanceof Error ? error.message : "Inténtalo de nuevo.",
        variant: "destructive",
      });
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC]">
      <Header />
      <Sidebar />
      <main className="lg:pl-64 pt-16">
        <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-8">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-primary p-3 text-white"><UserRound className="h-6 w-6" /></div>
            <div>
              <h1 className="text-2xl font-black text-primary">Mi perfil</h1>
              <p className="text-sm text-muted-foreground">Consulta y actualiza tus datos personales y de acceso.</p>
            </div>
          </div>

          {cargando ? (
            <Card><CardContent className="flex items-center gap-3 p-8 text-sm text-muted-foreground"><Loader2 className="h-5 w-5 animate-spin" /> Cargando perfil…</CardContent></Card>
          ) : usuario ? (
            <div className="grid gap-6 lg:grid-cols-[1.25fr_.75fr]">
              <Card className="shadow-sm">
                <CardHeader>
                  <CardTitle>Datos personales y acceso</CardTitle>
                  <CardDescription>Estos datos solo los puedes editar tú. El cambio de contraseña es opcional.</CardDescription>
                </CardHeader>
                <CardContent>
                  <form className="space-y-5" onSubmit={guardar}>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-2"><Label htmlFor="nombre">Nombre</Label><Input id="nombre" value={nombre} onChange={(event) => setNombre(event.target.value)} required /></div>
                      <div className="space-y-2"><Label htmlFor="apellidos">Apellidos</Label><Input id="apellidos" value={apellidos} onChange={(event) => setApellidos(event.target.value)} required /></div>
                    </div>
                    <div className="space-y-2"><Label htmlFor="correo">Correo electrónico</Label><Input id="correo" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></div>
                    {profesor && (
                      <div className="space-y-2 rounded-lg border bg-muted/20 p-4">
                        <Label htmlFor="disponibilidad-cuatrimestre">Disponibilidad para impartir</Label>
                        <Select value={disponibilidadCuatrimestre} onValueChange={(value: "PRIMERO" | "SEGUNDO" | "AMBOS") => setDisponibilidadCuatrimestre(value)}>
                          <SelectTrigger id="disponibilidad-cuatrimestre"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="AMBOS">Ambos cuatrimestres</SelectItem>
                            <SelectItem value="PRIMERO">Solo primer cuatrimestre</SelectItem>
                            <SelectItem value="SEGUNDO">Solo segundo cuatrimestre</SelectItem>
                          </SelectContent>
                        </Select>
                        <p className="text-xs text-muted-foreground">La ordenación impedirá elegir actividades que se desarrollen fuera del periodo indicado.</p>
                      </div>
                    )}
                    {profesor && (
                      <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
                        <div className="flex items-start gap-2">
                          <ListOrdered className="mt-0.5 h-4 w-4 text-primary" />
                          <div><Label>Mis prioridades de asignaturas</Label><p className="mt-1 text-xs text-muted-foreground">El orden ayuda a mostrar primero las opciones más adecuadas y a proponer intercambios realistas si hay un conflicto.</p></div>
                        </div>
                        <Select value="" onValueChange={(codigo) => actualizarPrioridades([...prioridadesAsignaturas, codigo])} disabled={!asignaturasPriorizables.length}>
                          <SelectTrigger><SelectValue placeholder={asignaturasPriorizables.length ? "Añadir asignatura" : "No hay asignaturas de tus áreas disponibles"} /></SelectTrigger>
                          <SelectContent>
                            {asignaturasPriorizables.filter((actividad) => !prioridadesAsignaturas.includes(actividad.codigo)).map((actividad) => <SelectItem key={actividad.codigo} value={actividad.codigo}>{actividad.nombre_asignatura || actividad.codigo} · {actividad.codigo}</SelectItem>)}
                          </SelectContent>
                        </Select>
                        {prioridadesAsignaturas.length ? <ol className="space-y-2">{prioridadesAsignaturas.map((codigo, indice) => <li key={codigo} className="flex items-center gap-1 rounded-md border bg-background px-2 py-1.5 text-sm"><span className="w-5 font-semibold text-primary">{indice + 1}</span><span className="min-w-0 flex-1 truncate">{asignaturaPorCodigo.get(codigo)?.nombre_asignatura || codigo}</span><Button type="button" variant="ghost" size="icon" className="h-7 w-7" disabled={!indice} onClick={() => { const siguiente = [...prioridadesAsignaturas]; [siguiente[indice - 1], siguiente[indice]] = [siguiente[indice], siguiente[indice - 1]]; actualizarPrioridades(siguiente); }} aria-label="Subir prioridad"><ArrowUp className="h-3.5 w-3.5" /></Button><Button type="button" variant="ghost" size="icon" className="h-7 w-7" disabled={indice === prioridadesAsignaturas.length - 1} onClick={() => { const siguiente = [...prioridadesAsignaturas]; [siguiente[indice], siguiente[indice + 1]] = [siguiente[indice + 1], siguiente[indice]]; actualizarPrioridades(siguiente); }} aria-label="Bajar prioridad"><ArrowDown className="h-3.5 w-3.5" /></Button><Button type="button" variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive" onClick={() => actualizarPrioridades(prioridadesAsignaturas.filter((item) => item !== codigo))} aria-label="Quitar prioridad"><X className="h-3.5 w-3.5" /></Button></li>)}</ol> : <p className="text-xs text-muted-foreground">Aún no has indicado preferencias.</p>}
                      </div>
                    )}
                    <div className="rounded-lg border bg-muted/30 p-4">
                      <div className="mb-3 flex items-center gap-2 text-sm font-semibold"><LockKeyhole className="h-4 w-4 text-primary" /> Cambiar contraseña</div>
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div className="space-y-2"><Label htmlFor="password">Nueva contraseña</Label><Input id="password" type="password" minLength={12} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Déjalo vacío para conservarla" /></div>
                        <div className="space-y-2"><Label htmlFor="repetir-password">Repetir contraseña</Label><Input id="repetir-password" type="password" minLength={12} autoComplete="new-password" value={repetirPassword} onChange={(event) => setRepetirPassword(event.target.value)} /></div>
                      </div>
                    </div>
                    <Button type="submit" disabled={guardando}>
                      {guardando ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />} Guardar cambios
                    </Button>
                  </form>
                </CardContent>
              </Card>

              <Card className="h-fit shadow-sm">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2"><BookOpen className="h-5 w-5 text-primary" /> Perfil docente</CardTitle>
                  <CardDescription>Datos que determinan las colas de ordenación.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4 text-sm">
                  {profesor ? <>
                    <div><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Categoría</p><p className="mt-1 font-medium">{profesor.categoria}</p></div>
                    <div><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Fecha de ingreso</p><p className="mt-1 font-medium">{formatearFecha(profesor.fecha_ingreso)}</p></div>
                    <div><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Carga objetivo</p><p className="mt-1 font-medium">{profesor.carga_docente} h</p></div>
                    <div><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Disponibilidad</p><p className="mt-1 font-medium">{getLabelDisponibilidadCuatrimestre(profesor.disponibilidad_cuatrimestre)}</p></div>
                    <div><p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Áreas de pertenencia</p><div className="flex flex-wrap gap-1">{(profesor.areas ?? []).map((area) => <Badge key={area.id} variant="outline">{area.codigo}</Badge>)}{(profesor.areas ?? []).length === 0 && <span className="text-muted-foreground">Sin áreas asociadas</span>}</div></div>
                    <div><p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Prioridades de asignaturas</p>{(profesor.prioridades_asignaturas ?? []).length ? <ol className="space-y-1">{(profesor.prioridades_asignaturas ?? []).map((item) => <li key={item.codigo} className="text-sm"><span className="mr-2 font-semibold text-primary">{item.prioridad}.</span>{item.nombre}</li>)}</ol> : <span className="text-muted-foreground">Sin prioridades declaradas</span>}</div>
                    <p className="rounded-lg bg-muted p-3 text-xs text-muted-foreground">La categoría, carga y áreas afectan al orden de elección. Para modificarlas, contacta con tu responsable de área, departamento o con administración.</p>
                  </> : <p className="rounded-lg bg-muted p-3 text-muted-foreground">Tu cuenta no tiene un perfil docente asociado.</p>}
                </CardContent>
              </Card>
            </div>
          ) : (
            <Card><CardContent className="p-8 text-sm text-destructive">No se ha podido recuperar el perfil de la cuenta.</CardContent></Card>
          )}
        </div>
      </main>
    </div>
  );
}
