"""One isolated cloud job; all files expire with the worker session."""
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
import zipfile

BASE=Path(os.environ.get('MEDIAFLOW_JOB_DIR','/vercel/job'))
BASE.mkdir(parents=True,exist_ok=True)
STATE={'state':'running','message':'Reading your playlist…','files':[],'log':[],'archiveReady':False}
KEY=os.environ['JOB_KEY']
ORIGIN=os.environ['APP_ORIGIN']
PROC=None
COOKIE_FILE=BASE/'youtube-cookies.txt'

def publish(file):
    file=Path(file).resolve()
    folder=(BASE/'files').resolve()
    if file.parent!=folder or not file.is_file() or file.suffix not in ('.mp3','.mp4','.flac','.m4a'):
        return
    if file.name not in [item['name'] for item in STATE['files']]:
        STATE['files']=STATE['files']+[{'name':file.name,'size':file.stat().st_size}]

def run(cmd,on_line=None):
    global PROC
    failed=False
    PROC=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True,bufsize=1)
    for line in PROC.stdout:
        text=re.sub(r'\x1b\[[0-9;]*[mGKHF]','',line).strip()
        if text.startswith('MEDIAFLOW_READY:'):
            publish(text.removeprefix('MEDIAFLOW_READY:'))
            continue
        if text:
            if any(marker in text.lower() for marker in ('sign in to confirm', 'cookies are no longer valid', 'login required')):
                STATE['errorCode']='YOUTUBE_AUTH_REQUIRED'
            if 'AudioProviderError' in text:STATE.setdefault('errorCode','SOURCE_UNAVAILABLE')
            if any(marker in text for marker in ('AudioProviderError','ERROR:','Failed to download')):failed=True
            STATE['message']=text[-500:];STATE['log']=(STATE['log']+[text[-500:]])[-30:]
        if on_line:on_line(text)
    code=PROC.wait();PROC.stdout.close()
    return code==0 and not failed

def download(config):
    folder=BASE/'files';folder.mkdir(exist_ok=True)
    success=True
    session=['--cookie-file',str(COOKIE_FILE)] if COOKIE_FILE.exists() else []
    try:
        if config['provider']=='spotify':
            listing=BASE/'tracks.spotdl'
            if not run([sys.executable,'-m','spotdl','save',config['url'],'--save-file',str(listing),'--no-cache','--max-retries','2','--simple-tui']):
                raise RuntimeError('Could not read the Spotify playlist. See download details.')
            tracks=json.loads(listing.read_text())
            STATE['total']=len(tracks)
            for index,track in enumerate(tracks,1):
                STATE['message']=f'Downloading song {index} of {len(tracks)}…'
                before={p.name for p in folder.iterdir()}
                ok=run([sys.executable,'-m','spotdl','download',track['url'],'--format',config['format'],'--threads','1','--no-cache','--max-retries','2','--print-errors','--simple-tui','--yt-dlp-args=--js-runtimes node',*session,'--output',str(folder/(f'{index:03} - '+'{artists} - {title}.{output-ext}'))])
                success=success and ok
                if not ok and STATE.get('errorCode')=='YOUTUBE_AUTH_REQUIRED':break
                if not ok and STATE.get('errorCode')=='SOURCE_UNAVAILABLE' and not STATE['files']:break
                if ok:
                    for file in sorted(folder.iterdir()):
                        if file.name not in before:publish(file)
        else:
            cmd=[sys.executable,'-m','yt_dlp','--ignore-config','--js-runtimes','node','--newline','--no-colors','--restrict-filenames','--socket-timeout','20','--retries','2','--yes-playlist' if config['playlist'] else '--no-playlist','--max-downloads','100','--max-filesize','300M','--no-simulate','--print','after_move:MEDIAFLOW_READY:%(filepath)s','-o',str(folder/'%(playlist_index&{} - |)s%(title).150B [%(id)s].%(ext)s')]
            if config['format']=='mp4':cmd+=['-f','bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best','--merge-output-format','mp4']
            else:cmd+=['-x','--audio-format',config['format'],'--audio-quality','0','--embed-metadata']
            if COOKIE_FILE.exists():cmd+=['--cookies',str(COOKIE_FILE)]
            success=run(cmd+['--',config['url']])
        files=[folder/item['name'] for item in STATE['files']]
        if not files:raise RuntimeError('No files were downloaded. The audio provider may require sign-in from this cloud server. See download details.')
        STATE.update(message='Preparing optional ZIP copy…')
        with zipfile.ZipFile(BASE/'playlist.zip','w',compression=zipfile.ZIP_STORED) as archive:
            for file in files:archive.write(file,file.name)
        STATE.update(state='complete' if success else 'partial',message=f'{len(files)} songs finished.' if success else f'{len(files)} songs finished; some items failed. See details.',archiveReady=True)
    except Exception as exc:
        if STATE.get('errorCode')=='YOUTUBE_AUTH_REQUIRED':
            message='YouTube requires a valid signed-in session. Choose your YouTube cookies.txt file below and retry. If a session was already supplied, it may have expired or YouTube may still be refusing this cloud connection.'
        else:message=str(exc)[-1600:]
        STATE.update(state='partial' if STATE['files'] else 'error',message=message)
    finally:
        COOKIE_FILE.unlink(missing_ok=True)
    STATE['finished']=time.time()

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_OPTIONS(self):
        self.send_response(204);self.cors();self.end_headers()
    def cors(self):
        self.send_header('Access-Control-Allow-Origin',ORIGIN)
        self.send_header('Access-Control-Allow-Methods','GET, OPTIONS')
        self.send_header('Access-Control-Expose-Headers','Content-Length, Content-Disposition')
        self.send_header('Cache-Control','no-store')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Content-Type-Options','nosniff')
    def do_GET(self):
        url=urlsplit(self.path);query=parse_qs(url.query)
        if not secrets.compare_digest(query.get('key',[''])[0],KEY):
            self.send_response(401);self.end_headers();return
        if url.path=='/status':
            self.send_response(200);self.cors();self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(STATE).encode());return
        if url.path=='/archive':
            if not STATE.get('archiveReady'):
                self.send_response(409);self.end_headers();return
            file=BASE/'playlist.zip'
        elif url.path=='/file':
            name=query.get('name',[''])[0]
            if name not in [f['name'] for f in STATE['files']]:
                self.send_response(404);self.end_headers();return
            file=BASE/'files'/name
        else:self.send_response(404);self.end_headers();return
        self.send_response(200);self.cors();self.send_header('Content-Type','application/octet-stream')
        self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+__import__('urllib.parse',fromlist=['quote']).quote(file.name))
        self.send_header('Content-Length',str(file.stat().st_size));self.end_headers()
        with file.open('rb') as source:shutil.copyfileobj(source,self.wfile)

if __name__=='__main__':
    config=json.loads((BASE/'config.json').read_text())
    threading.Thread(target=download,args=(config,),daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0',8000),Handler).serve_forever()
