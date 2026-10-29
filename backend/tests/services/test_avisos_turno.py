from unittest.mock import MagicMock, patch
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from services.avisos_turno import enviar, correo_configurado


def test_sin_configuracion_no_hay_envio(monkeypatch):
    monkeypatch.delenv('SMTP_HOST', raising=False)
    monkeypatch.delenv('SMTP_FROM', raising=False)
    assert not correo_configurado()


@pytest.mark.parametrize('correo', [None, '', 'prueba', 'marta@prueba.local', 'a@correo.invalid'])
def test_rechaza_destinatarios_de_prueba(correo):
    with patch('services.avisos_turno.smtplib.SMTP') as smtp:
        with pytest.raises(ValueError):
            enviar(correo, 'Marta', 'Informática', 1)
        smtp.assert_not_called()


def test_envio_con_tls_y_enlace(monkeypatch):
    monkeypatch.setenv('SMTP_HOST', 'smtp.test')
    monkeypatch.setenv('SMTP_FROM', 'avisos@universidad.es')
    monkeypatch.setenv('SMTP_SECURITY', 'starttls')
    monkeypatch.setenv('SMTP_USER', 'avisos')
    monkeypatch.setenv('SMTP_PASSWORD', 'secreto-prueba')
    monkeypatch.setenv('APP_PUBLIC_URL', 'https://docencia.universidad.es')
    with patch('services.avisos_turno.smtplib.SMTP') as factory:
        smtp = factory.return_value.__enter__.return_value
        enviar('profesor@universidad.es', 'Marta', 'Informática', 7)
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with('avisos', 'secreto-prueba')
        mensaje = smtp.send_message.call_args.args[0]
        assert mensaje['To'] == 'profesor@universidad.es'
        assert 'Informática' in mensaje['Subject']
        assert 'https://docencia.universidad.es/eleccion' in mensaje.get_content()


def test_cola_no_duplica_y_cancela_turnos_anteriores(monkeypatch):
    from services import avisos_turno
    memoria = {'actual': None, 'avisos': [], 'reinicio': 0}
    class Cursor:
        def execute(self, sql, params=()):
            self.sql = sql
            if sql.startswith('INSERT INTO avisos_turno_estado'):
                memoria['actual'] = {'firma': params[1], 'generacion': params[2]}
            elif sql.startswith('UPDATE avisos_turno_correo'):
                for aviso in memoria['avisos']:
                    aviso['estado'] = 'CANCELADO'
            elif sql.startswith('INSERT INTO avisos_turno_correo'):
                memoria['avisos'].append({'profesor': params[1], 'estado': 'PENDIENTE'})
        def fetchone(self):
            if 'advisory' in self.sql:
                return {'adquirido': True}
            if 'MAX(id)' in self.sql:
                return {'reinicio': memoria['reinicio']}
            return memoria['actual']
        def fetchall(self):
            return [{'id': 1, 'nombre': 'Informática'}]
    @contextmanager
    def cursor():
        yield Cursor()
    estado = SimpleNamespace(ordenacion_terminada=False, profesor_actual='Ortega, Marta')
    servicio = MagicMock()
    servicio.get_estados_por_area.return_value = {1: estado}
    servicio.profesor_repo.find_by_nombre_completo.return_value = {'id': 10}
    monkeypatch.setattr(avisos_turno, 'cursor_ctx', cursor)
    monkeypatch.setattr(avisos_turno, 'correo_configurado', lambda: False)
    with patch('services.ordenacion_service.OrdenacionService', return_value=servicio):
        avisos_turno.ciclo()
        avisos_turno.ciclo()
        assert len(memoria['avisos']) == 1
        servicio.profesor_repo.find_by_nombre_completo.return_value = {'id': 11}
        avisos_turno.ciclo()
        assert memoria['avisos'] == [{'profesor': 10, 'estado': 'CANCELADO'}, {'profesor': 11, 'estado': 'PENDIENTE'}]
        memoria['reinicio'] = 7
        avisos_turno.ciclo()
        assert len(memoria['avisos']) == 3
        estado.ordenacion_terminada = True
        avisos_turno.ciclo()
        assert all(a['estado'] == 'CANCELADO' for a in memoria['avisos'])
