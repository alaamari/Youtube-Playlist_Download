"""Use the native engine with stricter cloud resource limits."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys


def prepare_engine():
    spec=importlib.util.spec_from_file_location('mediaflow_native',Path(__file__).with_name('desktop_runner.py'))
    engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
    native_spotify=engine.spotify_command;native_youtube=engine.youtube_command
    def spotify(*args):
        cmd=native_spotify(*args)
        index=cmd.index('download')
        cmd=[sys.executable,'-u',str(Path(__file__).with_name('spotdl_cli.py')),str(args[3]/'tool-home')]+cmd[index:]
        return [part+' --max-filesize 64M --socket-timeout 15 --retries 1' if part.startswith('--yt-dlp-args=') else part for part in cmd]
    def youtube(*args):
        cmd=native_youtube(*args);index=cmd.index('--')
        return cmd[:index]+['--playlist-end','20','--max-downloads','20','--max-filesize','64M','--match-filters','duration <= 900 & !is_live']+cmd[index:]
    engine.spotify_command=spotify;engine.youtube_command=youtube
    return engine


def main():
    engine=prepare_engine()
    signal.signal(signal.SIGTERM,engine.cancel);signal.signal(signal.SIGINT,engine.cancel)
    try:engine.main(json.loads(sys.stdin.readline()))
    except Exception as exc:
        engine.emit('done',state='cancelled' if engine.CANCELLED else 'error',message='Download cancelled.' if engine.CANCELLED else str(exc)[-1400:])
        return 0 if engine.CANCELLED else 1
    return 0

if __name__=='__main__':sys.exit(main())
