# Instalación y comprobación

## Aplicación
Requisitos: Docker Desktop con Compose, acceso a Internet para construir las imágenes y PostgreSQL configurado con el esquema y datos de la aplicación. Las imágenes utilizan Python 3.13 y Node.js 22.

Desde la raíz del paquete, en PowerShell:

```powershell
Copy-Item backend/.env.example backend/.env
```

Editar backend/.env con la conexión y una JWT_SECRET_KEY aleatoria de al menos 32 caracteres. Puede generarse con `python -c "import secrets; print(secrets.token_urlsafe(48))"`. No distribuir ese archivo.
Para PostgreSQL en el equipo anfitrión con Docker Desktop, DB_HOST suele ser host.docker.internal. localhost dentro del contenedor designa al propio contenedor. Configurar permisos de conexión y el puerto correspondiente. SMTP es opcional.

```powershell
docker compose up --build -d
docker compose ps
docker compose logs --tail=100 backend
```

Interfaz: http://localhost:9002. API: http://localhost:8000/docs.
El compose de la aplicación no crea PostgreSQL ni una cuenta administrativa: requiere una base preparada. No se incluye un volcado de la base de trabajo. backend/integration_real/schema.sql y las migraciones permiten construir la base aislada de pruebas mediante el ejecutor descrito abajo; no son una demostración precargada para uso general. No ejecutar migraciones indiscriminadamente sobre una base existente.

## Batería reproducible con base aislada y navegador
Requisitos: Windows/PowerShell, Python 3.13, Node.js 22, Docker Desktop y Google Chrome. Puertos libres: 3000, 8011 y 55432.

Desde la raíz:

```powershell
py -3.13 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
npm ci --prefix frontend
npm ci --prefix backend/integration_real/browser
powershell -ExecutionPolicy Bypass -File backend/integration_real/ejecutar.ps1
```

El ejecutor crea o utiliza exclusivamente el contenedor marcado gestual-tfg-tests-20261027, prepara el esquema y datos ficticios, ejecuta las 319 pruebas y genera una nueva carpeta de informes. No lee backend/.env. Las contraseñas literales de integration_real son credenciales públicas de este entorno local desechable, no credenciales de la aplicación. Consultar backend/integration_real/README.md para alcance y aislamiento.

## Experimentos del motor
Los scripts e instancias están en output/evaluacion_tfg. Conservar las evidencias adjuntas antes de repetir experimentos: algunos scripts reutilizan sus rutas de salida. Ejecutarlos en una copia del paquete. Estos experimentos son independientes de las 319 pruebas automatizadas.

Ejecutar la suite principal y las comprobaciones complementarias en procesos separados, tal como hace ejecutar.ps1: las sustituciones de módulos de tests/conftest.py no deben compartirse con los modelos reales de la API. Una invocación conjunta de ambas carpetas produce errores de recopilación.
