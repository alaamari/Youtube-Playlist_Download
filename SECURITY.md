# Security status

Public cloud job creation is disabled. The website serves an explicit static file allowlist and a paused API endpoint. No account passwords, cookies, access keys or production secrets are required by this release. Do not restore the experimental cloud implementation from repository history without independent review and verified billing controls.

The 1.3.0 Mac build replaces Python 3.12.0 and FFmpeg 7.1 with Python 3.13.17 and FFmpeg 9.0.2. Its patched spotDL desktop engine excludes FastAPI, Starlette, AnyIO and Uvicorn, and it opens no web server. URL validation accepts only supported Spotify album/track/playlist and YouTube video/playlist shapes. It removes tracking parameters and rejects YouTube redirects. Downloads use argument arrays rather than shell commands.

A package audit reports known advisories, not proof of complete safety. Keep source providers and dependencies updated. Source availability, audio matching, rights and platform restrictions remain the user’s responsibility.

The release is ad-hoc signed and is NOT Apple-notarized. The maintainer currently has a free developer account; Developer ID signing requires active Apple Developer Program membership and a locally installed certificate. Do not claim notarization until Apple has accepted the exact signed release and staple/Gatekeeper checks pass.

For public-safe reports use the GitHub issue tracker. Do not attach passwords, browser cookies, private signing keys or other secrets. If a report contains a secret, revoke it through the issuing provider rather than reposting it. No private reporting channel is currently configured.
