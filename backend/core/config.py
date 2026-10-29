import os
from typing import List


def _required_env(name: str) -> str:
    """Obtiene una variable imprescindible sin dejar secretos en el código."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Falta configurar la variable de entorno obligatoria {name}.")
    return value


def _required_jwt_secret() -> str:
    secret = _required_env("JWT_SECRET_KEY")
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET_KEY debe tener al menos 32 caracteres.")
    return secret

class Settings:
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_NAME: str = os.getenv("DB_NAME", "ordenacion_docente")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = _required_env("DB_PASSWORD")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    # El pool se crea de forma diferida, por lo que no abre conexiones durante
    # importaciones o pruebas que no acceden a la base de datos.
    DB_POOL_MIN_SIZE: int = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
    DB_POOL_MAX_SIZE: int = int(os.getenv("DB_POOL_MAX_SIZE", "12"))
    DB_POOL_MAX_IDLE_SECONDS: int = int(os.getenv("DB_POOL_MAX_IDLE_SECONDS", "120"))
    DB_POOL_TIMEOUT_SECONDS: int = int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "30"))
    JWT_SECRET_KEY: str = _required_jwt_secret()
    
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:9002",
        "http://127.0.0.1:9002",
    ]
    CORS_ORIGIN_REGEX: str = r"https://.*\.(cloudworkstations|web\.app|firebaseapp)\.com"
    
    # La exportación institucional contiene décimas (p. ej. 20,5 y 0,1).
    # Deben conservarse para que las cuotas de área cierren exactamente.
    HORAS_MINIMAS: float = 0.1
    PASO_HORAS: float = 0.1
    ESCALA_SOLVER: int = 10
    # El límite por entradas conserva los estados recientes; el límite por
    # bytes evita que repartos grandes ocupen memoria de forma no acotada.
    SOLVER_CACHE_MAX_SIZE: int = int(os.getenv("SOLVER_CACHE_MAX_SIZE", "1000"))
    SOLVER_CACHE_MAX_BYTES: int = int(os.getenv("SOLVER_CACHE_MAX_BYTES", str(64 * 1024 * 1024)))
    # La primera solución factible ya cumple todas las restricciones. Limitar
    # la fase de optimización evita bloquear una pantalla en áreas grandes
    # intentando reducir unas pocas divisiones adicionales de grupos.
    SOLVER_MAX_TIME_MS: int = int(os.getenv("SOLVER_MAX_TIME_MS", "10000"))
    
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Ordenación Docente API"
    VERSION: str = "2.0.0"

settings = Settings()
