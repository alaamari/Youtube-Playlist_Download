# MediaFlow for Mac

This repository contains the standalone Mac downloader and its static download website. The website only serves product information, privacy details and links to the Mac installers. It does not accept playlist links or run a cloud download API. Download jobs run locally in the Mac app and save songs to the folder the user chooses.

## Website

The website is a static Vercel deployment. Its build copies `index.html`, `style.css` and `privacy.html` into `public/`. There are no website API routes, cloud workers, visitor access keys, cookies, or playlist-processing services.

Build the static site with:

```sh
npm run build
```

## Mac app

The current public installer is version 1.3.0 for Apple Silicon and Intel Macs, macOS 12 or later. The app saves songs one by one to a chosen folder. Spotify supplies track metadata; the app finds matching audio from public sources and does not decrypt Spotify streams. Provider availability and matching accuracy vary.

The app is not Apple-notarized. See the release and source before installing. Download only media you own or have permission to save, and follow platform terms.

[Download the 1.3.0 release](https://github.com/alaamari/Youtube-Playlist_Download/releases/tag/v1.3.0)
