# ClipNest V2 — All-in-One Video Downloader Website

A responsive downloader website with dark/light mode, Poppins typography, original blue-to-teal branding, a single-URL workflow and a Python backend. This UI was designed independently, using the familiar simple video-downloader page pattern as inspiration; it is not a copy of another service's copyrighted assets or branding.

## Features
- Responsive site, mobile and desktop layout, theme memory
- Paste URL, fetch supported public video metadata, select available format, download within hosting capacity
- FastAPI / yt-dlp / FFmpeg backend, Deno runtime included in Docker image for supported YouTube playback checks
- Basic abuse limits and supported-domain validation
- Optional Google Analytics 4 integration (disabled by default; loads only after explicit consent)
- Starter Privacy and Terms pages (owner must review and customise before production)
- Original FAQs and how-to explanations

## Deploy to Render
1. Extract the ZIP and open the **ClipNest** subfolder. Upload its files *and folders* into the root of your GitHub repository.
2. Render > New Web Service > GitHub repository > Language Docker > Free (for testing).
3. Leave Root Directory empty, deploy and access the Render-issued URL.
4. Future GitHub commits automatically redeploy if auto-deploy is on.

See `UPDATES_HINDI.txt` for step-by-step Hinglish instructions.

## Tracking visitors
1. Create a GA4 web data stream at https://analytics.google.com.
2. Put your own `G-...` measurement ID into `static/site-config.js`, commit and redeploy.
3. Consent banner is shown on the website. Visitors who reject are not measured via GA4.
4. GA4 logs visits and basic platform-level events (`video_info_success`, `video_info_failed`, `download_started`, `video_ready`, `download_failed`). **URLs and video titles are not sent to GA4** by this implementation.
5. Backend rate limits are not a persistent analytics datastore. Track precise completed downloads separately with a proper database, preferably after adding abuse and privacy controls.

## Monetisation note
AdSense approval is *not guaranteed*. Google Publisher Policies restrict sites that enable downloading streaming videos where prohibited by a provider. Copyright rules, clear site purpose, original content, privacy terms and safe ad placements matter. Never disguise an ad as a Download button. Google Ads (buy traffic) and Google AdSense (earn from displaying ads) are different products.

## Current free-demo limits
- Max 30 minutes per clip; max 200 MB output file.
- 2 active jobs at once; 16 requests/hour per IP.
- Temporary files are eligible for cleanup after 15 minutes.
- Links must use HTTPS and match known platform domains. No playlist, login, cookie or DRM bypass.
- Source platforms and Render can still block video extraction; site UI working does not guarantee every link works.
- Render Free instances are **not** recommended for high-volume production use.

## Quick tests
```
pip install -r requirements.txt pytest httpx
pytest -q
```
The test suite mocks platform extraction; it does not guarantee access to YouTube, Instagram, etc. from any hosting IP.
