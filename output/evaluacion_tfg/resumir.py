import sys,json,csv,statistics,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tmp/plotdeps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path(__file__).parent
rows=json.loads((OUT/'barrido.json').read_text())
groups=collections.defaultdict(list)
for r in rows:groups[(r['familia'],r['profesores'],r['modo'])].append(r)
summary=[]
for (family,n,mode),rs in groups.items():
    perseed=[statistics.median(x['segundos'] for x in rs if x['semilla']==seed) for seed in range(5)]
    summary.append(dict(familia=family,profesores=n,actividades=4*n,modo=mode,ejecuciones=len(rs),viables=sum(x['estado']=='viable' for x in rs),indeterminadas=sum(x['estado']=='indeterminado' for x in rs),inviables=sum(x['estado']=='inviable' for x in rs),mediana_entre_instancias=statistics.median(perseed),minimo=min(x['segundos'] for x in rs),maximo=max(x['segundos'] for x in rs),scip=sum(bool(x['solver']) for x in rs),respaldo_heuristico=sum(x['heuristico'] for x in rs)))
def csvwrite(name,rs):
    with (OUT/name).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
csvwrite('resumen_barrido.csv',summary)
plt.rcParams.update({'font.size':10})
fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True,layout='constrained')
timeline=[]
for name,color in [('conservadora','#17669d'),('adversa','#b44a22')]:
    rs=json.loads((OUT/f'timeline_{name}.json').read_text())
    xx=[r['turno'] for r in rs]
    rr=[None if r['estado']=='indeterminado' else 100 if r['estado']=='inviable' else r['riesgo']['riesgo'] for r in rs]
    axes[0].plot(xx,rr,'o-',label=name.capitalize(),color=color)
    axes[1].plot(xx,[r['cobertura'] for r in rs],'o-',label=name.capitalize(),color=color)
    for r,score in zip(rs,rr):
        timeline.append(dict(secuencia=name,turno=r['turno'],profesor=r.get('profesor'),riesgo_estructural=r['riesgo']['riesgo'],riesgo_evaluacion=score,cobertura_confirmada=r['cobertura'],estado=r['estado'],aceptado=r['aceptado'],segundos=r['segundos']))
        if not r['aceptado']:
            axes[0].annotate('Intento inviable: no se incorpora',xy=(r['turno'],score),xytext=(r['turno']-7,98),arrowprops={'arrowstyle':'->'},fontsize=9)
axes[0].set(ylabel='Índice de riesgo (0–100)',ylim=(-3,110),title='Arquitectura de Computadores · simulación por turnos')
axes[1].set(ylabel='Docencia confirmada (%)',xlabel='Turno simulado (mismo orden de docentes)',ylim=(-3,105),xticks=list(range(19)))
for ax in axes:ax.grid(alpha=.2);ax.legend(loc='upper left')
fig.savefig(OUT/'linea_temporal.png',dpi=180);fig.savefig(OUT/'linea_temporal.svg');plt.close(fig)
csvwrite('linea_temporal.csv',timeline)
fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
for mode,ax in zip(['factibilidad','optimizacion'],axes):
    for family in ['libre','cuatrimestre','solapes']:
        rr=[r for r in summary if r['familia']==family and r['modo']==mode]
        ax.plot([r['profesores'] for r in rr],[r['mediana_entre_instancias'] for r in rr],'o-',label=family)
    ax.set(yscale='log',xlabel='Profesores (4 actividades por profesor)',ylabel='Tiempo observado (s, escala logarítmica)',title=mode.capitalize())
    ax.grid(alpha=.2);ax.legend()
