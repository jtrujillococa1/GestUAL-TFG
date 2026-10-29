"""
Repository para categorías docentes.
"""
from typing import List, Dict, Any
from db.connection import conexion_ctx, cursor_ctx
from core.exceptions import ValidationError


class CategoriaRepository:
    """Gestiona operaciones CRUD de categorías docentes."""
    
    def find_all(self) -> List[Dict[str, Any]]:
        """Obtiene todas las categorías con sus pesos."""
        with cursor_ctx() as cur:
            cur.execute("""
                SELECT categoria, peso
                FROM categoria_pesos
                ORDER BY peso ASC
            """)
            return [dict(row) for row in cur.fetchall()]
    
    def get_prioridad_ordenada(self) -> List[str]:
        """Obtiene las categorías ordenadas por prioridad (peso ascendente)."""
        with cursor_ctx() as cur:
            cur.execute("""
                SELECT categoria
                FROM categoria_pesos
                ORDER BY peso ASC
            """)
            return [row["categoria"] for row in cur.fetchall()]
    
    def find_by_categoria(self, categoria: str) -> Dict[str, Any]:
        """Obtiene una categoría específica por nombre."""
        with cursor_ctx() as cur:
            cur.execute("""
                SELECT categoria, peso
                FROM categoria_pesos
                WHERE categoria = %s
            """, (categoria,))
            
            row = cur.fetchone()
            if not row:
                raise ValidationError(f"Categoría '{categoria}' no encontrada.")
            
            return dict(row)
    
    def update_peso(self, categoria: str, nuevo_peso: int) -> Dict[str, Any]:
        """Actualiza el peso de una categoría."""
        if nuevo_peso < 1:
            raise ValidationError("El peso debe ser mayor o igual a 1.")
        
        with conexion_ctx() as conn:
            cur = conn.cursor()
            
            # Verificar que existe
            cur.execute("SELECT categoria FROM categoria_pesos WHERE categoria = %s", (categoria,))
            if not cur.fetchone():
                raise ValidationError(f"Categoría '{categoria}' no encontrada.")
            
            # Actualizar peso
            cur.execute("""
                UPDATE categoria_pesos
                SET peso = %s
                WHERE categoria = %s
            """, (nuevo_peso, categoria))
        
        return self.find_by_categoria(categoria)
    
    def create(self, categoria: str, peso: int) -> Dict[str, Any]:
        """Crea una nueva categoría."""
        if peso < 1:
            raise ValidationError("El peso debe ser mayor o igual a 1.")
        
        with conexion_ctx() as conn:
            cur = conn.cursor()
            
            # Verificar que no existe
            cur.execute("SELECT categoria FROM categoria_pesos WHERE categoria = %s", (categoria,))
            if cur.fetchone():
                raise ValidationError(f"La categoría '{categoria}' ya existe.")
            
            # Crear
            cur.execute("""
                INSERT INTO categoria_pesos (categoria, peso)
                VALUES (%s, %s)
            """, (categoria, peso))
        
        return self.find_by_categoria(categoria)
    
    def delete(self, categoria: str) -> None:
        """Elimina una categoría."""
        with conexion_ctx() as conn:
            cur = conn.cursor()
            
            # Verificar que no tiene profesores asignados
            cur.execute("SELECT COUNT(*) FROM profesores WHERE categoria = %s", (categoria,))
            if cur.fetchone()[0] > 0:
                raise ValidationError(
                    f"No se puede eliminar la categoría '{categoria}': "
                    "tiene profesores asignados."
                )
            
            # Eliminar
            cur.execute("DELETE FROM categoria_pesos WHERE categoria = %s", (categoria,))
            
            if cur.rowcount == 0:
                raise ValidationError(f"Categoría '{categoria}' no encontrada.")