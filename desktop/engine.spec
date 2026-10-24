from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata
import sys
import os
from pathlib import Path
import importlib.util

root=Path(SPECPATH)
sys.path.insert(0,str(root))
from prepare_vendor import prepare
vendor=prepare(Path(os.environ['MEDIAFLOW_VENDOR_DIR']))
sys.path.insert(0,vendor)
datas=[];binaries=[];hiddenimports=['runner']
spotdl_path=Path(vendor)/'spotdl'
datas+=collect_data_files('spotdl')
for path in spotdl_path.rglob('*.py'):
    parts=path.relative_to(spotdl_path).with_suffix('').parts
    if parts[-1]=='__init__':parts=parts[:-1]
    hiddenimports.append('.'.join(('spotdl',)+parts))
for package in ('yt_dlp','yt_dlp_ejs','Cryptodome','pykakasi','unidecode','spotipyfree','spotapi','ytmusicapi'):
    package_data,package_binaries,package_imports=collect_all(package)
    datas+=package_data;binaries+=package_binaries;hiddenimports+=package_imports
from importlib.metadata import distribution
from packaging.requirements import Requirement
blocked={'fastapi','starlette','anyio','uvicorn','python-multipart'}
seen=set();pending=['spotdl','yt-dlp']
while pending:
    name=pending.pop().lower().replace('_','-')
    if name in seen or name in blocked:continue
    seen.add(name)
    dist=distribution(name)
    datas+=copy_metadata(name,recursive=False)
    for item in dist.requires or []:
        req=Requirement(item)
        if req.marker is None or req.marker.evaluate({'extra':''}):pending.append(req.name)
a=Analysis([str(root/'engine_entry.py')],pathex=[vendor,str(root)],binaries=binaries,datas=datas,hiddenimports=hiddenimports,excludes=['tkinter','PySide6','PyQt5','PyQt6','numpy','scipy','matplotlib','IPython','fastapi','starlette','anyio','uvicorn','spotdl.web','spotdl.console.web','spotdl.utils.web','Cryptodome.SelfTest','pip_audit','pytest'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='mediaflow-engine',console=True,strip=False,upx=False,target_arch=None,codesign_identity=None,entitlements_file=None)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='mediaflow-engine')
