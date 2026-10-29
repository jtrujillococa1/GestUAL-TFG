# Integración con PostgreSQL y recorridos E2E

Cuatro casos ejercitan el repositorio y el contexto transaccional reales. Dos recorren navegador → Next.js → FastAPI → PostgreSQL con login JWT real. No se sustituyen la red, el repositorio ni las respuestas del motor en los recorridos E2E.

## Requisitos y ejecución

- Docker Desktop y la imagen `postgres:16-alpine`.
- Dependencias de backend en `backend/.venv` y frontend en `frontend/node_modules`.
- `npm install --prefix backend/integration_real/browser` (Playwright fijado en package-lock).
- Google Chrome; para otro canal compatible, configurar `GESTUAL_BROWSER_CHANNEL`.
- Puertos locales libres 3000 y 8011. PostgreSQL de pruebas se publica solo en `127.0.0.1:55432`.
- Desde la raíz: `powershell -ExecutionPolicy Bypass -File backend/integration_real/ejecutar.ps1`.

El ejecutor conserva cada campaña en un directorio nuevo. Ejecuta 261 casos principales, 52 complementarios y los seis escenarios reales. Suma la cobertura de líneas sin duplicados, incluyendo los procesos reales de API de las pruebas de navegador. No mide cobertura JavaScript del frontend.

## Aislamiento

El contenedor `gestual-tfg-tests-20261027`, marcado `gestual.purpose=tfg-tests`, contiene únicamente la base `gestual_test`. No se lee `backend/.env`. Las credenciales del código de pruebas son exclusivamente para ese contenedor local desechable.

`schema.sql` contiene solo estructura, extraída de la copia local del proyecto; no incluye filas de usuarios o docencia. La inicialización aplica además las migraciones reales. El esquema se marca y se comprueba antes de cada limpieza. Nunca se reinicializa una base no vacía sin la marca prevista. Los datos de cada escenario se construyen desde cero y son ficticios. No se configura SMTP.

El frontend y la API temporales se detienen al terminar los casos. El contenedor se conserva para repetirlos; puede detenerse con `docker stop gestual-tfg-tests-20261027` y eliminarse con `docker rm gestual-tfg-tests-20261027` una vez detenidas las pruebas. Estas operaciones se refieren solo al contenedor de pruebas.

## Qué acreditan

1. Confirmación: reparto, limpieza del borrador, versión y evento visibles desde una conexión independiente.
2. Reversión: una restricción temporal de la base provoca un error al registrar el evento, después de las escrituras anteriores. Se compara el estado completo de cuatro tablas antes y después; la restricción se elimina en `finally`.
3. Reparación: aprobación de un plan preparado, conservación del área ajena, cantidades, estado, versión y evento. No es una prueba del algoritmo que genera el plan.
4. Concurrencia: dos conexiones esperan el mismo bloqueo real; al liberarlo, una confirma y otra recibe versión obsoleta, sin duplicar reparto ni evento.
5. E2E correcto: login, selección, confirmación, consulta tras recarga y comprobación independiente de los datos persistidos.
6. E2E obsoleto: dos contextos de navegador autenticados; el segundo sustituye Alfa por Beta en el borrador. El primero recibe 409 al confirmar su versión anterior. Se conservan el borrador nuevo y la ausencia de adjudicación.

Estos casos no equivalen a probar todas las pantallas, perfiles, configuraciones de despliegue o cargas concurrentes. Las capturas, estados HTTP e informes XML se guardan junto a la cobertura.

## Conexiones locales y diagnóstico

Ejecutar en un entorno que permita conexiones locales y acceso a Docker. En Windows, TestClient necesita conexiones internas incluso sin servidor HTTP externo. Si se bloquea antes de invocar la ruta, puede diagnosticarse con `-o faulthandler_timeout=15`: una espera en socketpair/accept al crear el bucle asyncio indica que debe revisarse el acceso local del entorno. La comprobación del 28 de octubre pasó los ocho casos HTTP al permitir dicho acceso, sin cambiar sus aserciones ni la aplicación.

El ejecutor inspecciona las etiquetas Docker mediante JSON para ser compatible con Windows PowerShell 5.1 y PowerShell 7.
