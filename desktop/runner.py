"""Local download worker. Launched only after the native window is open."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from urllib.parse import urlsplit

PROC = None
CANCELLED = False


def emit(kind, **values):
    print(json.dumps(dict(type=kind, **values)), flush=True)


def validate(config):
    url = str(config.get('url', '')).strip()
    parsed = urlsplit(url)
    host = (parsed.hostname or '').lower()
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError('Paste a valid HTTPS YouTube or Spotify link.')
    if host == 'open.spotify.com':
        if not re.fullmatch(r'/(?:intl-[a-z]{2}/)?(?:playlist|album|track)/[A-Za-z0-9]{22}/?', parsed.path):
            raise ValueError('Use a Spotify playlist, album, or track link.')
        provider = 'spotify'
    elif host in ('youtube.com', 'www.youtube.com', 'music.youtube.com', 'youtu.be'):
        if parsed.path in ('', '/'):
            raise ValueError('Paste a YouTube video or playlist link.')
        provider = 'youtube'
    else:
        raise ValueError('Only YouTube and Spotify links are supported.')
    fmt = config.get('format', 'mp3')
    if fmt not in ('mp3', 'm4a', 'flac', 'mp4') or (provider == 'spotify' and fmt == 'mp4'):
        raise ValueError('Choose an audio format for Spotify.')
    dest = Path(config['destination']).expanduser()
    if not dest.is_absolute():
        raise ValueError('Choose an absolute destination folder.')
    return url, provider, fmt, dest, bool(config.get('playlist', True))


def spotify_command(url, fmt, destination, data):
    # Redirect spotDL's cache only; never read or modify browser cookies.
    wrapper = "import pathlib,runpy,sys; cache_home=pathlib.Path(sys.argv.pop(1)); pathlib.Path.home=classmethod(lambda cls:cache_home); runpy.run_module('spotdl',run_name='__main__')"
    prefix = '' if '/track/' in url else '{track-number} - ' if '/album/' in url else '{list-position} - '
    launcher = [sys.executable, '--spotdl', str(data / 'tool-home')] if getattr(sys,'frozen',False) else [sys.executable, '-u', '-c', wrapper, str(data / 'tool-home')]
    return launcher + [
            'download', url, '--format', fmt, '--threads', '1', '--no-cache',
            '--max-retries', '2', '--print-errors', '--simple-tui',
            '--audio','bandcamp','youtube-music',
            '--yt-dlp-args=--js-runtimes node', '--output',
            str(destination / (prefix + '{artists} - {title} [{track-id}].{output-ext}'))]


def youtube_command(url, fmt, destination, playlist):
    launcher = [sys.executable, '--yt-dlp'] if getattr(sys,'frozen',False) else [sys.executable, '-u', '-m', 'yt_dlp']
    cmd = launcher + ['--ignore-config', '--js-runtimes', 'node',
           '--newline', '--no-colors', '--socket-timeout', '20', '--retries', '2',
           '--yes-playlist' if playlist else '--no-playlist', '--no-simulate',
           '--print', 'after_move:MEDIAFLOW_READY:%(filepath)s', '-o',
           str(destination / '%(playlist_index&{} - |)s%(title).160B [%(id)s].%(ext)s')]
    if fmt == 'mp4':
        cmd += ['-f', 'bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best', '--merge-output-format', 'mp4']
    else:
        cmd += ['-x', '--audio-format', fmt, '--audio-quality', '0', '--embed-metadata']
    return cmd + ['--', url]


def main(config):
    global PROC
    import importlib.util
    import shutil
    url, provider, fmt, destination, playlist = validate(config)
    module = 'spotdl' if provider == 'spotify' else 'yt_dlp'
    if importlib.util.find_spec(module) is None:
        raise RuntimeError(f'{module} is missing from the download engine. Reinstall the app dependencies.')
    if not shutil.which('ffmpeg'):
        raise RuntimeError('FFmpeg was not found. Install it before downloading.')
    destination.mkdir(parents=True, exist_ok=True)
    data = Path(config['data'])
    (data / 'tool-home').mkdir(parents=True, exist_ok=True)
    cmd = spotify_command(url, fmt, destination, data) if provider == 'spotify' else youtube_command(url, fmt, destination, playlist)
    emit('status', message='Reading Spotify playlist…' if provider == 'spotify' else 'Connecting to YouTube…')
    existing = {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in destination.iterdir() if p.is_file()}
    log = []
    failed = False
    saved = set()
    PROC = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in PROC.stdout:
        text = re.sub(r'\x1b\[[0-9;]*[mGKHF]', '', line).strip()
        if not text:
            continue
        if text.startswith('MEDIAFLOW_READY:'):
            path = Path(text.removeprefix('MEDIAFLOW_READY:'))
            if path.is_file() and path.parent.resolve() == destination.resolve():
                saved.add(str(path))
                emit('saved', name=path.name, count=len(saved))
            continue
        log = (log + [text])[-20:]
        failed = failed or any(value in text for value in ('AudioProviderError', 'FFmpegError', 'MetadataError', 'ERROR:', 'Failed to download'))
        percent = re.search(r'\[download\]\s+(\d+(?:\.\d+)?)%', text)
        emit('progress', message=text, percent=float(percent[1]) if percent else None)
        if provider == 'spotify' and ('Done' in text or re.search(r'\d+/\d+ complete', text)):
            for path in destination.iterdir():
                if path.is_file() and path.suffix in ('.mp3', '.flac', '.m4a') and str(path) not in saved:
                    info = path.stat()
                    if existing.get(path.name) != (info.st_size, info.st_mtime_ns):
                        saved.add(str(path))
                        emit('saved', name=path.name, count=len(saved))
    code = PROC.wait()
    PROC.stdout.close()
    if CANCELLED:
        emit('done', state='cancelled', message='Download cancelled. Files already saved remain in your folder.')
        return
    for path in destination.iterdir():
        if path.is_file() and path.suffix in ('.mp3', '.flac', '.m4a', '.mp4'):
            info = path.stat()
            if existing.get(path.name) != (info.st_size, info.st_mtime_ns):
                saved.add(str(path))
    if not saved:
        detail = ' '.join(log[-4:])
        if 'Sign in to confirm' in detail:
            detail = 'YouTube requested sign-in for this media. Try an accessible public track or playlist.'
        raise RuntimeError(detail or 'No files were downloaded. Check the link and try again.')
    state = 'partial' if code != 0 or failed else 'complete'
    emit('done', state=state, count=len(saved), destination=str(destination),
         message=f'{len(saved)} file(s) saved to your folder.' + (' Some tracks failed; see details.' if state == 'partial' else ''))


def cancel(_signum, _frame):
    global CANCELLED
    CANCELLED = True
    if PROC and PROC.poll() is None:
        try:
            PROC.terminate()
        except ProcessLookupError:
            pass


if __name__ == '__main__':
    try:
        os.setsid()
    except OSError:
        pass
    signal.signal(signal.SIGTERM, cancel)
    signal.signal(signal.SIGINT, cancel)
    try:
        config = json.loads(sys.stdin.readline())
        main(config)
    except Exception as exc:
        if CANCELLED:
            emit('done', state='cancelled', message='Download cancelled. Files already saved remain in your folder.')
        else:
            emit('done', state='error', message=str(exc)[-1800:])
            sys.exit(1)
