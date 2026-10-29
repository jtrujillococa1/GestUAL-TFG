# Verificación de entrega — 28 de octubre de 2026

319 pruebas superadas: 261 principales, 52 complementarias, cuatro con PostgreSQL real y dos recorridos E2E. Cero fallos, errores u omisiones. Cobertura conjunta: 3728/6126 líneas (60,86 %); domain: 697/766 (90,99 %); solver: 625/744 (84,01 %). Incluye cobertura de los procesos API de navegador; no mide cobertura JavaScript.

El bloqueo HTTP se reprodujo antes de alcanzar la API, en socketpair/accept durante la creación del bucle asyncio de TestClient. Al permitir conexiones locales en el entorno de ejecución, los ocho casos HTTP pasaron sin modificar las aserciones ni código de aplicación.

Se corrigió ejecutar.ps1: Windows PowerShell perdía las comillas de la plantilla de inspección Docker. Ahora se leen sus etiquetas mediante JSON y se conserva la comprobación de aislamiento.

La batería completa se ejecutó con el entorno instalado de trabajo. Se compararon byte a byte el código, pruebas y configuraciones empaquetados con los archivos ejecutados. No se reinstalaron dependencias desde cero ni se validó un despliegue de producción; los E2E utilizaron Next.js en modo desarrollo.

PostgreSQL de pruebas quedó detenido al finalizar. Las cuentas utilizadas son ficticias. No se modificó la base de uso ni la memoria. Las evidencias históricas permanecen en la carpeta original; el ZIP contiene esta comprobación automatizada final y los experimentos del motor que respaldan la memoria.

Recuperadas las evidencias citadas por los apéndices. El inventario coincide con los 319 casos XML. Se regeneró el informe desde .coverage y coincide con cobertura_total.json por archivo, líneas ejecutadas, ausentes y totales. Esta actualización incorpora documentación y evidencias; no modifica las pruebas ni sus resultados.
