# GestUAL — entrega del TFG

Fecha de preparación: 28 de octubre de 2026.
Autor: Francisco Javier Trujillo Coca.

## Contenido
- backend/: API FastAPI, dominio, persistencia, motor, migraciones y pruebas.
- frontend/: aplicación Next.js, configuración y dependencias fijadas en package-lock.json.
- backend/integration_real/: esquema sin datos, cuatro pruebas PostgreSQL, dos recorridos Playwright y ejecutor aislado.
- output/evaluacion_tfg/: evidencias finales automatizadas, instancias y experimentos del motor. Los límites de 1, 10 y 30 segundos son condiciones experimentales distintas, no versiones antiguas del programa.
- INSTALACION.md: configuración de la aplicación y ejecución de las pruebas.
- MANIFIESTO_SHA256.json: huellas de todos los archivos del paquete.

No se incluyen dependencias instaladas, compilaciones, cachés, archivos privados .env, volcados de datos, utilidades antiguas de mantenimiento, borradores de memoria ni entregas anteriores. La memoria definitiva se entrega aparte.

No se ha elegido una licencia de distribución. La entrega académica no implica una licencia de software libre.

## Evidencia automatizada final
Las 319 pruebas se ejecutaron y superaron el 28 de octubre de 2026. La cobertura conjunta del backend es 60,86 %. Los XML, resumen, cobertura, capturas y huellas están en output/evaluacion_tfg/verificacion_entrega_20261028. Consultar COMPROBACION_ENTREGA.md para el diagnóstico y alcance de la verificación.

Se incluyen siete capturas y registros del caso práctico en output/capturas_atc/, el inventario de 319 casos contrastado con los XML, las versiones y la cobertura combinada. Véase TRAZABILIDAD.md en la carpeta de verificación.

## Publicación del código en GitHub
Este repositorio contiene el código y las evidencias seleccionadas para la entrega académica del TFG.
No incluye una base de datos de producción ni credenciales operativas. Antes de cualquier
despliegue público, consultar [ANTES_DE_PUBLICAR.md](ANTES_DE_PUBLICAR.md).

El archivo binario `.coverage` del ordenador de desarrollo no se distribuye para evitar
exponer rutas locales del equipo. Los resultados de cobertura reproducibles para su consulta
se conservan en los informes JSON y XML de `output/evaluacion_tfg/verificacion_entrega_20261028/`.
El archivo `MANIFIESTO_SHA256.json` se ha actualizado para esta edición publicable.

Para la primera publicación en GitHub, crear un repositorio vacío llamado `GestUAL-TFG`
y ejecutar `Publicar_GestUAL_GitHub.ps1` desde el directorio extraído con Git instalado.
No se incorpora licencia de software libre: ver el apartado anterior de este README.
