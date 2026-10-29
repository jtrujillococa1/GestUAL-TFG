import os
import sys
import json
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ['MPLCONFIGDIR'] = str(ROOT / 'tmp/matplotlib_tfg')
sys.path.insert(0, str(ROOT / 'tmp/plotdeps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MultipleLocator

BASE = Path(__file__).parent
OUT = BASE / 'evolucion_elecciones'
OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})
fig, axes = plt.subplots(3, 1, figsize=(9, 9), sharex=True, layout='constrained')
allrows = []
for strategy, label, color, marker in [('conservadora', 'Conservadora', '#166b8b', 'o'), ('adversa', 'Adversa', '#ad4824', 's')]:
    rows = json.loads((BASE / f'timeline_{strategy}.json').read_text(encoding='utf-8'))
    xs = [r['turno'] for r in rows]
    times = [r['segundos'] for r in rows]
    risks = [r['riesgo']['riesgo'] for r in rows]
    coverage = [r['cobertura'] for r in rows]
    axes[0].plot(xs, times, color=color, marker=marker, markersize=4, label=label)
    axes[1].plot(xs, risks, color=color, marker=marker, markersize=4, linestyle='--' if strategy=='adversa' else '-', label=label)
    axes[2].plot(xs, coverage, color=color, marker=marker, markersize=4, linestyle='--' if strategy=='adversa' else '-', label=label)
    for r in rows:
        allrows.append(dict(secuencia=strategy, turno=r['turno'], segundos=r['segundos'], indice_estructural=r['riesgo']['riesgo'], cobertura_aceptada=r['cobertura'], estado=r['estado'], aceptado=r['aceptado']))
axes[0].set(title='(a) Tiempo de comprobación de la propuesta', ylabel='Tiempo del motor (s)', ylim=(0,2.6))
axes[0].yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:g}'.replace('.', ',')))
axes[0].annotate('Intento 16: 2,264 s\nInviabilidad demostrada', xy=(16,2.2640391), xytext=(9,1.65), arrowprops={'arrowstyle':'->','color':'#444'}, fontsize=9)
axes[0].legend(loc='upper left', frameon=False, ncol=2)
axes[1].set(title='(b) Índice estructural y clasificación del intento rechazado', ylabel='Índice (0-100)', ylim=(-4,112))
axes[1].plot([16,16],[40,100],color='#ad4824',linestyle=':',linewidth=1)
axes[1].scatter([16],[100],marker='x',s=65,color='#ad4824',zorder=5)
axes[1].annotate('100: clasificación de opción inviable\n40: índice del estado hipotético',xy=(16,100),xytext=(1,76),arrowprops={'arrowstyle':'->','color':'#444'},fontsize=9)
axes[2].set(title='(c) Cobertura del reparto aceptado', ylabel='Horas aceptadas (%)', ylim=(-3,108), xlabel='Turno de elección (0 = estado inicial)')
axes[2].annotate('Rechazo: se mantiene el 81,986 %',xy=(16,81.986),xytext=(7,12),arrowprops={'arrowstyle':'->','color':'#444'},fontsize=9,bbox={'facecolor':'white','edgecolor':'none','pad':2})
for ax in axes:
    ax.set_xlim(-.25,18.3)
    ax.xaxis.set_major_locator(MultipleLocator(1))
    ax.grid(alpha=.22)
    ax.spines[['top','right']].set_visible(False)
fig.savefig(OUT/'evolucion_elecciones_atc.png',dpi=240)
fig.savefig(OUT/'evolucion_elecciones_atc.svg')
with (OUT/'datos_evolucion.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(allrows[0])); w.writeheader(); w.writerows(allrows)
# Verify a shared dated interval in the preserved input, rather than weekly labels.
snapshot=json.loads((BASE/'instantanea.json').read_text(encoding='utf-8-sig'))
activities=[a for a in snapshot['actividades'] if a['id'] in [576,636,640]]
sessions=[next(h for h in a['horario_detallado'] if h['fecha']=='2026-11-19') for a in activities]
assert max(h['inicio'] for h in sessions)=='17:00'
assert min(h['fin'] for h in sessions)=='18:30'
(OUT/'horarios_bloqueo.json').write_text(json.dumps([{'codigo':a['codigo'],'asignatura':a['nombre_asignatura'],'grupo':a['tipo']+' '+a['codigo_grupo'],'sesion':h} for a,h in zip(activities,sessions)],ensure_ascii=False,indent=2),encoding='utf-8')
print(OUT)
