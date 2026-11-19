"""Assemble the Windows app, its runtime tools, notices, and release ZIP."""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import sysconfig
import urllib.request
import zipfile

VERSION = "1.4.0"
NODE_VERSION = "22.23.4"
FFMPEG_ARCHIVE = "ffmpeg-n9.0.2-57-gd838f9f9ae-win64-lgpl-shared-9.0.zip"
FFMPEG_URL = f"https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/download/autobuild-2026-11-12-15-40/{FFMPEG_ARCHIVE}"


def download(url, path):
    request = urllib.request.Request(url, headers={"User-Agent": "MediaFlow-Windows-Packager/1.4.0"})
    with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as target:
        shutil.copyfileobj(response, target)


def copy_package_data(name, relative, target):
    spec = importlib.util.find_spec(name)
    if not spec or not spec.submodule_search_locations:
        raise RuntimeError(f"Missing packaged dependency: {name}")
    source = Path(next(iter(spec.submodule_search_locations))) / relative
    if source.exists():
        shutil.copytree(source, target / name / relative, dirs_exist_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-dist", type=Path, required=True)
    parser.add_argument("--ui-dist", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    out = args.output.resolve()
    work = out / "work"
    package = out / f"MediaFlow-Windows-{VERSION}"
    if package.exists():
        shutil.rmtree(package)
    if work.exists():
        shutil.rmtree(work)
    package.mkdir(parents=True)
    work.mkdir(parents=True)
    engine_source = args.engine_dist.resolve() / "mediaflow-engine"
    if not (engine_source / "mediaflow-engine.exe").is_file():
        raise RuntimeError(f"PyInstaller engine output not found: {engine_source}")
    shutil.copytree(engine_source, package / "engine")
    copy_package_data("pykakasi", "data", package / "engine" / "_internal")
    copy_package_data("ytmusicapi", "locales", package / "engine" / "_internal")

    ui = args.ui_dist.resolve() / "MediaFlow.exe"
    if not ui.is_file():
        raise RuntimeError(f"Windows app window not found: {ui}")
    shutil.copy2(ui, package / "MediaFlow.exe")
    binaries = package / "bin"
    binaries.mkdir()
    licenses = package / "Licenses"
    licenses.mkdir()

    node_archive_name = f"node-v{NODE_VERSION}-win-x64.zip"
    node_archive = work / node_archive_name
    node_base = f"https://nodejs.org/download/release/v{NODE_VERSION}/"
    download(node_base + node_archive_name, node_archive)
    checksums = work / "SHASUMS256.txt"
    download(node_base + "SHASUMS256.txt", checksums)
    expected = next(line.split()[0] for line in checksums.read_text().splitlines() if line.split()[-1] == node_archive_name)
    if hashlib.sha256(node_archive.read_bytes()).hexdigest() != expected:
        raise RuntimeError("Node.js archive checksum mismatch")
    with zipfile.ZipFile(node_archive) as archive:
        node_member = next(name for name in archive.namelist() if name.endswith("/node.exe"))
        node_root = node_member.rsplit("/", 1)[0]
        (binaries / "node.exe").write_bytes(archive.read(node_member))
        license_member = node_root + "/LICENSE"
        (licenses / "Node-LICENSE.txt").write_bytes(archive.read(license_member))

    ffmpeg_archive = work / FFMPEG_ARCHIVE
    download(FFMPEG_URL, ffmpeg_archive)
    ffmpeg_root = work / "ffmpeg"
    ffmpeg_root.mkdir()
    with zipfile.ZipFile(ffmpeg_archive) as archive:
        archive.extractall(ffmpeg_root)
    ffmpeg_exe = next(ffmpeg_root.rglob("ffmpeg.exe"), None)
    if not ffmpeg_exe:
        raise RuntimeError("The FFmpeg release did not contain ffmpeg.exe")
    ffmpeg_bin = ffmpeg_exe.parent
    shutil.copy2(ffmpeg_exe, binaries / "ffmpeg.exe")
    for dll in ffmpeg_bin.glob("*.dll"):
        shutil.copy2(dll, binaries / dll.name)
    if not list(binaries.glob("av*.dll")):
        raise RuntimeError("The FFmpeg shared runtime DLLs are missing")
    for file in ffmpeg_root.rglob("*"):
        if file.is_file() and any(word in file.name.lower() for word in ("license", "copying")):
            shutil.copy2(file, licenses / ("FFmpeg-" + file.name))

    for distribution in importlib.metadata.distributions():
        for item in distribution.files or []:
            name = str(item)
            if ".dist-info/" in name and any(word in name.lower() for word in ("license", "copying", "notice")):
                source = Path(distribution.locate_file(item))
                if source.is_file():
                    target = licenses / distribution.metadata["Name"] / Path(name).name
                    target.parent.mkdir(exist_ok=True)
                    shutil.copy2(source, target)
    python_license = next((path for path in (
        Path(sysconfig.get_path("stdlib")) / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE",
    ) if path.is_file()), None)
    if python_license:
        shutil.copy2(python_license, licenses / "Python-LICENSE.txt")
    else:
        # The official Windows Python package does not consistently install
        # its license in the stdlib directory, so fetch the matching CPython tag.
        license_url = f"https://raw.githubusercontent.com/python/cpython/v{platform.python_version()}/LICENSE"
        download(license_url, licenses / "Python-LICENSE.txt")
        if (licenses / "Python-LICENSE.txt").stat().st_size < 1000:
            raise RuntimeError("Could not retrieve the matching Python license")
    (licenses / "Third-party-notices.txt").write_text(
        "MediaFlow for Windows includes Python (PSF), spotDL (MIT; modified for desktop use to remove its unused web server), yt-dlp (Unlicense), Node.js and their dependencies. "
        "FFmpeg 9.0.2 shared LGPL build is from FFmpeg-Builds/BtbN; it is dynamically linked and includes its required DLLs. No GPL-only or nonfree FFmpeg build is used. "
        "FFmpeg source and build project: https://ffmpeg.org/download.html and https://github.com/FFmpeg-Builds/FFmpeg-Builds. See the included notices and each upstream license. "
        "Application source: https://github.com/alaamari/Youtube-Playlist_Download. This is an unsigned community build.\n",
        encoding="utf-8",
    )
    (package / "README.txt").write_text(
        "MediaFlow for Windows 1.4.0\n\n"
        "1. Extract this entire folder to a location you choose.\n"
        "2. Open MediaFlow.exe. Keep the engine and bin folders beside it.\n"
        "3. Paste a YouTube or Spotify link, choose the destination folder, and click Download.\n\n"
        "Songs are saved to your computer one by one. The website does not process your downloads. Spotify provides track information; matching audio is found on public sources, not from Spotify's protected stream.\n"
        "Requires Windows 10 or later, 64-bit. The app is unsigned, so Windows may show a SmartScreen warning for an unknown publisher. Check the checksum on the release page and review the source before running it.\n"
        "Only download media you own or have permission to save, and follow the source platform's terms.\n"
        "Third-party licenses and notices are in the Licenses folder.\n",
        encoding="utf-8",
    )

    engine = package / "engine" / "mediaflow-engine.exe"
    env = dict(os.environ)
    env["PATH"] = str(binaries) + os.pathsep + env.get("PATH", "")
    subprocess.run([str(engine), "--self-check"], check=True, capture_output=True, text=True, env=env)
    subprocess.run([str(engine), "--spotdl", str(work / "spotdl-check"), "--version"], check=True, capture_output=True, text=True, env=env)
    subprocess.run([str(engine), "--yt-dlp", "--version"], check=True, capture_output=True, text=True, env=env)
    info = {
        "version": VERSION,
        "platform": "Windows x64",
        "python": platform.python_version(),
        "node": NODE_VERSION,
        "ffmpeg": FFMPEG_ARCHIVE,
        "packages": {name: importlib.metadata.version(name) for name in ("spotdl", "yt-dlp", "pyinstaller")},
    }
    (package / "build-info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    zip_path = out / f"MediaFlow-Windows-{VERSION}.zip"
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", root_dir=out, base_dir=package.name)
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (out / f"MediaFlow-Windows-{VERSION}.zip.sha256").write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    print(json.dumps({"zip": str(zip_path), "sha256": digest, "package": str(package)}, indent=2))


if __name__ == "__main__":
    main()
