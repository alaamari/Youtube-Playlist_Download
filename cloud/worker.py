"""HTTP adapter around the verified Mac app engine; one isolated job per worker."""
import json
import hashlib
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import parse_qs,urlsplit,quote
import zipfile

BASE=Path(os.environ.get('MEDIAFLOW_JOB_DIR','/vercel/job'))
BASE.mkdir(parents=True,exist_ok=True)
STATE={'state':'running','message':'Starting download…','files':[],'log':[],'archiveReady':False,'engineVersion':'1.1.1','engineSha256':hashlib.sha256(Path(__file__).with_name('mac_runner.py').read_bytes()).hexdigest()}
KEY=os.environ['JOB_KEY']
ORIGIN=os.environ['APP_ORIGIN']
PROC=None
COOKIE_FILE=BASE/'youtube-cookies.txt'
LOCK=threading.RLock()


def snapshot():
    with LOCK:return dict(STATE,files=list(STATE['files']),log=list(STATE['log']))


def publish(file):
    file=Path(file).resolve()
    if file.parent!=(BASE/'files').resolve() or not file.is_file() or file.suffix not in ('.mp3','.mp4','.flac','.m4a'):return
    with LOCK:
        if file.name not in [f['name'] for f in STATE['files']]:STATE['files']=STATE['files']+[{'name':file.name,'size':file.stat().st_size}]


def handle_event(event):
    kind=event.get('type')
    message=event.get('message','')
    with LOCK:
        if message:
            STATE['log']=(STATE['log']+[message[-1800:]])[-40:]
            if any(text in message.lower() for text in ('sign in to confirm','requested sign-in','cookies are no longer valid','login required')):STATE['errorCode']='YOUTUBE_AUTH_REQUIRED'
            elif 'No results found for song:' in message:STATE['errorCode']='MATCH_NOT_FOUND'
            elif 'AudioProviderError' in message:STATE.setdefault('errorCode','SOURCE_UNAVAILABLE')
            if STATE['state'] not in ('paused','cancelled'):
                if kind=='status':STATE['message']=message
                elif kind=='progress':
                    if 'Processing query:' in message:STATE['message']='Reading your Spotify link…'
                    elif 'Searching for song' in message:STATE['message']='Finding matching audio…'
                    elif 'returned no usable results' in message:STATE['message']='Trying another audio match…'
                    elif 'Getting audio meta' in message:STATE['message']='Preparing audio…'
                    elif 'Embedding metadata' in message:STATE['message']='Finishing the song…'
                    elif 'Downloading' in message or '[download]' in message:STATE['message']='Downloading…'
                    if isinstance(event.get('percent'),(int,float)):STATE['percent']=event['percent']
        if kind=='saved':publish(BASE/'files'/event.get('name',''))
        if kind=='done' and STATE['state']!='cancelled':
            state=event.get('state','error')
            STATE['state']='finishing' if state in ('complete','partial') else state
            if state in ('complete','partial'):
                for file in (BASE/'files').iterdir():publish(file)
                STATE['resultState']=state
                STATE['message']=f"{len(STATE['files'])} song(s) ready."+(' Some items failed; see details.' if state=='partial' else '')
            elif state=='cancelled':STATE['message']='Download cancelled. Songs already saved remain in your folder.'
            elif STATE.get('errorCode')=='YOUTUBE_AUTH_REQUIRED':STATE['message']='YouTube requires sign-in from this cloud connection. Open YouTube sign-in help and retry with your session.'
            elif STATE.get('errorCode')=='SOURCE_UNAVAILABLE':STATE['message']='The audio source refused this cloud download. See details or open YouTube sign-in help.'
            elif STATE.get('errorCode')=='MATCH_NOT_FOUND':STATE['message']='No matching audio was found for this Spotify selection. See details for the affected songs.'
            else:STATE['message']=message or 'No files were downloaded. See details.'


def package():
    if not STATE['files']:return
    with zipfile.ZipFile(BASE/'playlist.zip','w',compression=zipfile.ZIP_STORED) as archive:
        for file in list(STATE['files']):archive.write(BASE/'files'/file['name'],file['name'])
    with LOCK:STATE['archiveReady']=True


