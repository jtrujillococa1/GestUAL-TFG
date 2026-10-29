"""Dos recorridos con navegador, frontend, API, JWT y PostgreSQL reales."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import pytest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
REPORT=Path(os.environ.get('GESTUAL_REPORT_DIR',ROOT/'output/evaluacion_tfg/integracion_e2e_20261027')).resolve()

def free_port(port):
    with socket.socket() as s:s.bind(('127.0.0.1',port))

def wait_http(url,process,timeout=150):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if process.poll() is not None:raise RuntimeError('El servidor terminó; consulte su log.')
        try:
            with urllib.request.urlopen(url,timeout=3) as r:
                if r.status==200:return
        except Exception:time.sleep(.5)
    raise TimeoutError(url)

@pytest.fixture(scope='module')
def frontend():
    REPORT.mkdir(parents=True,exist_ok=True)
    free_port(3000)
    env=os.environ.copy()
    env.update(NEXT_PUBLIC_API_URL='http://127.0.0.1:8011',NEXT_PUBLIC_BASE_PATH='',NEXT_TELEMETRY_DISABLED='1')
    with (REPORT/'frontend.log').open('w',encoding='utf-8') as log:
        p=subprocess.Popen(['node',str(ROOT/'frontend/node_modules/next/dist/bin/next'),'dev','--turbopack','--hostname','127.0.0.1','-p','3000'],
            cwd=ROOT/'frontend',env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            wait_http('http://127.0.0.1:3000/login',p)
            yield
        finally:
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True)
            else:p.terminate()
            p.wait(timeout=15)

@pytest.fixture
def application(db,frontend,request):
    free_port(8011)
    env=os.environ.copy();env['GESTUAL_REPORT_DIR']=str(REPORT)
    env['PYTHONIOENCODING']='utf-8'
    with (REPORT/(request.node.name+'.api.log')).open('w',encoding='utf-8') as log:
        p=subprocess.Popen([sys.executable,str(HERE/'serve_covered.py')],cwd=HERE.parent,
            env=env,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,text=True)
        try:
            wait_http('http://127.0.0.1:8011/health',p,30)
            yield db
        finally:
            if p.poll() is None:
                p.stdin.write('stop\n');p.stdin.flush()
            p.wait(timeout=40)
            assert p.returncode==0,'La API debe guardar la cobertura y terminar limpiamente.'

def browser_case(name):
    env=os.environ.copy();env['GESTUAL_REPORT_DIR']=str(REPORT)
    result=subprocess.run(['node',str(HERE/'browser/recorridos.cjs'),name],env=env,cwd=ROOT,
        capture_output=True,text=True,encoding='utf-8',timeout=240)
    (REPORT/(name+'.browser.log')).write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
    assert result.returncode==0,result.stdout+'\n'+result.stderr

def test_e2e_seleccion_confirmacion_y_consulta(application):
    browser_case('confirmacion')
    with application() as c:
        assert c.execute('SELECT actividad_id,horas_asignadas FROM reparto_docente WHERE profesor_id=101').fetchall()==[(1001,6)]
        assert c.execute('SELECT count(*) FROM reparto_docente_borrador WHERE profesor_id=101').fetchone()[0]==0
        assert c.execute("SELECT count(*) FROM ordenacion_eventos WHERE tipo='TURNO_CONFIRMADO' AND area_id=10").fetchone()[0]==1

def test_e2e_rechazo_de_pantalla_obsoleta(application):
    browser_case('obsoleta')
    with application() as c:
        assert c.execute('SELECT count(*) FROM reparto_docente WHERE profesor_id=101').fetchone()[0]==0
        assert c.execute('SELECT actividad_id,horas_asignadas FROM reparto_docente_borrador WHERE profesor_id=101').fetchall()==[(1002,6)]
        assert c.execute("SELECT count(*) FROM ordenacion_eventos WHERE tipo='TURNO_CONFIRMADO' AND area_id=10").fetchone()[0]==0
        assert c.execute('SELECT version FROM ordenacion_areas_control WHERE area_id=10').fetchone()[0]==3
