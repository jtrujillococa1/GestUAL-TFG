"""
Repository para áreas académicas.
"""
import re
from typing import List, Optional, Dict, Any
from db.connection import conexion_ctx, cursor_ctx


class AreaRepository:
    """Gestiona operaciones CRUD de áreas."""

    @staticmethod
    def _resolver_responsable(
        cur, responsable_id: Optional[int], codigo_area: str, nombre_area: str,
    ) -> Optional[int]:
        """Convierte un docente elegido en su cuenta institucional de área."""
        if responsable_id is None:
            return None
        cur.execute("SELECT id, rol, password_hash FROM usuarios WHERE id = %s", (responsable_id,))
        usuario = cur.fetchone()
        if usuario and not isinstance(usuario, dict):
            usuario = dict(zip(('id', 'rol', 'password_hash'), usuario))
        if not usuario:
            from core.exceptions import ConstraintViolation
            raise ConstraintViolation(f"Usuario {responsable_id} no encontrado.")
        if usuario["rol"] in ("admin", "responsable_area"):
            return responsable_id
        cur.execute("SELECT 1 FROM profesores WHERE usuario_id=%s", (responsable_id,))
        if not cur.fetchone():
            from core.exceptions import ConstraintViolation
            raise ConstraintViolation(
                "Selecciona una cuenta responsable o el perfil docente de la persona responsable."
            )
        slug = re.sub(r"[^a-z0-9]+", "-", codigo_area.lower()).strip("-") or str(responsable_id)
        email = f"responsable.area.{slug}@gestual.local"
        nombre_limpio = re.sub(r"^Área\s+", "", nombre_area, flags=re.I)
        cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
        cuenta = cur.fetchone()
        if cuenta:
            return cuenta["id"] if isinstance(cuenta, dict) else cuenta[0]
        cur.execute(
            """
            INSERT INTO usuarios (nombre, apellidos, email, password_hash, rol, activo)
            VALUES (%s, %s, %s, %s, 'responsable_area', TRUE)
            RETURNING id
            """,
            ("Responsable", f"Área {nombre_limpio}", email, usuario["password_hash"]),
        )
        cuenta = cur.fetchone()
        return cuenta["id"] if isinstance(cuenta, dict) else cuenta[0]

    def create(
        self, codigo: str, nombre: str, departamento_id: int,
        responsable_area_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Crea el área y valida todos sus vínculos en la misma transacción."""
        from core.exceptions import ConstraintViolation

        with conexion_ctx() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM departamentos WHERE id=%s", (departamento_id,))
            if not cur.fetchone():
                raise ConstraintViolation(f"Departamento {departamento_id} no encontrado.")
            cur.execute("SELECT id FROM areas WHERE codigo=%s", (codigo,))
            if cur.fetchone():
                raise ConstraintViolation(f"Ya existe un área con código '{codigo}'.")
            responsable_area_id = self._resolver_responsable(cur, responsable_area_id, codigo, nombre)
            cur.execute(
                """
                INSERT INTO areas (codigo, nombre, departamento_id, responsable_area_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (codigo, nombre, departamento_id, responsable_area_id),
            )
            nuevo_id = cur.fetchone()[0]
        return self.find_by_id(nuevo_id)
    
    def find_all(self) -> List[Dict[str, Any]]:
        """Obtiene todas las áreas."""
        with conexion_ctx() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, codigo, nombre, departamento_id, responsable_area_id
                FROM areas
                ORDER BY codigo
            """)
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    
    def find_by_id(self, area_id: int) -> Optional[Dict[str, Any]]:
        """Obtiene un área por ID."""
        with conexion_ctx() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, codigo, nombre, departamento_id, responsable_area_id
                FROM areas
                WHERE id = %s
            """, (area_id,))
            
            row = cur.fetchone()
            if not row:
                return None
            
            cols = [desc[0] for desc in cur.description]
            return dict(zip(cols, row))
    
    def find_by_departamento(self, departamento_id: int) -> List[Dict[str, Any]]:
        """Obtiene áreas de un departamento."""
        with conexion_ctx() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, codigo, nombre, departamento_id, responsable_area_id
                FROM areas
                WHERE departamento_id = %s
                ORDER BY codigo
            """, (departamento_id,))
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    
    def update(self, area_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza un área."""
        from core.exceptions import AreaNotFound
        
        if not updates:
            raise ValueError("No hay campos para actualizar")
        
        set_clause = ", ".join(f"{k} = %s" for k in updates.keys())
        values = list(updates.values()) + [area_id]
        
        with conexion_ctx() as conn:
            cur = conn.cursor()
            if "codigo" in updates:
                cur.execute(
                    "SELECT id FROM areas WHERE codigo=%s AND id<>%s",
                    (updates["codigo"], area_id),
                )
                if cur.fetchone():
                    from core.exceptions import ConstraintViolation
                    raise ConstraintViolation(f"Ya existe un área con código '{updates['codigo']}'.")
            if "departamento_id" in updates:
                cur.execute("SELECT id FROM departamentos WHERE id=%s", (updates["departamento_id"],))
                if not cur.fetchone():
                    from core.exceptions import ConstraintViolation
                    raise ConstraintViolation(f"Departamento {updates['departamento_id']} no encontrado.")
            if "responsable_area_id" in updates:
                cur.execute("SELECT codigo, nombre FROM areas WHERE id=%s", (area_id,))
                actual = cur.fetchone()
                if not actual:
                    raise AreaNotFound(f"Área {area_id} no encontrada")
                if not isinstance(actual, dict):
                    actual = dict(zip(('codigo', 'nombre'), actual))
                updates["responsable_area_id"] = self._resolver_responsable(
                    cur, updates["responsable_area_id"], updates.get("codigo", actual["codigo"]), updates.get("nombre", actual["nombre"]),
                )
            values = list(updates.values()) + [area_id]
            cur.execute(f"""
                UPDATE areas
                SET {set_clause}
                WHERE id = %s
                RETURNING id
            """, values)
            
            if cur.rowcount == 0:
                raise AreaNotFound(f"Área {area_id} no encontrada")
        
        return self.find_by_id(area_id)
    
    def asignar_responsable(self, area_id: int, responsable_id: Optional[int]) -> Dict[str, Any]:
        """Asigna o quita responsable de área."""
        return self.update(area_id, {"responsable_area_id": responsable_id})
    
    def delete(self, area_id: int) -> None:
        """Elimina un área."""
        from core.exceptions import AreaNotFound, ConstraintViolation
        
        with conexion_ctx() as conn:
            cur = conn.cursor()
            
            # Verificar perfiles y asociaciones múltiples de profesores.
            cur.execute("SELECT COUNT(*) FROM profesor_areas WHERE area_id = %s", (area_id,))
            if cur.fetchone()[0] > 0:
                raise ConstraintViolation("No se puede eliminar: el área tiene profesores asignados")
            
            # Verificar cuotas y asociaciones académicas de actividades.
            cur.execute("SELECT COUNT(*) FROM actividad_areas WHERE area_id = %s", (area_id,))
            if cur.fetchone()[0] > 0:
                raise ConstraintViolation("No se puede eliminar: el área tiene actividades")
            
            # Eliminar
            cur.execute("DELETE FROM areas WHERE id = %s", (area_id,))
            
            if cur.rowcount == 0:
                raise AreaNotFound(f"Área {area_id} no encontrada")
