# Downloadable Mac app

The native window starts before the bundled download engine. Python, spotDL, yt-dlp, FFmpeg and Node are included; no Homebrew, Terminal setup, or access key is required.

Settings and caches live in `~/Library/Application Support/YouTube & Spotify Downloader`. Songs are saved directly to the selected folder, one by one. Spotify uses matching Bandcamp or YouTube audio, not Spotify stream extraction.

Build on macOS with Python 3.12 and Xcode command-line tools:

    python3 -m venv .build-venv
    .build-venv/bin/pip install -r desktop/requirements-build.txt
    .build-venv/bin/python desktop/build.py --output /absolute/path/to/release

Build separately on Apple Silicon and Intel so that compiled dependencies match the target processor. Builds are ad-hoc signed and are not Apple-notarized. A Developer ID certificate and Apple notarization are needed for distribution without the macOS first-open warning. Never remove quarantine or disable Gatekeeper in an installer.
