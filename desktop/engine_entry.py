"""Bundled engine entry point. No system Python or package install is needed."""
import json
import multiprocessing
import os
from pathlib import Path
import runpy
import signal
import sys


def main():
    multiprocessing.freeze_support()
    resources=Path(sys.executable).resolve().parents[1]
    os.environ['PATH']=str(resources/'bin')+os.pathsep+'/usr/bin:/bin'
    os.environ['PYTHONUNBUFFERED']='1'
    if sys.argv[1:2]==['--spotdl']:
        sys.argv.pop(1)
        home=Path(sys.argv.pop(1))
        home.mkdir(parents=True,exist_ok=True)
        Path.home=classmethod(lambda cls:home)
        if sys.argv[1:2] not in (['download'],['--version']):
            raise ValueError('This packaged engine supports downloads only.')
        runpy.run_module('spotdl',run_name='__main__')
        return 0
    if sys.argv[1:2]==['--yt-dlp']:
        sys.argv.pop(1)
        runpy.run_module('yt_dlp',run_name='__main__')
        return 0
    if sys.argv[1:2]==['--self-check']:
        import importlib.metadata
        import platform
        import shutil
        import subprocess
        result={'version':'1.3.0','python':platform.python_version(),'architecture':platform.machine(),'frozen':getattr(sys,'frozen',False),'spotdl':importlib.metadata.version('spotdl'),'yt-dlp':importlib.metadata.version('yt-dlp')}
        for name in ('ffmpeg','node'):
            path=shutil.which(name)
            if not path or not Path(path).is_relative_to(resources):
                raise RuntimeError('Bundled '+name+' is missing')
            result[name]=subprocess.check_output([path,'-version' if name=='ffmpeg' else '--version'],stderr=subprocess.STDOUT,text=True).splitlines()[0]
        print(json.dumps(result),flush=True)
        return 0
    import runner
    try:os.setsid()
    except OSError:pass
    signal.signal(signal.SIGTERM,runner.cancel)
    signal.signal(signal.SIGINT,runner.cancel)
    try:
        runner.main(json.loads(sys.stdin.readline()))
    except Exception as exc:
        runner.emit('done',state='cancelled' if runner.CANCELLED else 'error',message='Download cancelled.' if runner.CANCELLED else str(exc)[-1800:])
        return 0 if runner.CANCELLED else 1
    return 0


if __name__=='__main__':sys.exit(main())
