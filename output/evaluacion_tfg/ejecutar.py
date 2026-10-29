"""Experimentos sin conexiones a la base de datos. Ejecutar desde la raíz."""
import os,sys,json,time,random,hashlib,platform,statistics,copy
from pathlib import Path
from collections import defaultdict
os.environ['DB_PASSWORD']='offline-no-db'
os.environ['JWT_SECRET_KEY']='offline-experiment-not-used-for-authentication'
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from solver.engine import resolver_reparto
from solver.compatibilidad import construir_incompatibilidades
from domain.ordenacion.conflictos import preparar_contexto_riesgo,calcular_riesgo_estado
from domain.ordenacion.disponibilidad import profesor_disponible_para_actividad
import ortools
from ortools.linear_solver import pywraplp
OUT=Path(__file__).parent
SOLVES=[]
_create=pywraplp.Solver.CreateSolver
class SolverObservado:
    def __init__(self,solver):self.solver=solver
    def __getattr__(self,name):return getattr(self.solver,name)
    def Solve(self,*args):
        status=self.solver.Solve(*args)
        SOLVES.append(dict(status=int(status),iterations=self.solver.iterations(),nodes=self.solver.nodes()))
        return status
pywraplp.Solver.CreateSolver=staticmethod(lambda name: SolverObservado(_create(name)))

