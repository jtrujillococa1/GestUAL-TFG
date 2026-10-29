from typing import Optional
from core.exceptions import PermissionDenied, NotYourTurn

def require_admin(usuario_rol: str):
    if usuario_rol != "admin":
        raise PermissionDenied("Solo los administradores pueden realizar esta acciÃ³n.")

def can_modify_draft(usuario_rol: str, usuario_id: int, profesor_usuario_id: Optional[int],
                     profesor_nombre_completo: str, profesor_actual: Optional[str],
                     pertenece_al_ambito: bool = False) -> bool:
    if usuario_rol == "admin":
        return True

    if usuario_rol in ("responsable_departamento", "responsable_area"):
        if not pertenece_al_ambito:
            raise PermissionDenied("El profesor no pertenece a tu ámbito de gestión.")
        if profesor_actual != profesor_nombre_completo:
            raise NotYourTurn(f"No es el turno de '{profesor_nombre_completo}'. Turno actual: {profesor_actual}")
        return True

    if usuario_rol == "profesor":
        if profesor_usuario_id != usuario_id:
            raise PermissionDenied("Solo puedes modificar tu propio borrador.")
        
        if profesor_actual != profesor_nombre_completo:
            raise NotYourTurn(f"No es tu turno. Turno actual: {profesor_actual}")
        
        return True
    
    raise PermissionDenied("No tienes permiso para modificar borradores.")

def can_confirm_turn(usuario_rol: str, usuario_id: int, profesor_usuario_id: Optional[int],
                     profesor_nombre_completo: str, profesor_actual: Optional[str],
                     pertenece_al_ambito: bool = False) -> bool:
    return can_modify_draft(usuario_rol, usuario_id, profesor_usuario_id, 
                           profesor_nombre_completo, profesor_actual, pertenece_al_ambito)

def can_create_profesor(usuario_rol: str) -> bool:
    require_admin(usuario_rol)
    return True

def can_reset_ordenacion(usuario_rol: str) -> bool:
    require_admin(usuario_rol)
    return True
