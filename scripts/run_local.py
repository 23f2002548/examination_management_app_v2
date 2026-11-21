"""Run Flask, Celery worker/beat and a local SMTP inbox. Redis must be running."""
import os
import sys
import socket
import subprocess
from pathlib import Path
import redis

ROOT=Path(__file__).resolve().parent.parent

def port_open(port):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=1): return True
    except OSError: return False

def main():
    try: redis.Redis.from_url(os.environ.get('REDIS_URL','redis://localhost:6379/0'),socket_connect_timeout=3).ping()
    except redis.RedisError as error: raise SystemExit('Start Redis first (see README.md). '+str(error))
    if not (ROOT/'frontend'/'dist'/'index.html').exists(): raise SystemExit('Build the frontend first: cd frontend && npm install && npm run build')
    children=[]
    logs=ROOT/'instance'/'logs'; logs.mkdir(parents=True,exist_ok=True)
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    commands=[
        ('worker',[sys.executable,'-m','celery','-A','worker.celery','worker','--pool=solo','--loglevel=info']),
        ('beat',[sys.executable,'-m','celery','-A','worker.celery','beat','--loglevel=info','--schedule',str(ROOT/'instance'/'celerybeat-schedule')])
    ]
    if not os.environ.get('MAIL_HOST') and not port_open(1025):
        commands.insert(0,('mail',[sys.executable,'scripts/mail_sink.py']))
    try:
        for name,command in commands:
            handle=(logs/(name+'.log')).open('a',encoding='utf-8')
            process=subprocess.Popen(command,cwd=ROOT,stdout=handle,stderr=subprocess.STDOUT,creationflags=flags)
            children.append((process,handle))
        print('Open http://127.0.0.1:5000 | Logs: instance/logs | Demo emails: instance/mail',flush=True)
        subprocess.run([sys.executable,'run.py'],cwd=ROOT,check=True)
    except KeyboardInterrupt:
        pass
    finally:
        for process,handle in children:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill()
            handle.close()

if __name__=='__main__': main()
