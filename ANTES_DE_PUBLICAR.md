# Cuentas antes del despliegue universitario

El acceso rápido se ha eliminado del login y sus contraseñas ya no se incluyen en ese componente del cliente. El acceso normal sigue funcionando.

La revisión local del 8 de octubre de 2026 encontró ocho cuentas TFG de prueba activas y el administrador histórico con su contraseña inicial. No se han cambiado contraseñas, desactivado cuentas ni modificado adjudicaciones locales.

## Puerta de revisión antes de publicar

Ejecutar sobre la base de datos del servidor, antes de exponerlo:

```powershell
docker compose run --rm --no-deps backend python -m checks.revisar_cuentas_despliegue
```

Si devuelve código 1, detener el despliegue. Esta comprobación es manual: no constituye un bloqueo automático del servidor.

1. Renovar la contraseña del administrador mediante Mi perfil, con una clave única y no compartida. Verificar el acceso nuevo antes de desactivar ninguna cuenta administrativa.
2. Desactivar en el servidor las cuentas del escenario TFG y cualquier otra cuenta ficticia. No trasladar sin revisión la base local de demostración.
3. Revisar las demás cuentas anonimizadas y contraseñas compartidas. La ausencia de coincidencias conocidas no garantiza que todas sean seguras.
4. Configurar secretos exclusivos del servidor (base de datos, JWT y correo), fuera del repositorio. Rotar las credenciales que se hayan compartido en conversaciones o documentos.
5. Repetir la comprobación y probar inicio/cierre de sesión con las cuentas institucionales definitivas.

No se han automatizado cambios de contraseña ni desactivaciones para evitar dejar sin acceso al administrador o impedir la demostración local del TFG.
