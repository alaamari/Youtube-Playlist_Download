"""Build-time patch: omit spotDL's unused web server from the desktop-only engine."""
from pathlib import Path
import importlib.util
import shutil

def prepare(target):
    source=Path(next(iter(importlib.util.find_spec('spotdl').submodule_search_locations)))
    package=Path(target)/'spotdl'
    if package.exists():shutil.rmtree(package)
    shutil.copytree(source,package,ignore=shutil.ignore_patterns('__pycache__'))
    entry=package/'console/entry_point.py'
    text=entry.read_text()
    expected='from spotdl.console.web import web\n'
    if expected not in text:raise RuntimeError('Review upstream spotDL before applying the desktop-only patch.')
    text=text.replace(expected,'')
    begin=text.index('    # If the application is frozen start web ui')
    end=text.index('    # Check if save file',begin)
    text=text[:begin]+'    if arguments.operation != "download":\n        raise ValueError("This desktop engine supports downloads only.")\n\n'+text[end:]
    entry.write_text(text)
    shutil.rmtree(package/'web')
    for relative in ('console/web.py','utils/web.py'):(package/relative).unlink()
    return str(package.parent)
