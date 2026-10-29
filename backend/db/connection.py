import psycopg
from contextlib import contextmanager
from psycopg.rows import dict_row
from threading import Lock
from core.config import settings

DB_CONFIG = {
    "host": settings.DB_HOST,
    "dbname": settings.DB_NAME,
    "user": settings.DB_USER,
    "password": settings.DB_PASSWORD,
    "port": settings.DB_PORT,
}


# El dashboard y la ordenación realizan muchas lecturas pequeñas. Reutilizar
# conexiones evita que su coste de red supere al de las propias consultas. El
# pool se abre solo cuando se accede a él, por lo que los scripts y pruebas que
# no usan PostgreSQL no consumen conexiones.
_pool = None
_pool_lock = Lock()


def _configurar_conexion_pool(conn) -> None:
    """Mantiene la misma codificación explícita de las conexiones directas."""
    with conn.cursor() as cur:
        cur.execute("SET client_encoding TO 'UTF8'")
    # Los callbacks de psycopg_pool deben dejar la conexión fuera de una
    # transacción para que pueda entregarse inmediatamente a un repositorio.
    conn.commit()


def obtener_pool():
    """Obtiene el pool compartido de conexiones PostgreSQL de forma diferida."""
    global _pool
    if _pool is not None:
        return _pool

    with _pool_lock:
        if _pool is None:
            # psycopg_pool se importa aquí para mantener importables los
            # módulos de dominio en pruebas que no necesitan la base de datos.
            from psycopg_pool import ConnectionPool

            _pool = ConnectionPool(
                conninfo="",
                kwargs=DB_CONFIG,
                min_size=settings.DB_POOL_MIN_SIZE,
                max_size=max(settings.DB_POOL_MIN_SIZE, settings.DB_POOL_MAX_SIZE),
                timeout=settings.DB_POOL_TIMEOUT_SECONDS,
                max_idle=settings.DB_POOL_MAX_IDLE_SECONDS,
                configure=_configurar_conexion_pool,
                open=True,
            )
    return _pool


def cerrar_pool() -> None:
    """Cierra las conexiones reutilizables al apagar la aplicación."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None

def obtener_conexion():
    """Abre una conexión independiente para scripts de mantenimiento puntuales.

    Los repositorios usan ``conexion_ctx`` y se benefician del pool. Esta
    función se conserva para scripts que controlan su propia transacción.
    """
    conn = psycopg.connect(**DB_CONFIG)
    with conn.cursor() as cur:
        cur.execute("SET client_encoding TO 'UTF8'")
    conn.commit()
    return conn

@contextmanager
def conexion_ctx():
    with obtener_pool().connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

@contextmanager
def cursor_ctx():
    with conexion_ctx() as conn:
        cursor = conn.cursor(row_factory=dict_row)
        try:
            yield cursor
        finally:
            cursor.close()
