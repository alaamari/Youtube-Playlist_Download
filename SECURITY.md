# Security status

The public website uses a bounded cloud worker on Vercel Hobby with shared limits in a free Upstash database. Requests pass BotID Basic, exact-origin and strict URL checks before atomic quota reservation. Limits are 20 songs, 64 MB per song, 256 MB total, 20 minutes per session, one concurrent session, 10 shared sessions per rolling 30 days and 3 sessions per connection per day. A provider quota failure rejects the request before a worker starts. The project is not configured for a paid plan or paid overages; free provider quotas can still make downloads unavailable until reset.

Each sandbox is ephemeral and receives only a job-specific control key, a separate per-file token key, an expiry time, and the exact website origin. Control credentials are accepted only in authorization headers. Song URLs use scoped short-lived file tokens, not the job key. Source links and downloaded media are processed in the temporary worker and removed when it stops or expires. Worker networking is allowlisted for the documented audio sources and blocks private network ranges. No browser cookies or account passwords are accepted, and visitors do not need an access key.

The website serves an explicit static allowlist with a restrictive Content Security Policy, frame protection, no-referrer and content-type protection. Python source, packages, desktop build files and environment files are not published as static files. Production credentials remain server-side. No paid deployment tier, add-on or automatic upgrade is configured.

The 1.3.0 Mac build replaces Python 3.12.0 and FFmpeg 7.1 with Python 3.13.17 and FFmpeg 9.0.2. Its patched spotDL desktop engine excludes FastAPI, Starlette, AnyIO and Uvicorn, and it opens no web server. URL validation accepts only supported Spotify album/track/playlist and YouTube video/playlist shapes. It removes tracking parameters and rejects YouTube redirects. Downloads use argument arrays rather than shell commands.

A package audit reports known advisories, not proof of complete safety. Keep source providers and dependencies updated. Source availability, audio matching, rights and platform restrictions remain the user’s responsibility.

The release is ad-hoc signed and is NOT Apple-notarized. The maintainer currently has a free developer account; Developer ID signing requires active Apple Developer Program membership and a locally installed certificate. Do not claim notarization until Apple has accepted the exact signed release and staple/Gatekeeper checks pass.

For public-safe reports use the GitHub issue tracker. Do not attach passwords, browser cookies, private signing keys or other secrets. If a report contains a secret, revoke it through the issuing provider rather than reposting it. No private reporting channel is currently configured.
