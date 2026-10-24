from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata
from pathlib import Path
import importlib.util

root=Path(SPECPATH)
datas=[];binaries=[];hiddenimports=['runner']
spotdl_path=Path(next(iter(importlib.util.find_spec('spotdl').submodule_search_locations)))
datas+=collect_data_files('spotdl')
for path in spotdl_path.rglob('*.py'):
    parts=path.relative_to(spotdl_path).with_suffix('').parts
    if parts[-1]=='__init__':parts=parts[:-1]
    hiddenimports.append('.'.join(('spotdl',)+parts))
for package in ('yt_dlp','yt_dlp_ejs','Cryptodome','pykakasi','unidecode','spotipyfree','spotapi','ytmusicapi'):
    package_data,package_binaries,package_imports=collect_all(package)
    datas+=package_data;binaries+=package_binaries;hiddenimports+=package_imports
for package in ('spotdl','yt-dlp'):
    datas+=copy_metadata(package,recursive=True)
a=Analysis([str(root/'engine_entry.py')],pathex=[str(root)],binaries=binaries,datas=datas,hiddenimports=hiddenimports,excludes=['tkinter','PySide6','PyQt5','PyQt6','numpy','scipy','matplotlib','IPython'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='mediaflow-engine',console=True,strip=False,upx=False,target_arch=None,codesign_identity=None,entitlements_file=None)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='mediaflow-engine')