fig.suptitle('Barrido: mediana de las medianas por instancia · límite SCIP 1 s')
fig.savefig(OUT/'barrido_tiempos.png',dpi=180);fig.savefig(OUT/'barrido_tiempos.svg');plt.close(fig)
lines=['# Resultados experimentales de GestUAL','', '## Alcance y reproducción','',
'Se realizaron 450 ejecuciones: 75 instancias (5 tamaños × 3 familias × 5 semillas), dos modos solicitados y tres repeticiones. Todas parten de un testigo factible comprobado. Caché desactivada; límite de SCIP de 1 segundo por llamada, distinto del valor predeterminado de 10 segundos de la aplicación. El tiempo medido incluye preparación y posibles respaldos, por lo que puede superar un segundo.',
'', 'Las instancias libres y con cuatrimestres utilizan el camino de transporte sin SCIP; pedir optimización en ese camino no acredita un óptimo. Las instancias con solapes sí invocan SCIP. Los resultados indeterminados se conservan: no son pruebas de inviabilidad. Los tiempos incluyen todas las ejecuciones; la mediana por tamaño se calcula sobre las medianas de las cinco instancias. No es una prueba de concurrencia ni de navegador.',
'', '## Arquitectura de Computadores','',
'La instantánea contiene 18 docentes, 94 cuotas de actividad, 2.237,2 horas y 183 pares incompatibles. Todos los docentes tienen disponibilidad AMBOS. La base ya tenía el reparto completo; las simulaciones reinician únicamente las elecciones en memoria, sin cambiar los datos ni escribir en PostgreSQL. Dos perfiles tienen es_psi activado: su carga se conserva en el modelo; su adjudicación desde la aplicación requiere gestión autorizada, no elección autónoma del perfil PSI.',
'', 'Ambas secuencias conservan el orden del repositorio. La conservadora elige, entre tres soluciones completas con distinto orden de actividades, el bloque del profesor con menor índice estructural. La adversa añade doce bloques aleatorios localmente compatibles y de carga completa, escoge mayor riesgo y, en empate, prioriza esos bloques locales. Es una búsqueda ilustrativa reproducible, no una política óptima ni un muestreo representativo de decisiones humanas. Se conserva una primera exploración con desempate diferente que terminó sin bloqueo.',
'', 'La conservadora completa el 100 % en 18 turnos. Su índice es 25 hasta el turno 15, 40 en el 16, 85 en el 17 y 0 al terminar. La adversa conserva 81,986 % confirmado tras 15 turnos; el intento 16 es inviable y no se incorpora. Su índice estructural era 40; la evaluación de una opción inviable muestra 100 por la regla de la aplicación. La gráfica diferencia el estado hipotético del intento de la cobertura confirmada.',
'', '**Conclusión sobre el indicador:** no es una probabilidad de fracaso. Puede aumentar al reducirse el número de docentes restantes incluso en una secuencia viable. El contraste demuestra por qué es necesaria la comprobación global; no demuestra que el índice anticipe gradualmente todos los bloqueos. No se cambió la fórmula para producir curvas esperadas.',
'', '## Barrido: resultados','', '|Familia|Docentes|Modo|Viables / ejecuciones|Indeterminadas|Mediana (s)|', '|---|---:|---|---:|---:|---:|']
for r in summary:lines.append(f"|{r['familia']}|{r['profesores']}|{r['modo']}|{r['viables']}/{r['ejecuciones']}|{r['indeterminadas']}|{r['mediana_entre_instancias']:.4f}|")
lines+=['','## Archivos','', 'Los JSON de instancias conservan las entradas y el testigo; barrido.jsonl y barrido.json contienen cada ejecución. Los CSV y SVG/PNG permiten incorporar los resultados a la memoria. entorno.json identifica versiones y huellas del motor. Los participantes están seudonimizados.', '', 'Ejecutar desde la raíz: `backend/.venv/Scripts/python.exe output/evaluacion_tfg/ejecutar.py barrido`. Las líneas temporales se reproducen con `timeline`; `--adversa` ejecuta solo la adversa. La herramienta no importa repositorios ni abre conexiones a la base de datos. La verificación independiente comprueba cargas, cuotas, disponibilidad, solapes y elecciones fijadas de cada solución viable.', '', 'Pendiente: reproducir la demostración en una copia de la aplicación para capturas y contrastar con el tutor si desea un riesgo normalizado por avance. No se han sustituido aún capítulos de la memoria.']
(OUT/'RESULTADOS.md').write_text('\n'.join(lines),encoding='utf8')
print('Resumen y figuras guardados')
