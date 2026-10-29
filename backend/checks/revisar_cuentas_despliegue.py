"""Auditoría de solo lectura. Ejecutar con `python -m checks.revisar_cuentas_despliegue`.

No imprime contraseñas, hashes ni correos. Devuelve 1 si encuentra bloqueos.
No es una auditoría completa de seguridad ni reemplaza la revisión humana.
"""
from core.auth import verify_password
from repositories.usuario_repository import UsuarioRepository


def main():
    repo = UsuarioRepository()
    activos = [u for u in repo.find_all() if u.get("activo")]
    pruebas = [u for u in activos if (
        u["email"].lower().endswith(("@example.org", "@example.com", "@example.net"))
        or ".tfg26@" in u["email"].lower()
    )]
    print(f"Cuentas activas identificadas como prueba: {len(pruebas)}")
    # Credenciales históricas públicas del acceso rápido, ya retirado del cliente.
    predeterminadas = 0
    for email, clave in (("admin@universidad.es", "admin123"),
                         ("ana.garcia@universidad.es", "prof123")):
        usuario = repo.find_by_email(email)
        if usuario and usuario.get("activo") and verify_password(clave, usuario["password_hash"]):
            predeterminadas += 1
    print(f"Cuentas activas con clave inicial conocida: {predeterminadas}")
    if pruebas or predeterminadas:
        print("BLOQUEADO: no publicar esta base de datos hasta revisar/desactivar las cuentas de prueba y renovar las claves iniciales.")
        return 1
    print("Sin coincidencias conocidas. Revisar además cuentas anonimizadas, claves compartidas y secretos del servidor.")
    return 0


if __name__ == "__main__":
    from db.connection import cerrar_pool
    try:
        resultado = main()
    finally:
        cerrar_pool()
    raise SystemExit(resultado)
