"""Cloud-only CLI: no web server, no browser credentials, at most 20 tracks."""
import importlib
from pathlib import Path
import runpy
import sys
home=Path(sys.argv.pop(1));home.mkdir(parents=True,exist_ok=True)
Path.home=classmethod(lambda cls:home)
if sys.argv[1:2]!=['download']:raise ValueError('Only downloads are supported.')
module=importlib.import_module('spotdl.utils.search')
native_get_songs=module.get_simple_songs
def limited_query(*args,**kwargs):
    songs=native_get_songs(*args,**kwargs)
    if len(songs)>20:raise ValueError('The free cloud limit is 20 songs per download. Use a smaller playlist or the Mac app for the full collection.')
    return songs
module.get_simple_songs=limited_query
runpy.run_module('spotdl',run_name='__main__')
