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

BASE=Path('/vercel/job')
BASE.mkdir(parents=True,exist_ok=True)
STATE={'state':'running','message':'Reading your playlist…','files':[],'log':[],'archiveReady':False}
KEY=os.environ['JOB_KEY']
ORIGIN=os.environ['APP_ORIGIN']
PROC=None

def download(config):
    global PROC
    folder=BASE/'files';folder.mkdir(exist_ok=True)
    if config['provider']=='spotify':
        cmd=[sys.executable,'-m','spotdl','download',config['url'],'--format',config['format'],'--threads','2','--no-cache','--max-retries','2','--print-errors','--simple-tui','--output',str(folder/'{list-position} - {artists} - {title}.{output-ext}')]
    else:
        cmd=[sys.executable,'-m','yt_dlp','--ignore-config','--newline','--no-colors','--restrict-filenames','--socket-timeout','20','--retries','2','--yes-playlist' if config['playlist'] else '--no-playlist','--max-downloads','100','--max-filesize','300M','-o',str(folder/'%(playlist_index&{} - |)s%(title).150B [%(id)s].%(ext)s')]
        if config['format']=='mp4':cmd+=['-f','bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best','--merge-output-format','mp4']
        else:cmd+=['-x','--audio-format',config['format'],'--audio-quality','0','--embed-metadata']
        cmd+=['--',config['url']]
    try:
        PROC=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True,bufsize=1)
        for line in PROC.stdout:
            text=re.sub(r'\x1b\[[0-9;]*[mGKHF]','',line).strip()
            if text:
                STATE['message']=text[-500:];STATE['log']=(STATE['log']+[text[-500:]])[-30:]
        code=PROC.wait();PROC.stdout.close()
        files=sorted(p for p in folder.iterdir() if p.is_file() and p.suffix in ('.mp3','.mp4','.flac','.m4a'))
        if not files:raise RuntimeError('No files were downloaded. '+ ' '.join(STATE['log'][-4:]))
        STATE.update(message='Packaging your files…')
        with zipfile.ZipFile(BASE/'playlist.zip','w',compression=zipfile.ZIP_STORED) as archive:
            for file in files:archive.write(file,file.name)
        STATE.update(state='complete' if code==0 else 'partial',message=f'{len(files)} files ready to save.' if code==0 else f'{len(files)} files ready; some items failed. See details.',files=[{'name':p.name,'size':p.stat().st_size} for p in files],archiveReady=True)
    except Exception as exc:
        STATE.update(state='error',message=str(exc)[-1600:])
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
        if not STATE.get('archiveReady'):
            self.send_response(409);self.end_headers();return
        if url.path=='/archive':file=BASE/'playlist.zip'
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
