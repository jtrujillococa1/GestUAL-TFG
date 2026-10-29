"""API real; parada por stdin para guardar cobertura incluso en Windows."""
import os
import sys
import threading
import uuid
from pathlib import Path
import coverage

assert os.environ['DB_NAME']=='gestual_test' and os.environ['DB_PORT']=='55432'
out=Path(os.environ['GESTUAL_REPORT_DIR'])
cov=coverage.Coverage(data_file=str(out/('.coverage.api.'+uuid.uuid4().hex)),
    source=['api','core','db','domain','models','repositories','services','solver'])
cov.start()
import uvicorn
from main import app
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8011,log_level='warning'))
thread=threading.Thread(target=server.run)
thread.start()
try:
    sys.stdin.readline()
finally:
    server.should_exit=True
    thread.join(timeout=30)
    if thread.is_alive():raise RuntimeError('La API no terminó ordenadamente.')
    cov.stop()
    cov.save()
