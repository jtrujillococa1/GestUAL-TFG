"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle } from "lucide-react";
import { login } from "@/lib/auth";
import { Alert, AlertDescription } from "@/components/ui/alert";

const loginSchema = z.object({
  email: z.string().email("Introduce un correo institucional válido"),
  password: z.string().min(1, "La contraseña es obligatoria"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAccessHelp, setShowAccessHelp] = useState(false);
  const router = useRouter();

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const onSubmit = async (values: LoginFormValues) => {
    setIsLoading(true);
    setError(null);

    try {
      // Llamada real al backend
      await login(values);
      
      // Redirigir al dashboard
      router.replace("/dashboard");
    } catch (err: any) {
      console.error('Error en login:', err);
      setError(err.message || 'Error al iniciar sesión. Verifica tus credenciales.');
    } finally {
      setIsLoading(false);
    }
  };


  return (
    <div className="min-h-screen flex items-center justify-center bg-[#ECF0F3] p-6 font-body">
      <div className="w-full max-w-[400px] space-y-8 animate-in fade-in zoom-in duration-500">
        <div className="flex flex-col items-center gap-2 mb-8">
          <div className="bg-primary p-3 rounded-2xl shadow-xl shadow-primary/20 mb-2">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="w-10 h-10 text-white"
            >
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-primary">GestUAL Docente</h1>
          <p className="text-muted-foreground font-medium text-center uppercase tracking-widest text-[10px]">Gestión Inteligente de Ordenación</p>
        </div>

        <Card className="border-none shadow-2xl overflow-hidden rounded-3xl">
          <CardHeader className="space-y-1 pb-6">
            <CardTitle className="text-2xl font-bold text-center">Acceder al Sistema</CardTitle>
            <CardDescription className="text-center">Introduce tus credenciales universitarias</CardDescription>
          </CardHeader>
          <CardContent>
            {error && (
              <Alert variant="destructive" className="mb-4">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Correo Institucional</FormLabel>
                      <FormControl>
                        <Input 
                          placeholder="ejemplo@universidad.es" 
                          className="h-12 bg-secondary/30 border-none rounded-xl"
                          disabled={isLoading}
                          {...field} 
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="password"
                  render={({ field }) => (
                    <FormItem>
                      <div className="flex justify-between items-center">
                        <FormLabel>Contraseña</FormLabel>
                        <Button variant="link" type="button" className="p-0 h-auto text-xs font-semibold text-primary" aria-expanded={showAccessHelp} aria-controls="access-help" onClick={() => setShowAccessHelp((visible) => !visible)}>¿Olvidaste tu clave?</Button>
                      </div>
                      <FormControl>
                        <Input 
                          type="password" 
                          className="h-12 bg-secondary/30 border-none rounded-xl"
                          disabled={isLoading}
                          {...field} 
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button type="submit" className="w-full h-12 text-lg font-bold rounded-xl mt-4" disabled={isLoading}>
                  {isLoading ? "Validando..." : "Iniciar Sesión"}
                </Button>
              </form>
            </Form>
            {showAccessHelp && (
              <Alert id="access-help" className="mt-4">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  Solicita al administrador de la aplicación la recuperación de tu acceso,
                  indicando tu correo institucional. No compartas tu contraseña.
                  Este botón no envía correos ni cambia tus credenciales.
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
        
        <p className="text-center text-xs text-muted-foreground font-medium italic">
          v1.0.4 • © 2026 Universidad - Proyecto TFG
        </p>
      </div>
    </div>
  );
}
