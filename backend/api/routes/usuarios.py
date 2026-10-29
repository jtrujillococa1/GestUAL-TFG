"""
API Routes - Usuarios.

Endpoints para gestión de usuarios del sistema.
"""

from typing import List, Optional, Literal
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, Field, field_validator

from repositories import MapeoRepository, UsuarioRepository
from solver.cache import solver_cache
from core.exceptions import UsuarioNotFound, DuplicateResourceError
from core.auth import get_current_user, require_admin, get_password_hash

router = APIRouter(prefix="/api/v1/usuarios", tags=["usuarios"])


# ═══════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════

class CreateUsuarioRequest(BaseModel):
    nombre: str
    apellidos: str
    email: EmailStr
    password: str
    rol: str  # "admin", "profesor", "responsable_area", "responsable_departamento", "psi"
    activo: bool = True


class UpdateUsuarioRequest(BaseModel):
    nombre: Optional[str] = None
    apellidos: Optional[str] = None
    # Se mantienen cuentas de prueba ya existentes con dominio .local. Para
    # editarlas, aceptamos cualquier dirección con parte local y dominio, sin
    # relajar la comprobación mínima de formato.
    email: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=12)
    rol: Optional[str] = None
    activo: Optional[bool] = None

    @field_validator("email")
    @classmethod
    def validar_email_actualizado(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalizado = value.strip().lower()
        if (
            not normalizado
            or normalizado.count("@") != 1
            or any(caracter.isspace() for caracter in normalizado)
        ):
            raise ValueError("Introduce un correo electrónico válido.")
        usuario, dominio = normalizado.split("@", 1)
        if not usuario or not dominio or "." not in dominio:
            raise ValueError("Introduce un correo electrónico válido.")
        return normalizado


class CrearResponsableRequest(BaseModel):
    nombre_alcance: str = Field(min_length=3, max_length=150)
    email: EmailStr
    password: str = Field(min_length=12)
    rol: Literal['responsable_area', 'responsable_departamento']


@router.post('/responsables', status_code=201)
def crear_responsable(body: CrearResponsableRequest, current_user: dict = Depends(require_admin)):
    try:
        usuario = UsuarioRepository().create('Responsable', body.nombre_alcance.strip(), str(body.email).lower(), get_password_hash(body.password), body.rol)
        usuario.pop('password_hash', None)
        return usuario
    except DuplicateResourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS - SOLO ADMIN
# ═══════════════════════════════════════════════════════════════

@router.get("/", summary="Listar usuarios")
def get_usuarios(
    current_user: dict = Depends(require_admin)  # ✅ SOLO ADMIN
):
    """
    Lista todos los usuarios del sistema.
    
    **Roles permitidos:** ADMIN
    """
    repo = UsuarioRepository()
    return repo.find_all()


@router.get("/me", summary="Mi usuario actual")
def get_mi_usuario(
    current_user: dict = Depends(get_current_user)  # ✅ Cualquier usuario
):
    """
    Obtiene los datos del usuario autenticado.
    
    **Roles permitidos:** TODOS (autenticados)
    """
    repo = UsuarioRepository()
    usuario = repo.find_by_id(current_user["user_id"])
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # No devolver el password_hash
    if "password_hash" in usuario:
        del usuario["password_hash"]
    
    return usuario


@router.get("/responsables", summary="Listar cuentas institucionales responsables")
def get_cuentas_responsables(
    current_user: dict = Depends(get_current_user),
):
    """Devuelve las cuentas de gestión, nunca perfiles docentes vinculados.

    Se usa al asignar responsables de áreas y departamentos. Los datos de
    acceso no se devuelven y cada cuenta se mantiene independiente de la
    cuenta personal del profesorado.
    """
    cuentas = UsuarioRepository().find_all()
    return [
        {
            "id": cuenta["id"], "nombre": cuenta["nombre"], "apellidos": cuenta["apellidos"],
            "email": cuenta["email"], "rol": cuenta["rol"], "activo": cuenta["activo"],
        }
        for cuenta in cuentas
        if cuenta["rol"] in {"responsable_departamento", "responsable_area"}
    ]


@router.get("/{usuario_id}", summary="Obtener usuario por ID")
def get_usuario(
    usuario_id: int,
    current_user: dict = Depends(require_admin)  # ✅ SOLO ADMIN
):
    """
    Obtiene un usuario específico.
    
    **Roles permitidos:** ADMIN
    """
    repo = UsuarioRepository()
    usuario = repo.find_by_id(usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail=f"Usuario {usuario_id} no encontrado.")
    
    if "password_hash" in usuario:
        del usuario["password_hash"]
    
    return usuario


@router.get("/email/{email}", summary="Buscar usuario por email")
def get_usuario_por_email(
    email: str,
    current_user: dict = Depends(require_admin)  # ✅ SOLO ADMIN
):
    """
    Busca un usuario por email.
    
    **Roles permitidos:** ADMIN
    """
    repo = UsuarioRepository()
    usuario = repo.find_by_email(email)
    if not usuario:
        raise HTTPException(status_code=404, detail=f"Usuario con email '{email}' no encontrado.")
    
    if "password_hash" in usuario:
        del usuario["password_hash"]
    
    return usuario


@router.get("/rol/{rol}", summary="Usuarios por rol")
def get_usuarios_por_rol(
    rol: str,
    current_user: dict = Depends(require_admin)  # ✅ SOLO ADMIN
):
    """
    Obtiene usuarios por rol.
    
    **Roles permitidos:** ADMIN
    """
    repo = UsuarioRepository()
    return repo.find_by_rol(rol)


@router.post("/", status_code=status.HTTP_201_CREATED, summary="Crear usuario")
def create_usuario(
    body: CreateUsuarioRequest,
    current_user: dict = Depends(require_admin)  # ✅ SOLO ADMIN
):
    """
    Crea un nuevo usuario.
    
    **Roles permitidos:** ADMIN
    
    El password se hashea automáticamente con bcrypt.
    """
    repo = UsuarioRepository()
    
    # ✅ HASHEAR PASSWORD CON BCRYPT
    password_hash = get_password_hash(body.password)
    
    try:
        return repo.create(
            nombre=body.nombre,
            apellidos=body.apellidos,
            email=body.email,
            password_hash=password_hash,
            rol=body.rol,
            activo=body.activo,
        )
    except DuplicateResourceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{usuario_id}", summary="Actualizar usuario")
def update_usuario(
    usuario_id: int,
    body: UpdateUsuarioRequest,
    current_user: dict = Depends(get_current_user)  # ✅ ADMIN o el propio usuario
):
    """
    Actualiza un usuario.
    
    **Roles permitidos:**
    - ADMIN: Cualquier usuario
    - Otros: Solo su propio usuario (excepto rol y activo)
    """
    rol = current_user["rol"]
    
    # Si no es admin, solo puede editar su propio usuario
    if rol != "admin":
        if current_user["user_id"] != usuario_id:
            raise HTTPException(status_code=403, detail="Solo puedes editar tu propio usuario")
        
        # No puede cambiar rol ni activo
        if body.rol is not None:
            raise HTTPException(status_code=403, detail="No puedes cambiar tu propio rol")
        if body.activo is not None:
            raise HTTPException(status_code=403, detail="No puedes cambiar tu estado activo")
    
    repo = UsuarioRepository()
    
    updates = {}
    if body.nombre is not None:
        updates["nombre"] = body.nombre
    if body.apellidos is not None:
        updates["apellidos"] = body.apellidos
    if body.email is not None:
        updates["email"] = body.email
    if body.password is not None:
        # ✅ HASHEAR PASSWORD CON BCRYPT
        updates["password_hash"] = get_password_hash(body.password)
    if body.rol is not None:
        updates["rol"] = body.rol
    if body.activo is not None:
        updates["activo"] = body.activo
    
    if not updates:
        raise HTTPException(status_code=400, detail="No se proporcionó ningún campo")
    
    try:
        usuario_actualizado = repo.update(usuario_id, updates)

        # Nombre y apellidos se muestran también en el perfil docente y en la
        # cola de ordenación. Mantener ambos registros alineados evita que un
        # usuario vea un nombre distinto al que se usa en sus turnos.
        if body.nombre is not None or body.apellidos is not None:
            from db.connection import conexion_ctx

            campos = []
            valores = []
            if body.nombre is not None:
                campos.append("nombre = %s")
                valores.append(body.nombre)
            if body.apellidos is not None:
                campos.append("apellidos = %s")
                valores.append(body.apellidos)
            valores.append(usuario_id)
            with conexion_ctx() as conn:
                conn.cursor().execute(
                    f"UPDATE profesores SET {', '.join(campos)} WHERE usuario_id = %s",
                    valores,
                )
            solver_cache.clear()
            MapeoRepository().clear_cache()

        # Nunca devolver un hash, ni siquiera al propio usuario autenticado.
        usuario_actualizado.pop("password_hash", None)
        return usuario_actualizado
    except UsuarioNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DuplicateResourceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar usuario")
def delete_usuario(
    usuario_id: int,
    current_user: dict = Depends(require_admin)  # ✅ SOLO ADMIN
):
    """
    Elimina un usuario.
    
    **Roles permitidos:** ADMIN
    """
    # Evitar que admin se elimine a sí mismo
    if current_user["user_id"] == usuario_id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propio usuario")
    
    repo = UsuarioRepository()
    try:
        repo.delete(usuario_id)
    except UsuarioNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
