"""Repite exactamente las instancias guardadas con límite SCIP de 10 s."""
import json,sys,time,hashlib,platform
from pathlib import Path
import ejecutar as e

OUT=e.OUT/'limite_10s'
OUT.mkdir(exist_ok=True)
DEST=OUT/'barrido.jsonl'

def run():
    prev=[json.loads(x) for x in DEST.read_text(encoding='utf8').splitlines()] if DEST.exists() else []
    done={(r['familia'],r['profesores'],r['semilla'],r['modo'],r['repeticion']) for r in prev}
    meta=dict(python=sys.version,ortools=e.ortools.__version__,plataforma=platform.platform(),procesador=platform.processor(),limite_solver_ms=10000,cache=False,fecha=time.strftime('%Y-%m-%d %H:%M:%S'),codigo_sha256={str(p.relative_to(e.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['solver','domain/ordenacion'] for p in (e.ROOT/'backend'/folder).glob('*.py')})
    (OUT/'entorno.json').write_text(json.dumps(meta,indent=2),encoding='utf8')
    for family in ['libre','cuatrimestre','solapes']:
      for n in [6,12,18,24,36]:
       for seed in range(5):
        instance=json.loads((e.OUT/f'instancia_{family}_{n}_{seed}.json').read_text(encoding='utf8'))
        ps,acts=instance['profesores'],instance['actividades']
        for p in ps:p['horas_objetivo_por_area']={int(k):v for k,v in p['horas_objetivo_por_area'].items()}
        ident=hashlib.sha256(json.dumps([ps,acts],sort_keys=True).encode()).hexdigest()
        assert ident==instance['sha256']
        for mode in ['factibilidad','optimizacion']:
         for rep in range(3):
          if (family,n,seed,mode,rep) in done:continue
          r,t=e.resolver([],ps,acts,heur=False,optim=mode=='optimizacion',limit=10000)
          row=dict(familia=family,profesores=n,actividades=len(acts),semilla=seed,repeticion=rep,modo=mode,segundos=t,estado=e.estado(r),heuristico=r.get('heuristico',False),sin_optimizacion=r.get('sin_optimizacion'),divididas=r.get('actividades_divididas'),repartos=r.get('total_repartos'),sha256=ident,solver=r.get('observacion_solver'),limite_solver_ms=10000)
          prev.append(row)
          with DEST.open('a',encoding='utf8') as f:f.write(json.dumps(row)+'\n')
       print(f'{family} n={n}: {len(prev)}/450',flush=True)
    (OUT/'barrido.json').write_text(json.dumps(prev,indent=2),encoding='utf8')
    print('COMPLETO',flush=True)

if __name__=='__main__':run()
