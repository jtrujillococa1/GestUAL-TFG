from typing import Optional, List, Dict, Any, Callable
from db.connection import conexion_ctx, cursor_ctx

class BaseRepository:
    def __init__(self, table_name: str):
        self.table_name = table_name
    
    def exists(self, id_value: int) -> bool:
        with cursor_ctx() as cur:
            cur.execute(f"SELECT 1 FROM {self.table_name} WHERE id=%s", (id_value,))
            return cur.fetchone() is not None
    
    def count(self) -> int:
        with cursor_ctx() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            return int(cur.fetchone()["count"])

def build_update_query(table_name: str, id_value: int, updates: Dict[str, Any]) -> tuple:
    if not updates:
        raise ValueError("No hay campos para actualizar.")
    set_clauses = [f"{field}=%s" for field in updates.keys()]
    values = list(updates.values())
    values.append(id_value)
    query = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE id=%s"
    return query, values
