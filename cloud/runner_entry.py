"""Run the unchanged Mac download engine in an isolated web job."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys


def prepare_engine(cookie_file=None):
    spec=importlib.util.spec_from_file_location('mediaflow_native_engine',Path(__file__).with_name('mac_runner.py'))
    engine=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    native_spotify=engine.spotify_command
    def spotify_with_sources(url,fmt,destination,data):
        cmd=native_spotify(url,fmt,destination,data)
        index=cmd.index('--output')
        # Prefer public artist uploads before YouTube, which may reject cloud IPs.
        cmd=cmd[:index]+['--audio','bandcamp','youtube-music']+cmd[index:]
        if '/album/' in url:
            cmd[-1]=cmd[-1].replace('{list-position}','{track-number}')
        return cmd
    engine.spotify_command=spotify_with_sources
    if cookie_file and Path(cookie_file).is_file():
        spotify=engine.spotify_command
        youtube=engine.youtube_command
        def spotify_with_session(*args):
            cmd=spotify(*args)
            index=cmd.index('--output')
            return cmd[:index]+['--cookie-file',str(cookie_file)]+cmd[index:]
        def youtube_with_session(*args):
            cmd=youtube(*args)
            index=cmd.index('--')
            return cmd[:index]+['--cookies',str(cookie_file)]+cmd[index:]
        engine.spotify_command=spotify_with_session
        engine.youtube_command=youtube_with_session
    return engine


def main():
    engine=prepare_engine(os.environ.get('MEDIAFLOW_COOKIE_FILE'))
    try:os.setsid()
    except OSError:pass
    signal.signal(signal.SIGTERM,engine.cancel)
    signal.signal(signal.SIGINT,engine.cancel)
    try:
        engine.main(json.loads(sys.stdin.readline()))
    except Exception as exc:
        if engine.CANCELLED:engine.emit('done',state='cancelled',message='Download cancelled.')
        else:
            engine.emit('done',state='error',message=str(exc)[-1800:])
            return 1
    return 0


if __name__=='__main__':sys.exit(main())
