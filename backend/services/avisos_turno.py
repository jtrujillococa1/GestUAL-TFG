"""Avisos persistentes del turno activo; envío fuera de las peticiones web."""
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from threading import Event, Thread

from db.connection import cursor_ctx

logger = logging.getLogger(__name__)
_stop = Event()
_thread = None


def correo_configurado():
    return bool(os.getenv('SMTP_HOST') and os.getenv('SMTP_FROM'))


def enviar(destinatario, nombre, area, aviso_id, prueba=False, gestionado=False):
    if not destinatario or '@' not in destinatario or destinatario.lower().endswith(('.local', '.example', '.invalid')):
        raise ValueError('El profesor necesita una dirección de correo real.')
    mensaje = EmailMessage()
    mensaje['From'] = os.environ['SMTP_FROM']
    mensaje['To'] = destinatario
    mensaje['Subject'] = 'GestUAL: prueba de avisos por correo' if prueba else f'GestUAL: es tu turno en {area}'
    mensaje['Message-ID'] = f'<turno-{aviso_id}@gestual.local>'
    url = os.getenv('APP_PUBLIC_URL', 'http://localhost:9002').rstrip('/')
    mensaje.set_content(f'Hola, {nombre}:\n\nYa es tu turno de ordenación docente en {area}.\n'
                        f'Accede con tu cuenta de profesor para elegir y confirmar tus actividades:\n{url}/eleccion\n\nGestUAL\n')
    if prueba:
        mensaje.set_content('Este es un correo de prueba de los avisos de turno de GestUAL.\n'
                            'No corresponde a un turno real y no requiere ninguna acción.\n')
    elif gestionado:
        mensaje.set_content(f'Hola, {nombre}:\n\nHa llegado tu turno en {area}.\n'
                            'Por tu condición de PSI, la elección debe realizarla el responsable o el administrador. Contacta con tu responsable para gestionarla.\n\nGestUAL\n')
    seguridad = os.getenv('SMTP_SECURITY', 'starttls').lower()
    if seguridad not in {'starttls', 'ssl'}:
        raise ValueError('SMTP_SECURITY debe ser starttls o ssl.')
    clase = smtplib.SMTP_SSL if seguridad == 'ssl' else smtplib.SMTP
    opciones = {'timeout': 10}
    if seguridad == 'ssl':
        opciones['context'] = ssl.create_default_context()
    with clase(os.environ['SMTP_HOST'], int(os.getenv('SMTP_PORT', '465' if seguridad == 'ssl' else '587')), **opciones) as smtp:
        if seguridad == 'starttls':
            smtp.starttls(context=ssl.create_default_context())
        if os.getenv('SMTP_USER'):
            smtp.login(os.environ['SMTP_USER'], os.environ.get('SMTP_PASSWORD', ''))
        smtp.send_message(mensaje)


def ciclo():
    from services.ordenacion_service import OrdenacionService
    # Una única instancia procesa la cola aunque haya varios workers web.
    with cursor_ctx() as cur:
        cur.execute('SELECT pg_try_advisory_xact_lock(724193028) AS adquirido')
        if not cur.fetchone()['adquirido']:
            return
        cur.execute('SELECT id, nombre FROM areas')
        areas = cur.fetchall()
        estados = OrdenacionService().get_estados_por_area([a['id'] for a in areas])
        for area in areas:
            estado = estados[area['id']]
            profesor = None
            if not estado.ordenacion_terminada and estado.profesor_actual:
                profesor = OrdenacionService().profesor_repo.find_by_nombre_completo(estado.profesor_actual)
            cur.execute("SELECT COALESCE(MAX(id),0) AS reinicio FROM ordenacion_eventos WHERE area_id=%s AND tipo='ORDENACION_REINICIADA'", (area['id'],))
            reinicio = cur.fetchone()['reinicio']
            firma = f"{profesor['id'] if profesor else 0}:{reinicio}"
            cur.execute('SELECT firma, generacion FROM avisos_turno_estado WHERE area_id=%s', (area['id'],))
            anterior = cur.fetchone()
            if anterior and anterior['firma'] == firma:
                continue
            generacion = (anterior['generacion'] if anterior else 0) + 1
            cur.execute('INSERT INTO avisos_turno_estado(area_id,firma,generacion) VALUES(%s,%s,%s) ON CONFLICT(area_id) DO UPDATE SET firma=EXCLUDED.firma,generacion=EXCLUDED.generacion', (area['id'], firma, generacion))
            cur.execute("UPDATE avisos_turno_correo SET estado='CANCELADO' WHERE area_id=%s AND estado='PENDIENTE'", (area['id'],))
            if profesor:
                cur.execute('INSERT INTO avisos_turno_correo(area_id,profesor_id,generacion) VALUES(%s,%s,%s)', (area['id'], profesor['id'], generacion))
        if not correo_configurado():
            return
        cur.execute("""SELECT n.id, u.email, u.activo, p.nombre, p.es_psi, a.nombre AS area
            FROM avisos_turno_correo n JOIN profesores p ON p.id=n.profesor_id
            LEFT JOIN usuarios u ON u.id=p.usuario_id JOIN areas a ON a.id=n.area_id
            WHERE n.estado='PENDIENTE' AND n.proximo_intento<=NOW()
            ORDER BY n.id LIMIT 5 FOR UPDATE OF n SKIP LOCKED""")
        for aviso in cur.fetchall():
            try:
                if not aviso['activo']:
                    raise ValueError('El profesor necesita una cuenta activa con correo real.')
                enviar(aviso['email'], aviso['nombre'], aviso['area'], aviso['id'], gestionado=aviso['es_psi'])
            except Exception as exc:
                # No guardar respuestas SMTP: pueden incluir información privada.
                cur.execute("UPDATE avisos_turno_correo SET intentos=intentos+1,error=%s,proximo_intento=NOW()+INTERVAL '5 minutes' WHERE id=%s", (type(exc).__name__, aviso['id']))
            else:
                cur.execute("UPDATE avisos_turno_correo SET estado='ENVIADO',enviado_en=NOW(),intentos=intentos+1,error=NULL WHERE id=%s", (aviso['id'],))


def _trabajar():
    while not _stop.is_set():
        try:
            ciclo()
        except Exception:
            logger.exception('No se pudo procesar la cola de avisos de turno')
        _stop.wait(30)


def iniciar():
    global _thread
    _stop.clear()
    _thread = Thread(target=_trabajar, name='avisos-turno', daemon=True)
    _thread.start()


def detener():
    _stop.set()
    if _thread:
        _thread.join(timeout=55)
