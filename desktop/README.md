# Native Mac build 1.3.0

Build with CPython 3.13.17, Xcode command-line tools and the pinned packages in `requirements-build.txt`. Use separate Apple Silicon and Intel environments. Never embed developer credentials or browser cookies.

The native AppKit window opens before loading the packaged download engine. Downloads save one by one to the selected folder. Spotify provides metadata; audio is matched on Bandcamp first, then YouTube. The desktop-only spotDL patch in `prepare_vendor.py` removes its unused web server. FastAPI, Starlette, AnyIO and Uvicorn are deliberately excluded from the frozen app. They remain upstream spotDL installation requirements in the build environment, but are not runtime requirements for the patched desktop entry point.

## FFmpeg and corresponding sources

Use the official source archives named in `ffmpeg-source-manifest.json` and verify their SHA-256 values. Unpack them into an isolated workspace as `sources/ffmpeg-9.0.2` and `sources/lame-3.100`. Then run:

```sh
MEDIAFLOW_FFMPEG_BUILD_ROOT=/absolute/build/workspace /bin/sh desktop/build_ffmpeg.sh arm64
```

Use `x86_64` under an Intel execution environment for Intel. This build enables LGPL components only, uses macOS system TLS, and links LAME statically. Distribute both matching source archives, this build script, the manifest and LGPL texts beside the installers. The app calls FFmpeg as a separate executable; users may rebuild and replace it. Re-sign their modified local app afterward.

## Build the app

```sh
python3.13 -m venv .build-venv
.build-venv/bin/python -m pip install -r desktop/requirements-build.txt
.build-venv/bin/python desktop/build.py --output /absolute/release --ffmpeg /absolute/build/workspace/ffmpeg-arm64/bin/ffmpeg
```

The default is an ad-hoc signed test build, not Apple-notarized. An active paid Apple Developer Program membership and an installed Developer ID Application identity are required for public Developer ID signing. A free developer account is insufficient. With an installed identity, pass `--signing-identity 'Developer ID Application: …'`; signing proceeds from nested Mach-O files to the outer app, with hardened runtime. Only Node receives the JIT entitlement it needs.

Notarization must use credentials entered directly into Apple tools and stored in Keychain, never in source, command history or chat. Submit the signed app archive using `xcrun notarytool`, wait for Accepted, staple the app, then create/sign the distribution DMG and notarize/staple that DMG. Verify `codesign --verify --deep --strict`, `xcrun stapler validate`, and `spctl --assess --type execute` before describing a build as notarized. Never remove quarantine or disable Gatekeeper in an installer.

Settings and caches live under `~/Library/Application Support/YouTube & Spotify Downloader`. No server listens for download requests on the Mac. The original developer-installed app is not overwritten by this build.
