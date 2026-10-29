"""
API Routes - Authentication
Endpoints para login y gestión de tokens JWT
"""
from datetime import timedelta
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from core.auth import create_access_token, verify_password, ACCESS_TOKEN_EXPIRE_MINUTES
from repositories import UsuarioRepository

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class TokenResponse(BaseModel):
    """Response del endpoint de login"""
    access_token: str
    token_type: str


@router.post("/token", response_model=TokenResponse, summary="Login con email y contraseña")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Endpoint de autenticación.
    
    Recibe email (en username) y contraseña, retorna JWT token si las credenciales son válidas.
    """
    # Buscar usuario por email
    repo = UsuarioRepository()
    usuario = repo.find_by_email(form_data.username)
    
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verificar contraseña
    if not verify_password(form_data.password, usuario["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verificar que el usuario esté activo
    if not usuario.get("activo", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo"
        )
    
    # Crear token JWT con datos del usuario
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(usuario["id"]),
            "email": usuario["email"],
            "rol": usuario["rol"]
        },
        expires_delta=access_token_expires
    )
    
    # ✅ FIX: Retornar objeto Pydantic, no diccionario
    return TokenResponse(access_token=access_token, token_type="bearer")