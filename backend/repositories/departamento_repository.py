"""
Repository para departamentos.
"""
import re
from typing import List, Optional, Dict, Any
from db.connection import conexion_ctx, cursor_ctx
from core.exceptions import DepartamentoNotFound, ConstraintViolation


class DepartamentoRepository:
    """Gestiona operaciones CRUD de departamentos."""

    @staticmethod
    def _resolver_responsable(
        cur, responsable_id: Optional[int], codigo_departamento: str, nombre_departamento: str,
    ) -> Optional[int]:
        if responsable_id is None:
            return None
        cur.execute("SELECT id, rol, password_hash FROM usuarios WHERE id = %s", (responsable_id,))
        usuario = cur.fetchone()
        if usuario and not isinstance(usuario, dict):
            usuario = dict(zip(('id', 'rol', 'password_hash'), usuario))
        if not usuario:
            raise ConstraintViolation(f"Usuario {responsable_id} no encontrado.")
        if usuario["rol"] in ("admin", "responsable_departamento"):
            return responsable_id
        cur.execute("SELECT 1 FROM profesores WHERE usuario_id=%s", (responsable_id,))
        if not cur.fetchone():
            raise ConstraintViolation(
                "Selecciona una cuenta responsable o el perfil docente de la persona responsable."
            )
        slug = re.sub(r"[^a-z0-9]+", "-", codigo_departamento.lower()).strip("-") or str(responsable_id)
        email = f"responsable.departamento.{slug}@gestual.local"
        nombre_limpio = re.sub(r"^Departamento\s+", "", nombre_departamento, flags=re.I)
        cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
        cuenta = cur.fetchone()
        if cuenta:
            return cuenta["id"] if isinstance(cuenta, dict) else cuenta[0]
        cur.execute(
            """
            INSERT INTO usuarios (nombre, apellidos, email, password_hash, rol, activo)
            VALUES (%s, %s, %s, %s, 'responsable_departamento', TRUE)
            RETURNING id
            """,
            ("Responsable", f"Departamento {nombre_limpio}", email, usuario["password_hash"]),
        )
        cuenta = cur.fetchone()
        return cuenta["id"] if isinstance(cuenta, dict) else cuenta[0]
    
    def find_all(self) -> List[Dict[str, Any]]:
        """Obtiene todos los departamentos."""
        with cursor_ctx() as cur:
            cur.execute("""
                SELECT id, codigo, nombre, responsable_departamento_id
                FROM departamentos
                ORDER BY codigo
            """)
            return [dict(row) for row in cur.fetchall()]
    
    def find_by_id(self, departamento_id: int) -> Optional[Dict[str, Any]]:
        """Obtiene un departamento por ID."""
        with cursor_ctx() as cur:
            cur.execute("""
                SELECT id, codigo, nombre, responsable_departamento_id
                FROM departamentos
                WHERE id = %s
            """, (departamento_id,))
            
            row = cur.fetchone()
            if not row:
                return None
            
            return dict(row)
    
    def find_by_codigo(self, codigo: str) -> Optional[Dict[str, Any]]:
        """Obtiene un departamento por código."""
        with cursor_ctx() as cur:
            cur.execute("""
                SELECT id, codigo, nombre, responsable_departamento_id
                FROM departamentos
                WHERE codigo = %s
            """, (codigo,))
            
            row = cur.fetchone()
            if not row:
                return None
            
            return dict(row)
    
    def create(self, codigo: str, nombre: str, responsable_departamento_id: Optional[int] = None) -> Dict[str, Any]:
        """Crea un nuevo departamento."""
        with conexion_ctx() as conn:
            cur = conn.cursor()
            
            # Verificar código único
            cur.execute("SELECT id FROM departamentos WHERE codigo = %s", (codigo,))
            if cur.fetchone():
                raise ConstraintViolation(f"Ya existe un departamento con código '{codigo}'.")

            responsable_departamento_id = self._resolver_responsable(cur, responsable_departamento_id, codigo, nombre)
            
            # Crear
            cur.execute("""
                INSERT INTO departamentos (codigo, nombre, responsable_departamento_id)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (codigo, nombre, responsable_departamento_id))
            
            nuevo_id = cur.fetchone()[0]
        
        return self.find_by_id(nuevo_id)
    
    def update(self, departamento_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza un departamento."""
        if not updates:
            raise ValueError("No hay campos para actualizar")
        
        with conexion_ctx() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM departamentos WHERE id=%s", (departamento_id,))
            if not cur.fetchone():
                raise DepartamentoNotFound(f"Departamento {departamento_id} no encontrado.")
            if "codigo" in updates:
                cur.execute(
                    "SELECT id FROM departamentos WHERE codigo=%s AND id<>%s",
                    (updates["codigo"], departamento_id),
                )
                if cur.fetchone():
                    raise ConstraintViolation(f"Ya existe un departamento con código '{updates['codigo']}'.")
            if "responsable_departamento_id" in updates:
                cur.execute("SELECT codigo, nombre FROM departamentos WHERE id=%s", (departamento_id,))
                actual = cur.fetchone()
                if not isinstance(actual, dict):
                    actual = dict(zip(('codigo', 'nombre'), actual))
                updates["responsable_departamento_id"] = self._resolver_responsable(
                    cur, updates["responsable_departamento_id"], updates.get("codigo", actual["codigo"]), updates.get("nombre", actual["nombre"]),
                )
            set_clause = ", ".join(f"{k} = %s" for k in updates.keys())
            values = list(updates.values()) + [departamento_id]
            cur.execute(f"""
                UPDATE departamentos
                SET {set_clause}
                WHERE id = %s
            """, values)
        
        return self.find_by_id(departamento_id)
    
    def asignar_responsable(self, departamento_id: int, responsable_id: Optional[int]) -> Dict[str, Any]:
        """Asigna o quita el responsable de un departamento."""
        # Verificar que el departamento existe
        departamento = self.find_by_id(departamento_id)
        if not departamento:
            raise DepartamentoNotFound(f"Departamento {departamento_id} no encontrado.")
        
        return self.update(departamento_id, {"responsable_departamento_id": responsable_id})
    
    def delete(self, departamento_id: int) -> None:
        """Elimina un departamento."""
        # Verificar que existe
        departamento = self.find_by_id(departamento_id)
        if not departamento:
            raise DepartamentoNotFound(f"Departamento {departamento_id} no encontrado.")
        
        with conexion_ctx() as conn:
            cur = conn.cursor()
            
            # Verificar que no tiene áreas
            cur.execute("SELECT COUNT(*) FROM areas WHERE departamento_id = %s", (departamento_id,))
            if cur.fetchone()[0] > 0:
                raise ConstraintViolation(
                    "No se puede eliminar el departamento: tiene áreas asociadas."
                )
            
            # Eliminar
            cur.execute("DELETE FROM departamentos WHERE id = %s", (departamento_id,))

