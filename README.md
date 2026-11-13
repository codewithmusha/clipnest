# ClipNest — Free Video Downloader Website Starter

A clean, responsive **dark + light theme** website, built with **HTML + CSS + JavaScript + Python (FastAPI) + yt-dlp + FFmpeg**.

### Features
- One link field for supported sites (YouTube, Instagram, Facebook, X/Twitter, TikTok, LinkedIn, Vimeo, Reddit, Pinterest and more).
- Preview with video title / thumbnail where available.
- Best available / 1080p / 720p / 480p options (only if the source offers them).
- Download progress and a clear save-file button when the video is ready.
- Dark / light theme, saved in your browser.
- Mobile-friendly, no database, no login, no API key.
- Free-server guardrails: HTTPS domain allowlist, 2 concurrent downloads max, basic per-IP rate limit, 200 MB / 30 minute cap, files expire after 15 minutes.

**IMPORTANT:** Only use this to download content that you own or are authorized to save, and follow each platform's rules. This is not a DRM bypass, private-video downloader, or a promise that every platform works. Platforms often require sign-in or block hosting-provider IPs (especially YouTube). Downloads are not guaranteed; availability changes as platforms update.

## Deploy free on Render (simple steps)
1. Create a **GitHub** repository and upload **all these files and the `static` folder**. Keep the `Dockerfile` at the root.
2. Open [dashboard.render.com](https://dashboard.render.com) → **New** → **Web Service**.
3. Connect the GitHub repository.
4. Choose **Language/Runtime: Docker** and **Instance Type: Free**. (Render should find the Dockerfile automatically.)
5. Click **Deploy Web Service**. Render provides a URL similar to `https://your-app-name.onrender.com`.
6. Open that URL. Your website is live. You don't need to purchase a domain to test.

You can also import `render.yaml` as a Render Blueprint. Your app listens on the `PORT` provided by Render.

### Free-hosting limitations
Render Free is intended for experiments: it sleeps after **15 minutes of inactivity**, has bandwidth/compute limits, and **temporary files are lost when it sleeps or restarts**. Large videos, public traffic and some platform sites may fail. It may suspend services generating unusually high outbound traffic. Do not promise visitors unlimited free downloading.

## Run on your computer
Python 3.10+ and **FFmpeg** installed:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Visit `http://127.0.0.1:8000`.

## Project files
- `static/index.html` — website
- `static/styles.css` — dark/light theme and responsive layout
- `static/app.js` — UI, preview, progress and downloads
- `app.py` — FastAPI backend, URL validation, safe limits, temporary downloads
- `Dockerfile` — includes FFmpeg for Render
- `render.yaml` — optional one-click setup

## Customization
- Brand and copy: `static/index.html`
- Colors: CSS variables at the start of `static/styles.css`
- Limits / supported hostname list: constants in `app.py`

## Hindi short guide
भाई, ZIP extract करो → GitHub पर सारी files upload करो → Render पर **New Web Service** बनाकर **Docker + Free** select करो → Deploy करो। URL मिल जाएगा। Theme switch और mobile design पहले से तैयार हैं।

**Note:** I can build the project files here, but the actual Render deployment requires access to your own GitHub/Render accounts. This starter was tested locally; platform downloads depend on live platform access and are not guaranteed.
