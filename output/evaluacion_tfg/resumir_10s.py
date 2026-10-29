import os,sys,json,csv,statistics,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MPLCONFIGDIR']=str(ROOT/'tmp/matplotlib_tfg')
sys.path.insert(0,str(ROOT/'tmp/plotdeps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
BASE=Path(__file__).parent
OUT=BASE/'limite_10s'
rows=json.loads((OUT/'barrido.json').read_text())
previous=json.loads((BASE/'barrido.json').read_text())
assert len(rows)==450 and len(previous)==450
key=lambda r:(r['familia'],r['profesores'],r['semilla'],r['modo'],r['repeticion'])
old={key(r):r for r in previous}
assert all(r['sha256']==old[key(r)]['sha256'] for r in rows)
groups=collections.defaultdict(list)
for r in rows:groups[(r['familia'],r['profesores'],r['modo'])].append(r)
summary=[]
for (family,n,mode),rs in groups.items():
    seeds=[statistics.median(r['segundos'] for r in rs if r['semilla']==seed) for seed in range(5)]
    optimal=sum(mode=='optimizacion' and not r['heuristico'] and bool(r['solver']) and all(s['status']==0 for s in r['solver']) for r in rs)
    summary.append(dict(familia=family,profesores=n,actividades=n*4,modo=mode,n=len(rs),viables=sum(r['estado']=='viable' for r in rs),indeterminadas=sum(r['estado']=='indeterminado' for r in rs),optimas_certificadas=optimal if family=='solapes' and mode=='optimizacion' else None,mediana=statistics.median(seeds),minimo=min(r['segundos'] for r in rs),maximo=max(r['segundos'] for r in rs),viables_1s=sum(old[key(r)]['estado']=='viable' for r in rs)))
(OUT/'resumen.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
with (OUT/'resumen.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
fig,axs=plt.subplots(1,2,figsize=(10.8,4.4),layout='constrained')
for mode,ax in zip(['factibilidad','optimizacion'],axs):
    for family,label in [('libre','Sin restricciones temporales'),('cuatrimestre','Disponibilidad por cuatrimestre'),('solapes','Disponibilidad y solapes')]:
        rs=[r for r in summary if r['modo']==mode and r['familia']==family]
        ax.plot([r['profesores'] for r in rs],[r['mediana'] for r in rs],'o-',label=label)
    ax.set(xlabel='Número de docentes',ylabel='Tiempo observado (s, escala logarítmica)',yscale='log',title=mode.capitalize(),xticks=[6,12,18,24,36])
    ax.grid(alpha=.2);ax.legend(fontsize=7)
fig.suptitle('Barrido de tamaños · límite SCIP de 10 segundos')
for ext in ['png','svg']:fig.savefig(OUT/f'barrido_10s.{ext}',dpi=190)
plt.close(fig)
fig,axs=plt.subplots(2,1,figsize=(10,6.4),sharex=True,layout='constrained')
for name,color in [('conservadora','#17669d'),('adversa','#b44a22')]:
    rs=json.loads((BASE/f'timeline_{name}.json').read_text());ok=[r for r in rs if r['aceptado']]
    axs[0].plot([r['turno'] for r in ok],[r['riesgo']['riesgo'] for r in ok],'o-',color=color,label=name.capitalize())
    axs[1].plot([r['turno'] for r in rs],[r['cobertura'] for r in rs],'o-',color=color,label=name.capitalize())
    if not rs[-1]['aceptado']:
        last=rs[-1];prior=ok[-1]
        axs[0].plot([prior['turno'],last['turno']],[prior['riesgo']['riesgo'],100],'--',color=color)
        axs[0].scatter([last['turno']],[100],marker='x',s=80,color=color)
        axs[0].annotate('Intento inviable (rechazado)',xy=(last['turno'],100),xytext=(8,99),arrowprops={'arrowstyle':'->'},fontsize=9)
axs[0].set(ylabel='Índice de riesgo (0–100)',ylim=(-3,110),title='Arquitectura de Computadores · evolución por turnos')
axs[1].set(ylabel='Docencia asignada en la simulación (%)',xlabel='Turno simulado',ylim=(-3,105),xticks=list(range(19)))
for ax in axs:ax.grid(alpha=.2);ax.legend(loc='upper left',fontsize=9)
for ext in ['png','svg']:fig.savefig(OUT/f'linea_temporal_atc.{ext}',dpi=190)
plt.close(fig)
print('RESULTADOS',collections.Counter(r['estado'] for r in rows))
for r in summary: print(r)
