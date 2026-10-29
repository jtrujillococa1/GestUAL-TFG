"""Reevaluación selectiva sin acceso a base de datos; conserva campañas anteriores."""
import json,hashlib,sys,platform,time
from pathlib import Path
import ejecutar as e

out=e.OUT/'ampliacion_selectiva_20261026'
out.mkdir(exist_ok=True)
old=json.loads((e.OUT/'limite_10s/barrido.json').read_text(encoding='utf8'))
cases=[r for r in old if r['estado']=='indeterminado']
assert len(cases)==8
prior=json.loads((e.OUT/'limite_10s/entorno.json').read_text(encoding='utf8'))
hashes={p:hashlib.sha256((e.ROOT/p).read_bytes()).hexdigest() for p in prior['codigo_sha256']}
changed=[p for p,h in hashes.items() if h!=prior['codigo_sha256'][p]]
assert all(Path(p).name=='reparacion_conflictos.py' for p in changed),'Cambios en el motor de asignación'
assert 'solver.reparacion_conflictos' not in sys.modules
meta=dict(python=sys.version,ortools=e.ortools.__version__,plataforma=platform.platform(),procesador=platform.processor(),fecha=time.strftime('%Y-%m-%d %H:%M:%S'),cache=False,codigo_sha256=hashes,diseno='Solo las ocho ejecuciones indeterminadas a 10 s; nuevas ejecuciones desde cero a 30 s, no reanudaciones.')
meta['cambios_fuera_del_calculo']=changed
(out/'entorno.json').write_text(json.dumps(meta,indent=2),encoding='utf8')
dest=out/'resultados.jsonl'
rows=[json.loads(x) for x in dest.read_text(encoding='utf8').splitlines()] if dest.exists() else []
done={(r['semilla'],r['repeticion']) for r in rows}
for oldr in cases:
    key=(oldr['semilla'],oldr['repeticion'])
    if key in done:continue
    data=json.loads((e.OUT/f"instancia_solapes_36_{oldr['semilla']}.json").read_text(encoding='utf8'))
    ps,acts=data['profesores'],data['actividades']
    for p in ps:p['horas_objetivo_por_area']={int(k):v for k,v in p['horas_objetivo_por_area'].items()}
    ident=hashlib.sha256(json.dumps([ps,acts],sort_keys=True).encode()).hexdigest()
    assert ident==oldr['sha256']==data['sha256']
    r,t=e.resolver([],ps,acts,heur=False,optim=True,limit=30000)
    row=dict(semilla=key[0],repeticion=key[1],limite_ms=30000,segundos=t,estado=e.estado(r),verificada=bool(r.get('viable')),solver=r.get('observacion_solver'),sin_optimizacion=r.get('sin_optimizacion'),divididas=r.get('actividades_divididas'),repartos=r.get('total_repartos'),sha256=ident,segundos_originales=oldr['segundos'])
    (out/f"respuesta_semilla_{key[0]}_rep_{key[1]}.json").write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
    with dest.open('a',encoding='utf8') as f:f.write(json.dumps(row)+'\n')
    rows.append(row)
    print(json.dumps(row),flush=True)
(out/'resultados.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
print('FINALIZADO',len(rows),flush=True)
