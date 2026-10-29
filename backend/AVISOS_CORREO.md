# Avisos del turno docente

El backend comprueba las colas cada 30 segundos y guarda un aviso cuando cambia
el profesor activo de un área. También registra los turnos activos al instalar
esta función. Las modificaciones del borrador y los reinicios del servidor no
generan nuevos avisos para el mismo turno. Un reinicio de ordenación sí inicia
un nuevo aviso. Los avisos pendientes de turnos anteriores se cancelan.

Configurar en `backend/.env`: SMTP_HOST, SMTP_PORT, SMTP_SECURITY (`starttls`
o `ssl`), SMTP_FROM, SMTP_USER, SMTP_PASSWORD y APP_PUBLIC_URL. Usar una URL
accesible para los profesores; localhost solo sirve en el propio equipo.
Después recrear el backend para cargar las variables. No guardar credenciales
en el repositorio. Cada profesor necesita una cuenta activa con correo real.

Sin servidor configurado, los avisos permanecen pendientes. Los errores se
reintentan cada cinco minutos. El administrador puede consultar los últimos
100 avisos en GET /api/v1/admin/avisos-turno, con su sesión autenticada.
ENVIADO significa aceptado por el servidor SMTP; no confirma la lectura ni
la entrega final al buzón. Ante una caída justo después de la aceptación SMTP
puede haber un reenvío; el Message-ID permanece estable para ese aviso.

Aplicar `python migrar_modelo_docente.py` antes de iniciar la versión nueva.
