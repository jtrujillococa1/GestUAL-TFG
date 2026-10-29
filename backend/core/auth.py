import hashlib
import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from core.config import settings

# Configuración JWT
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verificar contraseña usando SHA256 + bcrypt"""
    password_hash = hashlib.sha256(plain_password.encode()).hexdigest()
    return bcrypt.checkpw(password_hash.encode(), hashed_password.encode())


def get_password_hash(password: str) -> str:
    """Hashear contraseña usando SHA256 + bcrypt"""
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    hashed = bcrypt.hashpw(password_hash.encode(), bcrypt.gensalt())
    return hashed.decode()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crear token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Decodificar token JWT"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Obtener usuario actual desde el token"""
    payload = decode_access_token(token)
    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo validar las credenciales",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identificador de usuario inválido",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # El token acredita la identidad, no conserva permisos para siempre.
    # Consultar el estado actual revoca inmediatamente cuentas desactivadas
    # y evita que un cambio de rol mantenga privilegios hasta la caducidad.
    usuario = _usuario_de_sesion(user_id)
    if not usuario or not usuario.get("activo"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="La cuenta no está disponible. Inicia sesión de nuevo.",
                            headers={"WWW-Authenticate": "Bearer"})
    return {
        "user_id": user_id,
        "email": usuario.get("email"),
        "rol": usuario["rol"],
    }


def _usuario_de_sesion(user_id: int) -> Optional[dict]:
    from db.connection import cursor_ctx
    with cursor_ctx() as cur:
        cur.execute("SELECT email, rol, activo FROM usuarios WHERE id=%s", (user_id,))
        return cur.fetchone()


def require_role(allowed_roles: list):
    """Decorator para requerir roles específicos"""
    def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["rol"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para realizar esta acción"
            )
        return current_user
    return role_checker


def require_admin(current_user: dict = Depends(get_current_user)):
    """Requerir rol de administrador"""
    if current_user["rol"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador"
        )
    return current_user
