# YouTube & Spotify Downloader

Native Mac app for saving permitted YouTube media and matching audio from Spotify metadata to your selected folder. Songs save one by one. No visitor access key, browser cookies or account password is required.

## Public website security update

Cloud job creation is disabled. The public API returns a paused status for GET and rejects every POST without loading credentials or provisioning a worker. This prevents anonymous visitors from creating paid download workers while a zero-overage service has not been configured. Hosting and bandwidth still follow the account provider’s plan; this is not a billing guarantee.

The website publishes only an explicit allowlist of static files into `public/`. Python source, packages, desktop build files and environment files are excluded from the static output. Security headers include a restrictive Content Security Policy, frame protection, no-referrer and content-type protection. No cookie upload is accepted. Production JavaScript dependencies have been removed.

The old experimental cloud engine remains in repository history for reference. It is not deployed as a worker, and must not be re-enabled without durable atomic admission, bot checks, per-user and global quotas, scoped short-lived download credentials, resource caps and verified billing safeguards. An in-memory counter or a list-then-create check is insufficient.

## Mac app

The current public installer is version 1.3.0, an ad-hoc signed security rebuild with Python 3.13.17, FFmpeg 9.0.2 and the unused spotDL web server removed. It is not Apple-notarized. Build sources are in `desktop/`. The developer’s original installed app is separate and is not replaced by website deployment.

Spotify supplies track metadata; matching audio comes from public source providers. Spotify streams are not decrypted. Provider availability and match accuracy vary. Download only media you own or have explicit permission to download, and follow platform terms. Public availability is not permission.

## Build and verify the website

```sh
npm ci --ignore-scripts
npm test
npm run build
npm audit --omit=dev
```

`vercel.json` selects `public/` as static output and the standalone `api/jobs.mjs` endpoint. The active website requires no environment variables. Old cloud secrets are not read by this release.

Privacy, permitted use and support links are on `/privacy.html`. Do not post passwords, cookies or private signing keys in public issues.

## Release verification

The exact requested six-track Spotify album downloaded as six MP3 files, a track saved as FLAC through the native app, YouTube MP4 completed, and an Intel Spotify-to-M4A download succeeded under Rosetta. Output files passed full decoding. Both disk images passed read-only package and signature checks. All 55 packaged Python distributions passed the known-advisory audit. No developer signing or notarization credentials are embedded.

Download the [1.3.0 release](https://github.com/alaamari/Youtube-Playlist_Download/releases/tag/v1.3.0). Corresponding FFmpeg/LAME sources, a package inventory and checksums accompany the installers. An active paid Apple Developer Program membership is required before Developer ID signing and notarization can be completed. The original installed Mac app is unchanged.
