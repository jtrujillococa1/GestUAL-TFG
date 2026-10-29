import pytest
from fastapi import HTTPException
from core import auth


@pytest.mark.parametrize('usuario', [None, {'activo': False, 'rol': 'admin'}])
def test_cuenta_no_disponible_no_conserva_acceso(monkeypatch, usuario):
    monkeypatch.setattr(auth, 'decode_access_token', lambda token: {'sub':'123','rol':'admin'})
    monkeypatch.setattr(auth, '_usuario_de_sesion', lambda uid: usuario)
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user('token')
    assert exc.value.status_code == 401


def test_permisos_se_toman_de_cuenta_actual(monkeypatch):
    monkeypatch.setattr(auth, 'decode_access_token', lambda token: {'sub':'123','rol':'admin'})
    monkeypatch.setattr(auth, '_usuario_de_sesion', lambda uid: {'activo':True,'rol':'profesor','email':'actual@example.org'})
    usuario = auth.get_current_user('token')
    assert usuario['rol'] == 'profesor'
    with pytest.raises(HTTPException) as exc:
        auth.require_admin(usuario)
    assert exc.value.status_code == 403
