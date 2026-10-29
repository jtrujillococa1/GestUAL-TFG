"""
Repository para usuarios.
"""
from typing import List, Dict, Optional
from db.connection import conexion_ctx, cursor_ctx
from repositories.base import BaseRepository, build_update_query
from core.exceptions import UsuarioNotFound, DuplicateResourceError


class UsuarioRepository(BaseRepository):
    """Gestiona operaciones CRUD de usuarios."""
    def __init__(self):
        super().__init__("usuarios")
    
    def find_by_id(self, usuario_id: int) -> Optional[Dict]:
        """Obtiene un usuario por ID."""
        with cursor_ctx() as cur:
            cur.execute("""
                SELECT id, nombre, apellidos, email, password_hash, rol, activo
                FROM usuarios
                WHERE id = %s
            """, (usuario_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    
    def find_by_email(self, email: str) -> Optional[Dict]:
        """Busca un usuario por email."""
        with cursor_ctx() as cur:
            cur.execute("""
                SELECT id, nombre, apellidos, email, password_hash, rol, activo
                FROM usuarios
                WHERE email = %s
            """, (email,))
            row = cur.fetchone()
            return dict(row) if row else None
    
    def find_by_rol(self, rol: str) -> List[Dict]:
        """Obtiene usuarios por rol."""
        with cursor_ctx() as cur:
            cur.execute("""
                SELECT id, nombre, apellidos, email, rol, activo
                FROM usuarios
                WHERE rol = %s
                ORDER BY apellidos, nombre
            """, (rol,))
            return [dict(row) for row in cur.fetchall()]
    
    def find_all(self) -> List[Dict]:
        """Obtiene todos los usuarios."""
        with cursor_ctx() as cur:
            cur.execute("""
                SELECT id, nombre, apellidos, email, rol, activo
                FROM usuarios
                ORDER BY apellidos, nombre
            """)
            return [dict(row) for row in cur.fetchall()]
    
    def create(
        self, nombre: str, apellidos: str, email: str,
        password_hash: str, rol: str, activo: bool = True
    ) -> Dict:
        """Crea un nuevo usuario."""
        with conexion_ctx() as conn:
            cur = conn.cursor()
            
            # Verificar email único
            cur.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
            if cur.fetchone():
                raise DuplicateResourceError(f"Ya existe un usuario con email '{email}'.")
            
            # Crear usuario
            cur.execute("""
                INSERT INTO usuarios (nombre, apellidos, email, password_hash, rol, activo)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (nombre, apellidos, email, password_hash, rol, activo))
            
            nuevo_id = cur.fetchone()[0]
        
        return self.find_by_id(nuevo_id)
    
    def update(self, usuario_id: int, updates: Dict) -> Dict:
        """Actualiza un usuario."""
        if not self.exists(usuario_id):
            raise UsuarioNotFound(f"Usuario {usuario_id} no encontrado.")
        
        # Verificar email único si se está actualizando
        if "email" in updates:
            with cursor_ctx() as cur:
                cur.execute(
                    "SELECT id FROM usuarios WHERE email = %s AND id != %s",
                    (updates["email"], usuario_id)
                )
                if cur.fetchone():
                    raise DuplicateResourceError(f"Ya existe un usuario con email '{updates['email']}'.")
        
        with conexion_ctx() as conn:
            query, values = build_update_query("usuarios", usuario_id, updates)
            conn.cursor().execute(query, values)
        
        return self.find_by_id(usuario_id)
    
    def delete(self, usuario_id: int) -> None:
        """Elimina un usuario."""
        with conexion_ctx() as conn:
            cur = conn.cursor()
            
            if not self.exists(usuario_id):
                raise UsuarioNotFound(f"Usuario {usuario_id} no encontrado.")
            
            # Limpiar referencias
            cur.execute("UPDATE profesores SET usuario_id = NULL WHERE usuario_id = %s", (usuario_id,))
            cur.execute("UPDATE areas SET responsable_area_id = NULL WHERE responsable_area_id = %s", (usuario_id,))
            cur.execute("UPDATE departamentos SET responsable_departamento_id = NULL WHERE responsable_departamento_id = %s", (usuario_id,))
            
            # Eliminar usuario
            cur.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))