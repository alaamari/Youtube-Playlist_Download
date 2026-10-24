"""MediaFlow local download engine. Standard-library HTTP API; bind to loopback."""
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote
import uuid
import zipfile

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get('MEDIAFLOW_DATA', str(ROOT / '.mediaflow'))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
# Keep third-party caches beside the app, rather than modifying the user's home.
import pathlib
pathlib.Path.home = classmethod(lambda cls: DATA)
os.environ['XDG_CACHE_HOME'] = str(DATA / 'cache')
TOKEN = secrets.token_urlsafe(32)
JOBS = {}
LOCK = threading.Lock()
SLOTS = threading.BoundedSemaphore(2)
ALLOWED_ORIGINS = {'http://127.0.0.1:3000', 'http://localhost:3000',
                   'https://youtube-playlist-download.vercel.app',
                   'https://youtube-playlist-download-alaa12.vercel.app'}
DEFAULT_DEST = str(Path(os.path.expanduser('~/Downloads')) / 'MediaFlow')


def validate(payload):
    url = payload.get('url', '').strip()
    parts = urlsplit(url)
    host = (parts.hostname or '').lower()
    if parts.scheme != 'https' or parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError('Paste a valid HTTPS YouTube or Spotify link.')
    if host == 'open.spotify.com':
        if not re.fullmatch(r'/(?:intl-[a-z]{2}/)?(?:playlist|album|track)/[A-Za-z0-9]{22}/?', parts.path):
            raise ValueError('Use a Spotify playlist, album, or track link.')
        provider = 'spotify'
    elif host in ('youtube.com', 'www.youtube.com', 'music.youtube.com', 'youtu.be'):
        if not parts.path or parts.path == '/':
            raise ValueError('Paste a YouTube video or playlist link.')
        provider = 'youtube'
    else:
        raise ValueError('Only youtube.com, youtu.be and open.spotify.com links are supported.')
    fmt = payload.get('format', 'mp3')
    if fmt not in ('mp3', 'mp4', 'flac', 'm4a') or (provider == 'spotify' and fmt == 'mp4'):
        raise ValueError('Choose an audio format for Spotify.')
    dest = Path(payload.get('destination') or DEFAULT_DEST).expanduser()
    if not dest.is_absolute():
        raise ValueError('Choose an absolute destination folder path.')
    return url, provider, fmt, dest.resolve(), bool(payload.get('playlist', True))


def command(url, provider, fmt, folder, playlist):
    if provider == 'spotify':
        return [sys.executable, '-m', 'spotdl', 'download', url, '--format', fmt,
                '--output', str(folder / '{list-position} - {artists} - {title}.{output-ext}'),
                '--threads', '2', '--print-errors', '--no-cache']
    cmd = [sys.executable, '-m', 'yt_dlp', '--newline', '--no-colors', '--ignore-config',
           '--yes-playlist' if playlist else '--no-playlist', '--max-downloads', '500',
           '--socket-timeout', '30', '--retries', '3', '--restrict-filenames',
           '-o', str(folder / '%(playlist_index&{} - |)s%(title).180B [%(id)s].%(ext)s')]
    if fmt == 'mp4':
        cmd += ['-f', 'bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best', '--merge-output-format', 'mp4']
    else:
        cmd += ['-x', '--audio-format', fmt, '--audio-quality', '0', '--embed-metadata']
    return cmd + ['--', url]


def dependencies():
    import importlib.util
    return {name: bool(importlib.util.find_spec(module)) for name, module in
            [('youtube', 'yt_dlp'), ('spotify', 'spotdl')]} | {'ffmpeg': bool(shutil.which('ffmpeg'))}


def execute(job, cmd):
    try:
        with SLOTS:
            if job['state'] == 'cancelled':
                return
            job.update(state='running', message='Connecting and reading playlist…')
            # Run module in a wrapper so spotDL caches stay in MEDIAFLOW_DATA.
            if cmd[1:3] == ['-m', 'spotdl']:
                wrapper = "import pathlib,runpy,sys; pathlib.Path.home=classmethod(lambda cls:pathlib.Path(sys.argv.pop(1))); runpy.run_module('spotdl',run_name='__main__')"
                cmd = [sys.executable, '-u', '-c', wrapper, str(DATA)] + cmd[3:]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, start_new_session=True, bufsize=1)
            job['_process'] = proc
            if job['state'] == 'cancelled':
                os.killpg(proc.pid, signal.SIGTERM)
            for line in proc.stdout:
                line = re.sub(r'\x1b\[[0-9;]*[mGKHF]', '', line).strip()
                if line:
                    job['message'] = line[-500:]
                    job['log'] = (job['log'] + [line[-500:]])[-40:]
            code = proc.wait()
            proc.stdout.close()
            if job['state'] == 'cancelled':
                return
            files = sorted(p for p in job['_folder'].iterdir() if p.is_file() and p.suffix in ('.mp3', '.mp4', '.m4a', '.flac'))
            job['files'] = [p.name for p in files]
            if not files:
                raise RuntimeError('No media files were produced. ' + ' '.join(job['log'][-4:]))
            if code != 0:
                job.update(state='partial', message=f'{len(files)} files saved; some items failed. Check details below.')
            else:
                job.update(state='complete', message=f'{len(files)} files saved to {job["destination"]}')
            archive = DATA / f'{job["id"]}.zip'
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as zf:
                for p in files:
                    zf.write(p, p.name)
            job['archiveReady'] = True
    except Exception as exc:
        if job['state'] != 'cancelled':
            job.update(state='error', message=str(exc)[-2000:])
    finally:
        job.pop('_process', None)
        job['finished'] = time.time()


