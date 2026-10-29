# Resultados experimentales de GestUAL

## Alcance y reproducción

Los cálculos se ejecutaron en Windows con el entorno Python local del proyecto, no dentro del contenedor. OR-Tools es 9.14.6206. Se comprobó que engine.py, compatibilidad.py, conflictos.py y reparto_heuristico.py coinciden byte a byte con los del contenedor. Los tiempos no deben presentarse como mediciones de Docker, de la API o del navegador. Las instantáneas de lectura anteriores y posteriores son idénticas.

Resultado global: 385 ejecuciones con solución verificada y 65 indeterminadas. Ninguna instancia sintética se clasificó como inviable. Esto no acredita todas las áreas posibles ni estabilidad bajo concurrencia. Se trata de una primera campaña con límite de un segundo; el límite habitual del proyecto es de diez segundos y conviene contrastarlo antes de formular conclusiones de rendimiento de producción.

Se realizaron 450 ejecuciones: 75 instancias (5 tamaños × 3 familias × 5 semillas), dos modos solicitados y tres repeticiones. Todas parten de un testigo factible comprobado. Caché desactivada; límite de SCIP de 1 segundo por llamada, distinto del valor predeterminado de 10 segundos de la aplicación. El tiempo medido incluye preparación y posibles respaldos, por lo que puede superar un segundo.

Las instancias libres y con cuatrimestres utilizan el camino de transporte sin SCIP; pedir optimización en ese camino no acredita un óptimo. Las instancias con solapes sí invocan SCIP. Los resultados indeterminados se conservan: no son pruebas de inviabilidad. Los tiempos incluyen todas las ejecuciones; la mediana por tamaño se calcula sobre las medianas de las cinco instancias. No es una prueba de concurrencia ni de navegador.

## Arquitectura de Computadores

El intento adverso final se volvió a comprobar con un límite de diez segundos: SCIP devolvió estado 2 (INFEASIBLE). No se trata de un timeout. La prueba se conserva en verificacion_rechazo.json.

La instantánea contiene 18 docentes, 94 cuotas de actividad, 2.237,2 horas y 183 pares incompatibles. Todos los docentes tienen disponibilidad AMBOS. La base ya tenía el reparto completo; las simulaciones reinician únicamente las elecciones en memoria, sin cambiar los datos ni escribir en PostgreSQL. Dos perfiles tienen es_psi activado: su carga se conserva en el modelo; su adjudicación desde la aplicación requiere gestión autorizada, no elección autónoma del perfil PSI.

Ambas secuencias conservan el orden del repositorio. La conservadora elige, entre tres soluciones completas con distinto orden de actividades, el bloque del profesor con menor índice estructural. La adversa añade doce bloques aleatorios localmente compatibles y de carga completa, escoge mayor riesgo y, en empate, prioriza esos bloques locales. Es una búsqueda ilustrativa reproducible, no una política óptima ni un muestreo representativo de decisiones humanas. Se conserva una primera exploración con desempate diferente que terminó sin bloqueo.

La conservadora completa el 100 % en 18 turnos. Su índice es 25 hasta el turno 15, 40 en el 16, 85 en el 17 y 0 al terminar. La adversa conserva 81,986 % confirmado tras 15 turnos; el intento 16 es inviable y no se incorpora. Su índice estructural era 40; la evaluación de una opción inviable muestra 100 por la regla de la aplicación. La gráfica diferencia el estado hipotético del intento de la cobertura confirmada.

**Conclusión sobre el indicador:** no es una probabilidad de fracaso. Puede aumentar al reducirse el número de docentes restantes incluso en una secuencia viable. El contraste demuestra por qué es necesaria la comprobación global; no demuestra que el índice anticipe gradualmente todos los bloqueos. No se cambió la fórmula para producir curvas esperadas.

## Barrido: resultados

|Familia|Docentes|Modo|Viables / ejecuciones|Indeterminadas|Mediana (s)|
|---|---:|---|---:|---:|---:|
|libre|6|factibilidad|15/15|0|0.0017|
|libre|6|optimizacion|15/15|0|0.0013|
|libre|12|factibilidad|15/15|0|0.0060|
|libre|12|optimizacion|15/15|0|0.0067|
|libre|18|factibilidad|15/15|0|0.0113|
|libre|18|optimizacion|15/15|0|0.0094|
|libre|24|factibilidad|15/15|0|0.0189|
|libre|24|optimizacion|15/15|0|0.0198|
|libre|36|factibilidad|15/15|0|0.0391|
|libre|36|optimizacion|15/15|0|0.0440|
|cuatrimestre|6|factibilidad|15/15|0|0.0022|
|cuatrimestre|6|optimizacion|15/15|0|0.0024|
|cuatrimestre|12|factibilidad|15/15|0|0.0061|
|cuatrimestre|12|optimizacion|15/15|0|0.0068|
|cuatrimestre|18|factibilidad|15/15|0|0.0150|
|cuatrimestre|18|optimizacion|15/15|0|0.0163|
|cuatrimestre|24|factibilidad|15/15|0|0.0130|
|cuatrimestre|24|optimizacion|15/15|0|0.0168|
|cuatrimestre|36|factibilidad|15/15|0|0.0431|
|cuatrimestre|36|optimizacion|15/15|0|0.0371|
|solapes|6|factibilidad|15/15|0|0.0572|
|solapes|6|optimizacion|15/15|0|0.0959|
|solapes|12|factibilidad|15/15|0|0.4001|
|solapes|12|optimizacion|15/15|0|0.4233|
|solapes|18|factibilidad|7/15|8|1.1221|
|solapes|18|optimizacion|6/15|9|1.5118|
|solapes|24|factibilidad|6/15|9|2.6364|
|solapes|24|optimizacion|6/15|9|2.3345|
|solapes|36|factibilidad|0/15|15|4.6519|
|solapes|36|optimizacion|0/15|15|4.3251|

## Archivos

Los JSON de instancias conservan las entradas y el testigo; barrido.jsonl y barrido.json contienen cada ejecución. Los CSV y SVG/PNG permiten incorporar los resultados a la memoria. entorno.json identifica versiones y huellas del motor. Los participantes están seudonimizados.

Ejecutar desde la raíz: `backend/.venv/Scripts/python.exe output/evaluacion_tfg/ejecutar.py barrido`. Las líneas temporales se reproducen con `timeline`; `--adversa` ejecuta solo la adversa. La herramienta no importa repositorios ni abre conexiones a la base de datos. La verificación independiente comprueba cargas, cuotas, disponibilidad, solapes y elecciones fijadas de cada solución viable.

Pendiente: reproducir la demostración en una copia de la aplicación para capturas y contrastar con el tutor si desea un riesgo normalizado por avance. No se han sustituido aún capítulos de la memoria.
