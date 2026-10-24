"""Bounded ephemeral media worker. Control credentials never appear in download URLs."""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import resource
import secrets
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit, quote

BASE=Path(os.environ.get('MEDIAFLOW_JOB_DIR','/vercel/job'))
FILES=BASE/'files';FILES.mkdir(parents=True,exist_ok=True)
KEY=os.environ['JOB_KEY'];FILE_KEY=os.environ['FILE_KEY'].encode()
ORIGIN=os.environ.get('APP_ORIGIN','https://youtube-playlist-download.vercel.app')
EXPIRES=int(os.environ.get('JOB_EXPIRES_AT',str(int(time.time()*1000)+1200000)))
MAX_FILE=64*1024*1024;MAX_TOTAL=256*1024*1024;MAX_TRANSFER=512*1024*1024;MAX_FILES=20
LOCK=threading.RLock();PROC=None;START=time.monotonic();LIMIT_HIT=False;TRANSFER=0
STATE={'state':'running','message':'Starting download…','files':[],'log':[],'engineVersion':'1.3.0','expiresAt':EXPIRES}


def file_token(name):
    raw=base64.urlsafe_b64encode(json.dumps({'p':'file','n':name,'e':EXPIRES},separators=(',',':')).encode()).decode().rstrip('=')
    mac=hmac.new(FILE_KEY,raw.encode(),hashlib.sha256).hexdigest()
    return raw+'.'+mac


def valid_file_token(token,name):
    try:
        if len(token)>4096:return False
        raw,mac=token.split('.')
        if not hmac.compare_digest(mac,hmac.new(FILE_KEY,raw.encode(),hashlib.sha256).hexdigest()):return False
        value=json.loads(base64.urlsafe_b64decode(raw+'='*(-len(raw)%4)))
        return value=={'p':'file','n':name,'e':EXPIRES} and time.time()*1000<EXPIRES
    except (ValueError,TypeError,UnicodeError):return False


def snapshot():
    with LOCK:
        files=[dict(f,token=file_token(f['name'])) for f in STATE['files']]
        return dict(STATE,files=files,log=list(STATE['log']))


def publish(path):
    path=Path(path)
    if path.is_symlink() or path.resolve().parent!=FILES.resolve() or not path.is_file() or path.suffix not in ('.mp3','.flac','.m4a','.mp4'):return
    if len(path.name)>512 or any(ord(c)<32 for c in path.name) or '\\' in path.name:return
    size=path.stat().st_size
    with LOCK:
        if path.name in [f['name'] for f in STATE['files']]:return
        if 0<size<=MAX_FILE and len(STATE['files'])<MAX_FILES and sum(f['size'] for f in STATE['files'])+size<=MAX_TOTAL:
            STATE['files'].append({'name':path.name,'size':size})


def terminate():
    if PROC and PROC.poll() is None:
        try:os.killpg(PROC.pid,signal.SIGCONT);os.killpg(PROC.pid,signal.SIGTERM)
        except ProcessLookupError:return
        def force():
            if PROC.poll() is None:
                try:os.killpg(PROC.pid,signal.SIGKILL)
                except ProcessLookupError:pass
        threading.Timer(3,force).start()


def limit(message):
    global LIMIT_HIT
    with LOCK:
        if LIMIT_HIT:return
        LIMIT_HIT=True;STATE.update(state='partial' if STATE['files'] else 'error',message=message)
    terminate()


def handle_event(event):
    kind=event.get('type');message=str(event.get('message',''))[-1500:]
    with LOCK:
        if message:STATE['log']=(STATE['log']+[message])[-35:]
        if kind=='saved':publish(FILES/str(event.get('name','')))
        if LIMIT_HIT or STATE['state']=='cancelled':return
        if kind in ('progress','status') and STATE['state']!='paused':
            if kind=='status' or 'Found ' in message:STATE['message']=message
            elif 'Searching for song' in message:STATE['message']='Finding matching audio…'
            elif 'Downloading' in message or '[download]' in message:STATE['message']='Downloading the next song…'
            elif 'Embedding metadata' in message:STATE['message']='Finishing the song…'
            percent=event.get('percent')
            if isinstance(percent,(int,float)):STATE['percent']=percent
        if kind=='done':
            for path in FILES.iterdir():publish(path)
            state=event.get('state','error')
            if state=='complete' and not STATE['files']:state='error'
            STATE['state']=state
            if STATE['files']:STATE['message']=f"{len(STATE['files'])} file(s) ready."+(' Some items failed; see details.' if state=='partial' else '')
            elif 'sign' in message.lower() or 'AudioProviderError' in message:STATE['message']='This source is unavailable from the cloud. Try another selection or use the Mac app.'
            else:STATE['message']=message or 'No files were downloaded. See details.'


def child_limits(pid):
    resource.prlimit(pid,resource.RLIMIT_FSIZE,(MAX_FILE,MAX_FILE))
    resource.prlimit(pid,resource.RLIMIT_NOFILE,(256,256))


def download(config):
    global PROC
    try:
        native=dict(config,destination=str(FILES),data=str(BASE/'data'))
        PROC=subprocess.Popen([sys.executable,'-u',str(Path(__file__).with_name('runner_entry.py'))],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True,env=dict(os.environ,NODE_OPTIONS="--max-old-space-size=256"))
        child_limits(PROC.pid)
        PROC.stdin.write(json.dumps(native)+'\n');PROC.stdin.close()
        for line in iter(lambda:PROC.stdout.readline(8192),''):
            try:event=json.loads(line)
            except (ValueError,TypeError):
                with LOCK:STATE['log']=(STATE['log']+[line.strip()[-1000:]])[-35:]
                continue
            if isinstance(event,dict):handle_event(event)
        code=PROC.wait();PROC.stdout.close()
        with LOCK:
            if STATE['state'] in ('running','paused'):
                STATE.update(state='partial' if STATE['files'] else 'error',message='The source could not finish this download. Ready files remain available.')
    except Exception as exc:
        with LOCK:STATE.update(state='partial' if STATE['files'] else 'error',message='The download could not finish. Try another selection or use the Mac app.')
    finally:
        with LOCK:STATE['finished']=time.time()