def public(job):
    return {k: v for k, v in job.items() if not k.startswith('_')}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def origin_ok(self):
        if (self.headers.get('Host', '').split(':')[0]) not in ('localhost', '127.0.0.1'):
            return False
        origin = self.headers.get('Origin')
        return not origin or origin in ALLOWED_ORIGINS

    def send_headers(self, code, content='application/json'):
        self.send_response(code)
        self.send_header('Content-Type', content)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if self.headers.get('Origin') in ALLOWED_ORIGINS:
            self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
            self.send_header('Vary', 'Origin')
        self.send_header('Access-Control-Allow-Private-Network', 'true')

    def respond(self, code, value):
        self.send_headers(code)
        self.end_headers()
        self.wfile.write(json.dumps(value).encode())

    def do_OPTIONS(self):
        if not self.origin_ok():
            return self.respond(403, {'error': 'Origin not allowed.'})
        self.send_headers(204)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.end_headers()

    def authorized(self):
        return self.origin_ok() and secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + TOKEN)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ('/', '/index.html', '/style.css', '/app.js'):
            if not self.origin_ok():
                return self.respond(403, {'error': 'Origin not allowed.'})
            file = ROOT / ('desktop.html' if path in ('/', '/index.html') else path[1:])
            content = file.read_bytes()
            if path in ('/', '/index.html'):
                content = content.replace(b'<!--LOCAL_CONFIG-->', ('<script>window.MEDIAFLOW_LOCAL=' + json.dumps({'token': TOKEN}) + '</script>').encode())
            self.send_headers(200, 'text/html; charset=utf-8' if file.suffix == '.html' else ('text/css' if file.suffix == '.css' else 'text/javascript'))
            self.end_headers()
            self.wfile.write(content)
            return
        if not self.authorized():
            return self.respond(401, {'error': 'Connect your download engine with its connection key.'})
        if path == '/api/health':
            return self.respond(200, {'status': 'ready', 'dependencies': dependencies(), 'defaultDestination': DEFAULT_DEST})
        match = re.fullmatch(r'/api/jobs/([a-f0-9]{32})(/archive)?', path)
        if match and match[1] in JOBS:
            job = JOBS[match[1]]
            if match[2]:
                if not job.get('archiveReady'):
                    return self.respond(409, {'error': 'Archive is not ready.'})
                archive = DATA / f'{job["id"]}.zip'
                self.send_headers(200, 'application/zip')
                self.send_header('Content-Disposition', 'attachment; filename="MediaFlow-playlist.zip"')
                self.send_header('Content-Length', str(archive.stat().st_size))
                self.end_headers()
                with archive.open('rb') as source:
                    shutil.copyfileobj(source, self.wfile)
                return
            return self.respond(200, public(job))
        self.respond(404, {'error': 'Not found.'})

    def do_POST(self):
        if not self.authorized():
            return self.respond(401, {'error': 'Connection key required.'})
        path = urlsplit(self.path).path
        if path == '/api/folder':
            if sys.platform != 'darwin':
                return self.respond(400, {'error': 'Enter your destination folder path manually on this system.'})
            result = subprocess.run(['osascript', '-e', 'POSIX path of (choose folder with prompt "Choose your MediaFlow download folder")'], capture_output=True, text=True, timeout=120)
            return self.respond(200, {'destination': result.stdout.strip() if result.returncode == 0 else None})
        if path == '/api/jobs':
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 8192:
                    raise ValueError('Invalid request size.')
                url, provider, fmt, dest, playlist = validate(json.loads(self.rfile.read(length)))
                deps = dependencies()
                if not deps[provider] or not deps['ffmpeg']:
                    raise ValueError('Install the engine dependencies first. See the setup instructions.')
                with LOCK:
                    if sum(j['state'] in ('queued', 'running') for j in JOBS.values()) >= 4:
                        return self.respond(429, {'error': 'Four jobs are already active. Wait for one to finish.'})
                    job_id = uuid.uuid4().hex
                    # Dedicated subfolder avoids overwrites and accidental inclusion of other files.
                    folder = dest / ('MediaFlow-' + job_id[:8])
                    folder.mkdir(parents=True, exist_ok=False)
                    job = dict(id=job_id, state='queued', message='Waiting to start…', files=[], log=[],
                               destination=str(folder), provider=provider, archiveReady=False, _folder=folder)
                    JOBS[job_id] = job
                threading.Thread(target=execute, args=(job, command(url, provider, fmt, folder, playlist)), daemon=True).start()
                self.respond(202, public(job))
            except (ValueError, OSError, TypeError, AttributeError) as exc:
                self.respond(400, {'error': str(exc)})
            return
        match = re.fullmatch(r'/api/jobs/([a-f0-9]{32})/cancel', path)
        if match and match[1] in JOBS:
            length = int(self.headers.get('Content-Length', '0'))
            if length > 8192:
                return self.respond(400, {'error': 'Invalid request size.'})
            self.rfile.read(length)
            job = JOBS[match[1]]
            if job['state'] in ('queued', 'running'):
                job.update(state='cancelled', message='Cancelled. Files already saved remain in your folder.')
                proc = job.get('_process')
                if proc and proc.poll() is None:
                    try:
                        os.killpg(proc.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
            return self.respond(200, public(job))
        self.respond(404, {'error': 'Not found.'})


def run_server():
    port = int(os.environ.get('PORT', '3000'))
    ALLOWED_ORIGINS.update({f'http://localhost:{port}', f'http://127.0.0.1:{port}'})
    print(f'Open http://127.0.0.1:{port}\nWebsite connection key: {TOKEN}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()


if __name__ == '__main__':
    run_server()