def download(config):
    global PROC
    (BASE/'files').mkdir(exist_ok=True)
    native_config=dict(config,destination=str(BASE/'files'),data=str(BASE/'data'))
    env=os.environ.copy()
    if COOKIE_FILE.exists():env['MEDIAFLOW_COOKIE_FILE']=str(COOKIE_FILE)
    try:
        PROC=subprocess.Popen([sys.executable,'-u',str(Path(__file__).with_name('runner_entry.py'))],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True,bufsize=1,env=env)
        PROC.stdin.write(json.dumps(native_config)+'\n');PROC.stdin.close()
        if STATE['state']=='cancelled':os.killpg(PROC.pid,signal.SIGTERM)
        for line in PROC.stdout:
            try:event=json.loads(line)
            except json.JSONDecodeError:
                with LOCK:STATE['log']=(STATE['log']+[line.strip()[-500:]])[-40:]
                continue
            if isinstance(event,dict):handle_event(event)
        code=PROC.wait();PROC.stdout.close()
        with LOCK:
            if STATE['state'] not in ('error','cancelled','finishing'):
                STATE.update(state='error',message='The download engine stopped. See details.')
        package()
        with LOCK:
            if STATE['state']=='finishing':STATE['state']=STATE.pop('resultState','complete')
    except Exception as exc:
        with LOCK:
            if STATE['state']!='cancelled':STATE.update(state='partial' if STATE['files'] else 'error',message=str(exc)[-1600:])
    finally:
        COOKIE_FILE.unlink(missing_ok=True)
        with LOCK:STATE['finished']=time.time()


def control(action):
    with LOCK:
        if action=='pause' and STATE['state']=='running' and PROC and PROC.poll() is None:
            os.killpg(PROC.pid,signal.SIGSTOP);STATE.update(state='paused',message='Paused.')
        elif action=='resume' and STATE['state']=='paused' and PROC and PROC.poll() is None:
            os.killpg(PROC.pid,signal.SIGCONT);STATE.update(state='running',message='Resuming download…')
        elif action=='cancel' and STATE['state'] in ('running','paused'):
            STATE.update(state='cancelled',message='Download cancelled. Songs already saved remain in your folder.')
            if PROC and PROC.poll() is None:
                try:os.killpg(PROC.pid,signal.SIGCONT);os.killpg(PROC.pid,signal.SIGTERM)
                except ProcessLookupError:pass
        elif action not in ('pause','resume','cancel'):raise ValueError('Unknown action.')
    return snapshot()


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def cors(self):
        self.send_header('Access-Control-Allow-Origin',ORIGIN)
        self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers','Content-Type')
        self.send_header('Access-Control-Expose-Headers','Content-Length, Content-Disposition')
        self.send_header('Cache-Control','no-store')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Content-Type-Options','nosniff')
    def respond(self,code,data):
        self.send_response(code);self.cors();self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(data).encode())
    def authorized(self):return secrets.compare_digest(parse_qs(urlsplit(self.path).query).get('key',[''])[0],KEY)
    def do_OPTIONS(self):self.send_response(204);self.cors();self.end_headers()
    def do_POST(self):
        if not self.authorized():return self.respond(401,{'error':'Invalid download session.'})
        if urlsplit(self.path).path!='/control':return self.respond(404,{'error':'Not found.'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<1024:raise ValueError('Invalid request.')
            return self.respond(200,control(json.loads(self.rfile.read(length))['action']))
        except (ValueError,KeyError,ProcessLookupError) as exc:return self.respond(400,{'error':str(exc)})
    def do_GET(self):
        url=urlsplit(self.path);query=parse_qs(url.query)
        if not self.authorized():return self.respond(401,{'error':'Invalid download session.'})
        if url.path=='/status':return self.respond(200,snapshot())
        if url.path=='/archive':
            if not STATE['archiveReady']:return self.respond(409,{'error':'ZIP is not ready.'})
            file=BASE/'playlist.zip'
        elif url.path=='/file':
            name=query.get('name',[''])[0]
            if name not in [f['name'] for f in snapshot()['files']]:return self.respond(404,{'error':'Not found.'})
            file=BASE/'files'/name
        else:return self.respond(404,{'error':'Not found.'})
        self.send_response(200);self.cors();self.send_header('Content-Type','application/octet-stream')
        self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(file.name));self.send_header('Content-Length',str(file.stat().st_size));self.end_headers()
        with file.open('rb') as source:shutil.copyfileobj(source,self.wfile)


if __name__=='__main__':
    config=json.loads((BASE/'config.json').read_text())
    threading.Thread(target=download,args=(config,),daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0',8000),Handler).serve_forever()
