# YouTube & Spotify Downloader

Native Mac app for saving permitted YouTube media and matching audio from Spotify metadata to your selected folder. Songs save one by one. No visitor access key, browser cookies or account password is required.

## Website downloads

Cloud downloads run on the Vercel Hobby plan and the free Upstash plan. They are limited to 20 songs, 64 MB per song, 256 MB total, and 20 minutes per session. Only one session can run at a time; the shared allowance is 10 sessions per 30 days and 3 sessions per connection per day. If a free quota is exhausted, new sessions are rejected until it resets. No paid plan, paid add-on, or automatic upgrade is configured.

Each finished song is offered separately or saved immediately to the folder you choose. Workers are temporary, private to one job, and stop after completion or expiry. The website has no visitor access-key field and never asks for account passwords or browser cookies. Vercel BotID Basic, exact website-origin checks and atomic Upstash limits protect job creation. Random short-lived worker and file tokens are generated internally for each session.

The website publishes only an explicit allowlist of static files into `public/`. Python source, packages, desktop build files and environment files are excluded from the static output. Security headers include a restrictive Content Security Policy, frame protection, no-referrer and content-type protection. Production JavaScript dependencies have been removed from the static page.

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

`vercel.json` selects `public/` as static output and the standalone `api/jobs.mjs` endpoint. Production requires server-only Vercel Sandbox, BotID, signing-secret and Upstash environment settings. No credentials are exposed to visitors or included in the website build.

Privacy, permitted use and support links are on `/privacy.html`. Do not post passwords, cookies or private signing keys in public issues.

## Release verification

The exact requested six-track Spotify album downloaded as six MP3 files, a track saved as FLAC through the native app, YouTube MP4 completed, and an Intel Spotify-to-M4A download succeeded under Rosetta. Output files passed full decoding. Both disk images passed read-only package and signature checks. All 55 packaged Python distributions passed the known-advisory audit. No developer signing or notarization credentials are embedded.

Download the [1.3.0 release](https://github.com/alaamari/Youtube-Playlist_Download/releases/tag/v1.3.0). Corresponding FFmpeg/LAME sources, a package inventory and checksums accompany the installers. An active paid Apple Developer Program membership is required before Developer ID signing and notarization can be completed. The original installed Mac app is unchanged.