def watchdog():
    while time.time()*1000<EXPIRES:
        with LOCK:active=STATE['state'] in ('running','paused')
        if active:
            sizes=[p.stat().st_size for p in FILES.iterdir() if p.is_file() and not p.is_symlink()]
            if any(s>MAX_FILE for s in sizes) or sum(sizes)>MAX_TOTAL:limit('The free cloud size limit was reached. Ready songs are kept; use the Mac app for larger downloads.')
            elif time.monotonic()-START>720:limit('The 12-minute processing limit was reached. Ready songs are kept; use a smaller selection or the Mac app.')
        time.sleep(1)
    terminate()
    for path in FILES.iterdir():
        if path.is_file():path.unlink(missing_ok=True)


def control(action):
    with LOCK:
        if action=='pause' and STATE['state']=='running' and PROC and PROC.poll() is None:
            os.killpg(PROC.pid,signal.SIGSTOP);STATE.update(state='paused',message='Paused. The session expiry still applies.')
        elif action=='resume' and STATE['state']=='paused' and PROC and PROC.poll() is None:
            os.killpg(PROC.pid,signal.SIGCONT);STATE.update(state='running',message='Resuming download…')
        elif action=='cancel':
            STATE.update(state='cancelled',message='Cancelled. Ready songs can still be saved until the session expires.');terminate()
        elif action not in ('pause','resume'):raise ValueError('Unknown action.')
    return snapshot()


class BoundedServer(ThreadingHTTPServer):
    daemon_threads=True
    slots=threading.BoundedSemaphore(8)
    def process_request(self,request,address):
        if not self.slots.acquire(False):request.close();return
        try:super().process_request(request,address)
        except Exception:self.slots.release();raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()


class Handler(BaseHTTPRequestHandler):
    def setup(self):super().setup();self.connection.settimeout(15)
    def log_message(self,*args):pass
    def cors(self):
        self.send_header('Access-Control-Allow-Origin',ORIGIN)
        self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type')
        self.send_header('Access-Control-Expose-Headers','Content-Length, Content-Disposition')
        self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Content-Type-Options','nosniff')
    def respond(self,code,data):
        body=json.dumps(data).encode();self.send_response(code);self.cors();self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def authorized(self):
        value=self.headers.get('Authorization','')
        return len(value)<256 and secrets.compare_digest(value,'Bearer '+KEY)
    def do_OPTIONS(self):
        if self.headers.get('Origin')!=ORIGIN:return self.respond(403,{'error':'Origin not allowed.'})
        self.send_response(204);self.cors();self.end_headers()
    def do_POST(self):
        if time.time()*1000>=EXPIRES:return self.respond(410,{'error':'Session expired.'})
        if self.headers.get('Origin')!=ORIGIN:return self.respond(403,{'error':'Origin not allowed.'})
        if not self.authorized():return self.respond(401,{'error':'Invalid session.'})
        if urlsplit(self.path).path!='/control':return self.respond(404,{'error':'Not found.'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<1024:raise ValueError('Invalid request.')
            return self.respond(200,control(json.loads(self.rfile.read(length))['action']))
        except (ValueError,KeyError,TypeError,ProcessLookupError):return self.respond(400,{'error':'Invalid control request.'})
    def do_GET(self):
        global TRANSFER
        if time.time()*1000>=EXPIRES:return self.respond(410,{'error':'Session expired.'})
        url=urlsplit(self.path);query=parse_qs(url.query)
        if url.path=='/status':
            if not self.authorized():return self.respond(401,{'error':'Invalid session.'})
            return self.respond(200,snapshot())
        if url.path!='/file':return self.respond(404,{'error':'Not found.'})
        name=query.get('name',[''])[0];token=query.get('token',[''])[0]
        if not valid_file_token(token,name):return self.respond(401,{'error':'Invalid file link.'})
        with LOCK:
            record=next((f for f in STATE['files'] if f['name']==name),None)
            if not record:return self.respond(404,{'error':'Not found.'})
            if TRANSFER+record['size']>MAX_TRANSFER:return self.respond(429,{'error':'This session has reached its download-transfer allowance.'})
            TRANSFER+=record['size']
        file=FILES/name
        if not file.is_file() or file.is_symlink() or file.resolve().parent!=FILES.resolve():return self.respond(404,{'error':'Not found.'})
        self.send_response(200);self.cors();self.send_header('Content-Type','application/octet-stream')
        self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(name));self.send_header('Content-Length',str(record['size']));self.end_headers()
        try:
            with file.open('rb') as source:
                while chunk:=source.read(65536):self.wfile.write(chunk)
        except (BrokenPipeError,ConnectionResetError,TimeoutError):pass


if __name__=='__main__':
    config=json.loads((BASE/'config.json').read_text())
    threading.Thread(target=download,args=(config,),daemon=True).start()
    threading.Thread(target=watchdog,daemon=True).start()
    server=BoundedServer(('0.0.0.0',int(os.environ.get('MEDIAFLOW_PORT','8000'))),Handler)
    (BASE/'server.ready').write_text('ready')
    server.serve_forever()
