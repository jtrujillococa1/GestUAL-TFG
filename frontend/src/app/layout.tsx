import type { Metadata } from 'next';
import './globals.css';
import { Toaster } from '@/components/ui/toaster';
import { SessionGuard } from '@/components/auth/session-guard';

export const metadata: Metadata = {
  title: 'GestUAL Docente - Gestión de Ordenación',
  description: 'Sistema inteligente de gestión de ordenación docente universitaria',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body className="font-body antialiased bg-background text-foreground">
        <SessionGuard>{children}</SessionGuard>
        <Toaster />
      </body>
    </html>
  );
}
