"use client";
import { useState } from 'react';
import { getUserRole } from '@/lib/auth';
import { apiFetch } from '@/lib/api-client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export function CrearResponsable({ rol, nombre, onCreated }: { rol: 'responsable_area' | 'responsable_departamento'; nombre: string; onCreated: (cuenta: any) => void }) {
  const [abierto, setAbierto] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [guardando, setGuardando] = useState(false);
  if (getUserRole() !== 'Admin') return null;
  const crear = async () => {
    if (!nombre.trim() || password.length < 12 || !email.includes('@')) { setError('Indica el nombre del área/departamento, un correo y una contraseña de al menos 12 caracteres.'); return; }
    setGuardando(true); setError('');
    try {
      const cuenta = await apiFetch('/usuarios/responsables', { method: 'POST', body: { nombre_alcance: nombre, email, password, rol } });
      onCreated(cuenta); setPassword(''); setAbierto(false);
    } catch (e) { setError(e instanceof Error ? e.message : 'No se pudo crear la cuenta'); }
    finally { setGuardando(false); }
  };
  return <div className="space-y-2 rounded border p-3">
    <Button type="button" variant="outline" onClick={() => setAbierto(!abierto)}>Crear cuenta responsable independiente</Button>
    {abierto && <div className="space-y-2">
      <p className="text-sm">Responsable · {nombre || 'Introduce primero el nombre de la entidad'}. Se seleccionará automáticamente; guarda la entidad para vincularla.</p>
      <label className="block text-sm">Correo de acceso<Input type="email" value={email} onChange={e => setEmail(e.target.value)} /></label>
      <label className="block text-sm">Contraseña inicial<Input type="password" autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} /></label>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <Button type="button" disabled={guardando} onClick={crear}>{guardando ? 'Creando…' : 'Crear y seleccionar cuenta'}</Button>
    </div>}
  </div>;
}
