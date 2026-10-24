"""Build a self-contained native Mac app and drag-to-Applications disk image."""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import ssl
import subprocess
import sys
import sysconfig
import tarfile
import urllib.request
import certifi

VERSION='1.3.0'
NODE_VERSION='22.23.4'
ROOT=Path(__file__).resolve().parent
TLS=ssl.create_default_context(cafile=certifi.where())


def run(*args,**kwargs):
    print('Running',args[0],flush=True)
    subprocess.run([str(x) for x in args],check=True,**kwargs)


def download(url,path):
    if not path.exists():
        with urllib.request.urlopen(url,timeout=90,context=TLS) as response,path.open('wb') as target:
            shutil.copyfileobj(response,target)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--ffmpeg',required=True,type=Path,help='Patched FFmpeg built with desktop/build_ffmpeg.sh')
    parser.add_argument('--signing-identity',help='Installed Developer ID Application identity; omit for a test build')
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--skip-freeze',action='store_true',help='Reuse the engine during packaging-only repairs')
    parser.add_argument('--skip-dmg',action='store_true',help='Create ZIP only when disk images are unavailable')
    args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    arch=platform.machine()
    if arch not in ('arm64','x86_64'):raise RuntimeError('Build on an Apple Silicon or Intel Mac.')
    label='AppleSilicon' if arch=='arm64' else 'Intel'
    work=out/('build-'+arch);work.mkdir(exist_ok=True)
    stage=out/('stage-'+arch)
    if stage.exists():shutil.rmtree(stage)
    stage.mkdir()
    app=stage/'YouTube & Spotify Downloader.app'
    contents=app/'Contents';resources=contents/'Resources';binaries=resources/'bin'
    binaries.mkdir(parents=True);(contents/'MacOS').mkdir()
    build_env=dict(os.environ,PYINSTALLER_CONFIG_DIR=str(work/'pyinstaller-cache'),MEDIAFLOW_VENDOR_DIR=str(work/'vendor'))
    if not args.skip_freeze:
        run(sys.executable,'-m','PyInstaller','--noconfirm','--clean','--distpath',work/'dist','--workpath',work/'pyinstaller',ROOT/'engine.spec',env=build_env)
    shutil.copytree(work/'dist/mediaflow-engine',resources/'engine',symlinks=True)
    # These resources are loaded by path at runtime, including on the first query.
    for package,directory in (('pykakasi','data'),('ytmusicapi','locales')):
        package_root=Path(next(iter(importlib.util.find_spec(package).submodule_search_locations)))
        shutil.copytree(package_root/directory,resources/'engine/_internal'/package/directory,dirs_exist_ok=True)
    run('swiftc','-swift-version','5','-O','-module-cache-path',work/'swift-cache','-target',arch+'-apple-macosx12.0','-framework','AppKit',ROOT/'Main.swift','-o',contents/'MacOS/Downloader')
    shutil.copy2(ROOT/'icon.icns',resources/'icon.icns')
    ffmpeg=args.ffmpeg.resolve()
    if not ffmpeg.is_file():raise RuntimeError('Provide the verified patched FFmpeg executable.')
    shutil.copy2(ffmpeg,binaries/'ffmpeg');(binaries/'ffmpeg').chmod(0o755)
    node_arch='arm64' if arch=='arm64' else 'x64'
    node_name=f'node-v{NODE_VERSION}-darwin-{node_arch}'
    archive_name=node_name+'.tar.gz'
    node_archive=work/archive_name
    node_base=f'https://nodejs.org/download/release/v{NODE_VERSION}/'
    download(node_base+archive_name,node_archive)
    with urllib.request.urlopen(node_base+'SHASUMS256.txt',timeout=30,context=TLS) as response:
        checksums=response.read().decode()
    expected=next(line.split()[0] for line in checksums.splitlines() if line.split()[-1]==archive_name)
    if hashlib.sha256(node_archive.read_bytes()).hexdigest()!=expected:raise RuntimeError('Node checksum mismatch')
    licenses=resources/'Licenses';licenses.mkdir()
    with tarfile.open(node_archive) as archive:
        with archive.extractfile(node_name+'/bin/node') as source,(binaries/'node').open('wb') as target:shutil.copyfileobj(source,target)
        with archive.extractfile(node_name+'/LICENSE') as source:(licenses/'Node-LICENSE.txt').write_bytes(source.read())
    (binaries/'node').chmod(0o755)
    for distribution in importlib.metadata.distributions():
        for item in distribution.files or []:
            name=str(item)
            if ('.dist-info/' in name and any(x in name.lower() for x in ('license','copying','notice'))):
                source=Path(distribution.locate_file(item))
                if source.is_file():
                    target=licenses/distribution.metadata['Name']/Path(name).name
                    target.parent.mkdir(exist_ok=True)
                    shutil.copy2(source,target)
    for filename in ('FFmpeg-LGPL-2.1.txt','LAME-COPYING.txt','ffmpeg-source-manifest.json','build_ffmpeg.sh'):
        source=ROOT/filename
        if not source.exists():raise RuntimeError('Missing source/license record: '+filename)
        shutil.copy2(source,licenses/filename)
    (licenses/'Third-party-notices.txt').write_text('Includes Python (PSF), spotDL (MIT, patched to omit its web server), yt-dlp (Unlicense), Node.js and dependencies. FFmpeg 9.0.2 and LAME 3.100 are built from the corresponding source archives and build script supplied with this release, under their included LGPL terms. No GPL-only FFmpeg components are enabled. Source archives and this application source: https://github.com/alaamari/Youtube-Playlist_Download/releases . Modified FFmpeg binaries may replace Contents/Resources/bin/ffmpeg; re-sign the local bundle after replacing a component.\n')
    python_license=Path(sysconfig.get_path('stdlib'))/'LICENSE.txt'
    if not python_license.exists():raise RuntimeError('The Python license notice is missing from the build runtime.')
    shutil.copy2(python_license,licenses/'Python-LICENSE.txt')
    info={'CFBundleExecutable':'Downloader','CFBundleIdentifier':'com.alaamari.mediaflow','CFBundleName':'YouTube & Spotify Downloader','CFBundleDisplayName':'YouTube & Spotify Downloader','CFBundlePackageType':'APPL','CFBundleShortVersionString':VERSION,'CFBundleVersion':'130','CFBundleIconFile':'icon.icns','LSMinimumSystemVersion':'12.0','NSHighResolutionCapable':True}
    (contents/'Info.plist').write_bytes(plistlib.dumps(info))
    versions={name:importlib.metadata.version(name) for name in ('spotdl','yt-dlp','pyinstaller')}
    (resources/'build-info.json').write_text(json.dumps({'version':VERSION,'architecture':arch,'node':NODE_VERSION,'python':platform.python_version(),'ffmpeg':subprocess.check_output([str(ffmpeg),'-version'],text=True).splitlines()[0],'packages':versions},indent=2))
    shutil.copy2(ROOT/'Install.txt',stage/'Install.txt')
    os.symlink('/Applications',stage/'Applications')
    from sign_release import sign_app
    sign_app(app,args.signing_identity)
    run('codesign','--verify','--deep','--strict',app)
    run(resources/'engine/mediaflow-engine','--self-check',env={'PATH':'/usr/bin:/bin','HOME':str(Path.home()),'LANG':'en_US.UTF-8'})
    run(resources/'engine/mediaflow-engine','--spotdl',work/'self-test','--version')
    run(resources/'engine/mediaflow-engine','--yt-dlp','--version')
    artifact=f'YouTube-Spotify-Downloader-{VERSION}-{label}'
    dmg=out/(artifact+'.dmg');dmg.unlink(missing_ok=True)
    if not args.skip_dmg:
        run('hdiutil','create','-volname','YouTube & Spotify Downloader','-srcfolder',stage,'-format','UDZO','-ov','-o',dmg)
    zip_path=out/(artifact+'.zip');zip_path.unlink(missing_ok=True)
    run('ditto','-c','-k','--sequesterRsrc','--keepParent',app,zip_path)
    for artifact_path in (dmg,zip_path):
        if not artifact_path.exists():continue
        digest=hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        artifact_path.with_suffix(artifact_path.suffix+'.sha256').write_text(digest+'  '+artifact_path.name+'\n')
    print(json.dumps({'app':str(app),'dmg':str(dmg),'zip':str(zip_path),'architecture':arch}),flush=True)


if __name__=='__main__':main()