def nombre(p): return f"{p['apellidos']}, {p['nombre']}"
def estado(r): return 'indeterminado' if r.get('indeterminado') else ('viable' if r.get('viable') else 'inviable')
def guardar(name,data): (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
def eleccion(p,a,h): return dict(profesor=nombre(p),actividad_id=a['id'],codigo=a['codigo'],tipo=a['tipo'],codigo_grupo=a['codigo_grupo'],horas=round(h,1))

def verificar(r,ps,acts,forced):
    if not r.get('viable'): return
    asign={};byid={a['id']:a for a in acts};pairs=construircompat(acts)
    for p,row in zip(ps,r['reparto']):
        assert row['profesor']==p['nombre']
        own={}
        for x in row['actividades']:
            aid=x['actividad_id'];h=round(x['horas']*10)
            assert h>0 and profesor_disponible_para_actividad(p,byid[aid])
            assert p['area_id']==byid[aid]['area_id']
            own[aid]=h;asign[(nombre(p),aid)]=h
        assert sum(own.values())==round(p['horas_objetivo']*10)
        assert not any(a in own and b in own for a,b in pairs)
    for a in acts: assert sum(h for (_,aid),h in asign.items() if aid==a['id'])==round(a['horas_totales']*10)
    for e in forced: assert asign.get((e['profesor'],e['actividad_id']),0)==round(e['horas']*10)

def construircompat(acts):
    raw=construir_incompatibilidades(acts)
    return raw

def resolver(es,ps,acts,heur=True,optim=False,limit=1000):
    SOLVES.clear()
    t=time.perf_counter()
    r=resolver_reparto(es,ps,acts,usar_cache=False,preferir_heuristico=heur,solo_factibilidad=not optim,tiempo_limite_ms=limit)
    elapsed=time.perf_counter()-t
    r['observacion_solver']=list(SOLVES)
    verificar(r,ps,acts,es)
    return r,elapsed

def sintetico(n,seed,family):
    rng=random.Random(seed);ps=[];acts=[];witness=[]
    for i in range(n):
        p=dict(id=i+1,nombre=f'P{i+1}',apellidos='Sintetico',area_id=1,area_ids=[1],horas_objetivo=12,carga_docente=12,horas_objetivo_por_area={1:12},disponibilidad_cuatrimestre='SEGUNDO' if family!='libre' and i%3==0 else 'AMBOS')
        ps.append(p)
        slots=rng.sample(range(8),4)
        for j,slot in enumerate(slots):
            period='C2' if p['disponibilidad_cuatrimestre']=='SEGUNDO' else rng.choice(['C1','C2'])
            a=dict(id=4*i+j+1,codigo=f'A{4*i+j+1}',nombre_asignatura='Sintetica',tipo='GD',codigo_grupo='A',grupo='A',area_id=1,horas_totales=3,duracion=period,requiere_horario=family=='solapes',horario_confirmado=family=='solapes',origen_horario='SINTETICO',dias='Lunes',horario=f'{8+slot:02d}:00-{9+slot:02d}:00')
            acts.append(a);witness.append(eleccion(p,a,3))
    rng.shuffle(acts)
    return ps,acts,witness

def barrido():
    rows=[]
    (OUT/'barrido.jsonl').write_text('',encoding='utf8')
    for family in ['libre','cuatrimestre','solapes']:
      for n in [6,12,18,24,36]:
       for seed in range(5):
        ps,acts,w=sintetico(n,seed,family)
        # Verificación independiente de la solución generadora, sin medirla.
        wr={'viable':True,'reparto':[{'profesor':p['nombre'],'actividades':[e for e in w if e['profesor']==nombre(p)]} for p in ps]}
        verificar(wr,ps,acts,w)
        ident=hashlib.sha256(json.dumps([ps,acts],sort_keys=True).encode()).hexdigest()
        guardar(f'instancia_{family}_{n}_{seed}.json',dict(profesores=ps,actividades=acts,testigo=w,sha256=ident))
        for mode in ['factibilidad','optimizacion']:
         for rep in range(3):
          r,t=resolver([],ps,acts,heur=False,optim=mode=='optimizacion')
          row=dict(familia=family,profesores=n,actividades=len(acts),semilla=seed,repeticion=rep,modo=mode,segundos=t,estado=estado(r),heuristico=r.get('heuristico',False),sin_optimizacion=r.get('sin_optimizacion'),divididas=r.get('actividades_divididas'),repartos=r.get('total_repartos'),sha256=ident,solver=r.get('observacion_solver'))
          rows.append(row)
          with (OUT/'barrido.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(row)+'\n')
       print('BARRIDO',family,n,len(rows),flush=True)
    guardar('barrido.json',rows)

def timeline():
    s=json.loads((OUT/'instantanea.json').read_text(encoding='utf-8-sig'))
    area=next(x for x in s['areas'] if x['codigo']=='AR035');aid=area['id']
    ps=[p for p in s['profesores'] if aid in p['area_ids']]
    assert all(p['area_ids']==[aid] for p in ps), 'No aislar dependencias multiarea'
    for p in ps:p['horas_objetivo_por_area']={int(k):v for k,v in p['horas_objetivo_por_area'].items()}
    acts=[a for a in s['actividades'] if a['area_id']==aid]
    ctx=preparar_contexto_riesgo(ps,acts,aid);total=sum(a['horas_totales'] for a in acts)
    pairs={frozenset(x) for x in construircompat(acts)}
    for strategy in (['adversa'] if '--adversa' in sys.argv else ['conservadora','adversa']):
        es=[];rows=[];rng=random.Random(41026)
        base,t=resolver(es,ps,acts,limit=10000);assert base.get('viable')
        rows.append(dict(turno=0,profesor=None,cobertura=0,riesgo=calcular_riesgo_estado(es,ctx),estado='viable',aceptado=True,segundos=t,elecciones=[]))
        for turn,p in enumerate(ps,1):
            candidates=[]
            # Soluciones completas proporcionan al menos un bloque seguro.
            for k in range(3):
                aa=list(acts);rng.shuffle(aa)
                r,t=resolver(es,ps,aa,limit=1500)
                if r.get('viable'):
                    row=next(row for row in r['reparto'] if row['profesor']==p['nombre'])
                    block=[eleccion(p,next(a for a in acts if a['id']==x['actividad_id']),x['horas']) for x in row['actividades']]
                    candidates.append((calcular_riesgo_estado(es+block,ctx)['riesgo'],block,True))
            if strategy=='adversa':
                used=defaultdict(float)
                for e in es:used[e['actividad_id']]+=e['horas']
                for k in range(12):
                    aa=list(acts);rng.shuffle(aa);left=p['horas_objetivo'];block=[];chosen=[]
                    for a in aa:
                        if not profesor_disponible_para_actividad(p,a) or any(frozenset([a['id'],b]) in pairs for b in chosen):continue
                        h=round(min(left,a['horas_totales']-used[a['id']]),1)
                        if h<=0:continue
                        block.append(eleccion(p,a,h));chosen.append(a['id']);left=round(left-h,1)
                        if left<=0:break
                    if left==0:candidates.append((calcular_riesgo_estado(es+block,ctx)['riesgo'],block,False))
            if not candidates:
                rows.append(dict(turno=turn,estado='sin_candidatos',aceptado=False));break
            candidates.sort(key=lambda x:(x[0],not x[2]),reverse=strategy=='adversa')
            risk,block,known=candidates[0]
            result,t=resolver(es+block,ps,acts,limit=10000)
            accepted=bool(result.get('viable'))
            rows.append(dict(turno=turn,profesor=p['nombre'],cobertura=round(100*sum(x['horas'] for x in es+(block if accepted else []))/total,3),cobertura_hipotetica=round(100*sum(x['horas'] for x in es+block)/total,3),riesgo=calcular_riesgo_estado(es+block,ctx),riesgo_confirmado=calcular_riesgo_estado(es+(block if accepted else []),ctx),estado=estado(result),aceptado=accepted,segundos=t,elecciones=block,diagnostico=result.get('diagnostico')))
            print('ATC',strategy,turn,risk,estado(result),flush=True)
            guardar(f'timeline_{strategy}.json',rows)
            if not accepted:break
            es+=block
        guardar(f'timeline_{strategy}.json',rows)

if __name__=='__main__':
    guardar('entorno.json',dict(python=sys.version,ortools=ortools.__version__,plataforma=platform.platform(),procesador=platform.processor(),limite_solver_ms=1000,cache=False,fecha=time.strftime('%Y-%m-%d %H:%M:%S'),codigo_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'backend').glob('solver/*.py')}))
    if sys.argv[-1]=='barrido':barrido()
    else:timeline()
