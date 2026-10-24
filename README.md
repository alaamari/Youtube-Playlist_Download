# MediaFlow

Download YouTube videos and Spotify playlists to a folder on your Mac.

The main interface and API run on Vercel. Each download runs in an isolated Vercel cloud worker with Python, spotDL, yt-dlp, and FFmpeg. Your Mac does not need a local engine for the hosted website. Choose a destination folder in Chrome/Edge, then save individual files when conversion finishes; other browsers can save a ZIP.

Cloud sessions last **45 minutes**, including conversion and saving. Save before the displayed expiry time. Files are temporary and are deleted when the worker stops or expires. One worker runs at a time. Starting another download stops the previous worker, so save first. Cloud compute and transfer count toward your Vercel usage. Very long playlists may exceed the session limit.

Spotify metadata is used to find matching audio on Bandcamp first, then YouTube through spotDL. Files are not extracted from Spotify streams. Matches and availability can vary. Private/restricted playlists may need authentication or may be unavailable under Spotify's API restrictions. Download only material you have permission to save.

## Current verification status

The Spotify album `https://open.spotify.com/album/3eZWAHSjyU30lfC89F2jnQ` (Noussaïr — 7ess-75) downloaded all six full-length MP3 tracks from public Bandcamp artist uploads in a Vercel cloud worker without cookies or a visitor access key. All six files passed full FFmpeg decoding; their titles, artist, album tags, and durations matched Spotify metadata. YouTube still rejects this cloud connection with “Sign in to confirm you’re not a bot,” so selections available only on YouTube may still fail. This test establishes this album and the alternate source path, not availability of every Spotify release.

## Website engine update

The cloud adapter now launches `cloud/mac_runner.py`, an unchanged copy of the tested Mac app 1.1.1 engine. `cloud/engine-version.json` records its SHA-256. `runner_entry.py` adds Bandcamp-first matching and album track numbering, plus optional session injection, without altering that engine. The cloud HTTP wrapper translates its JSON progress/saved/done events, exposes finished songs immediately, and pauses/resumes/cancels the isolated child process group. Cancel retains finished files until the browser starts another job or the cloud session expires.

The website starts with local HTML/CSS/JavaScript and a compact interface matching the Mac workflow. No visitor access key or local engine is needed. Browser folder permissions still apply. The same engine can be rejected by YouTube when it runs on a cloud connection; desktop success does not establish cloud success. Live verification is recorded in the task output report.

## Use the cloud website

Open the Vercel site. No access key is required. Paste a Spotify playlist/album/track or a YouTube link. Choose your audio/video format, choose a folder if supported by your browser, and click **Download**. If you chose a folder first in Chrome or Edge, each finished song saves immediately while remaining songs continue downloading. Spotify tracks run one at a time. Completed files are exposed only after conversion and metadata writing finish. Each song is saved once per browser session. Otherwise use the individual **Save song** links as they appear, or choose **Save ready songs to folder**. A ZIP remains an optional copy after all tracks finish. The website writes only to folders you explicitly authorize.

Spotify downloads use matching audio sources, not Spotify stream extraction. For best results use public, accessible playlists. All processing occurs in the cloud. No Spotify login is collected. If YouTube requests sign-in, use **YouTube sign-in session** to select a Netscape cookies.txt export from your own signed-in browser. The API validates the format, filters out every non-YouTube cookie, and sends the remaining session only to that isolated download worker in a private file. Cookie contents are excluded from job tickets, status responses, browser storage, logs, media downloads, and ZIPs. The cookie file is removed after processing; cancellation/expiry destroys the non-persistent worker. Session exports grant account access and should be kept private. Supplying a session may still fail if YouTube rejects the cloud connection.

## Setup (optional local Mac app)

Requires macOS, Python 3.12+, and FFmpeg. Install FFmpeg with Homebrew if needed:

```sh
brew install ffmpeg
```

Download this repository with GitHub's **Code → Download ZIP**, unzip it, and open Terminal in that folder. Then:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
chmod +x 'Start MediaFlow.command'
./'Start MediaFlow.command'
```

Open **http://127.0.0.1:3000**. The local page connects automatically. Paste a Spotify playlist, album, or track link, click **Choose…**, select your destination folder, and click **Download to folder**. Spotify offers MP3, FLAC, or M4A; YouTube also offers MP4. Converting to FLAC does not restore quality absent from the source.

To use the Vercel website on the same Mac, copy the connection key printed in the engine's Terminal window into **Connect your Mac download engine**. Allow local-network access if your browser requests it. The key is held only for the browser session and changes whenever the engine restarts. If your browser blocks the hosted page's local connection, use the local page above.

Cloud browser saves go directly into the folder you select, matching the Mac app. The optional legacy local HTTP engine creates a per-job subfolder. A ZIP copy becomes available after completion. Partial results are marked separately. Cancel stops the worker but retains files already saved. The native folder chooser appears on the Mac running the engine.

## Troubleshooting

- **Engine disconnected:** start the engine, use the current connection key, and allow local-network access. Use the local page if the browser blocks access from HTTPS to localhost.
- **Missing dependencies:** install the requirements in the same Python environment used to start the engine; ensure FFmpeg is in PATH.
- **Spotify errors:** update spotDL and review Download details. Spotify can restrict playlist access; a valid link does not guarantee access. No success is reported when no files are produced.
- **YouTube sign-in / bot / unavailable errors:** availability depends on YouTube, region, and current downloader support. Update yt-dlp. Do not bypass access controls.
- **Permission denied:** choose a writable folder and allow macOS folder access when prompted.

## Hosting

GitHub repository: `alaamari/Youtube-Playlist_Download`. Vercel project: `youtube-playlist-download` in team `alaa12`. Framework **Other**, output directory `.`, no build command. Node API `/api/jobs` creates and stops isolated workers using Vercel OIDC, without a personal Vercel token.

Required server-only Vercel settings:

- `MEDIAFLOW_SIGNING_SECRET`: server-only secret used to sign job cancellation tickets; visitors never enter or see it.
- `MEDIAFLOW_SNAPSHOT_ID`: prepared worker image snapshot with `/vercel/mediaflow-venv/bin/python`, spotDL, yt-dlp, and FFmpeg.

The website does not require an access key. Signed job tickets protect cancellation; each worker has an automatic random download token. Files are served directly from the worker, avoiding Vercel Function response-size limits. Source URLs and formats are validated before use; no shell interpolation handles user input.

The image snapshot contains dependencies, not user downloads. Rebuild it when updating downloader versions. Keep it available for future jobs. Per-job workers are non-persistent. The `cloud/worker.py` source is uploaded with each job, so application updates do not require rebuilding dependencies.

## Checks

```sh
python3 -m unittest discover -s tests -v
node --check app.js
```

Tests validate input, playlist command construction, job isolation, real HTTP authentication, origin restrictions, cancellation, and archive contents. External provider availability needs a real playlist test and is not guaranteed by the automated tests.

Local caches and ZIP copies live in `.mediaflow/`, which is excluded from Git. You can remove this directory after stopping the engine to reclaim space; your selected destination folders are unaffected.
