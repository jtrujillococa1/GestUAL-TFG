# Campaña con límite SCIP de diez segundos

450 ejecuciones sobre las mismas 75 instancias del ensayo de un segundo, verificadas mediante sus huellas SHA-256. Cinco tamaños (6, 12, 18, 24 y 36 docentes), tres familias, cinco semillas, dos modos y tres repeticiones. Caché desactivada. Equipo: i7-8550U, cuatro núcleos y ocho hilos lógicos, 8 GB de RAM; Windows 11, Python 3.13.7, OR-Tools 9.14.6206. Configuración de hilos predeterminada, sin forzar ocho hilos de búsqueda.

## Resultados

- 442 respuestas viables y comprobadas; 8 indeterminadas; ninguna instancia sintética declarada inviable.
- Factibilidad: 225/225 respuestas viables, incluidas las 15 ejecuciones de la familia con solapes y 36 docentes.
- Optimización: 217/225 respuestas viables. Las ocho indeterminadas pertenecen a la familia con solapes y 36 docentes.
- En las familias sin solapes, el motor utiliza transporte, no SCIP. Las 300 respuestas son válidas, sin atribuirles certificación de optimalidad.
- En la familia con solapes, el modo de optimización certificó 67 óptimos de 75 ejecuciones: 15/15 por tamaño hasta 24 docentes y 7/15 con 36. Las otras ocho no devolvieron solución.
- El ensayo de un segundo produjo 385 respuestas viables y 65 indeterminadas. La comparación no es un experimento de concurrencia ni una garantía de latencia de la API.

## Tiempos

Se mide la llamada completa al motor, excluyendo el verificador posterior. Incluye construcción, resolución y respaldos; puede superar el presupuesto de diez segundos de SCIP. La mediana presentada es la mediana de las cinco medianas por instancia, cada una obtenida de tres repeticiones. Se conservan las ejecuciones indeterminadas en el cálculo. Los rangos completos están en resumen.csv.

En solapes, medianas F/O (segundos): 6 docentes 0,049/0,064; 12 docentes 0,263/0,441; 18 docentes 1,047/1,822; 24 docentes 3,247/3,539; 36 docentes 8,352/11,722. La última cifra no es tiempo hasta el óptimo: incluye las ocho respuestas indeterminadas.

## Arquitectura de Computadores

Se reutilizan las dos secuencias simuladas y verificadas con presupuesto de hasta diez segundos, sobre la instantánea conservada de AR035: 18 perfiles, 94 actividades y 2.237,2 horas. No son ejecuciones de la interfaz ni adjudicaciones nuevas en PostgreSQL.

La secuencia conservadora completa el reparto. La adversa mantiene 81,986 % asignado tras quince turnos y rechaza el intento dieciséis. Tras ese intento quedarían tres actividades pendientes incompatibles por pares (40152207 GT C1, 70354202 GD C y 70354203 GD C) y solo dos docentes con carga disponible. Se conservan una comprobación independiente de este argumento y el estado INFEASIBLE de SCIP.

El índice estructural vale 25 hasta el turno quince en ambas secuencias. En la conservadora sube a 40 y 85, manteniendo viabilidad, y baja a cero al finalizar. En la adversa el intento tiene índice estructural 40 pero la evaluación global es inviable y se representa con 100 conforme a la regla de la aplicación. No es una probabilidad estadística ni una alerta gradual garantizada.

## Artefactos

barrido.json y barrido.jsonl contienen cada ejecución; resumen.json y resumen.csv contienen estadísticas; barrido_10s.png y linea_temporal_atc.png son las figuras para la memoria. Las versiones SVG se conservan para edición. Las instancias, el guion y la instantánea están en el directorio superior. No se han modificado archivos de la aplicación ni su base de datos.
