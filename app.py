"""ClipNest — a small, permission-based video downloader web app.

Supports public videos from a curated set of sites where extraction is permitted.
No cookies, logins, private posts, DRM bypass, or unrestricted URL fetching.
"""
from __future__ import annotations

import ipaddress
import logging
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DOWNLOAD_ROOT = Path(os.getenv("DOWNLOAD_DIR", Path(tempfile.gettempdir()) / "clipnest-downloads"))
DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)

MAX_BYTES = 200 * 1024 * 1024
MAX_DURATION_SECONDS = 30 * 60
JOB_TTL_SECONDS = 15 * 60
MAX_CONCURRENT_JOBS = 2
ALLOWED_DOMAINS = {
    "youtube.com": "YouTube", "youtu.be": "YouTube",
    "youtube-nocookie.com": "YouTube", "instagram.com": "Instagram",
    "facebook.com": "Facebook", "fb.watch": "Facebook",
    "x.com": "X", "twitter.com": "X", "tiktok.com": "TikTok",
    "vimeo.com": "Vimeo", "dailymotion.com": "Dailymotion",
    "linkedin.com": "LinkedIn", "reddit.com": "Reddit",
    "redd.it": "Reddit", "pinterest.com": "Pinterest",
    "pin.it": "Pinterest", "threads.net": "Threads",
    "twitch.tv": "Twitch", "snapchat.com": "Snapchat",
}

app = FastAPI(title="ClipNest Downloader", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS)
lock = threading.RLock()
jobs: dict[str, dict] = {}
rate_events: dict[str, deque] = defaultdict(deque)
logger = logging.getLogger("clipnest")


class LinkRequest(BaseModel):
    url: str = Field(min_length=12, max_length=2048)


class DownloadRequest(LinkRequest):
    quality: Literal["best", "1080", "720", "480"] = "720"


def check_url(url: str) -> tuple[str, str]:
    """Allow only known, public, HTTPS social platform URL hostnames."""
    url = url.strip()
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port  # Reading this also detects malformed port numbers.
    except ValueError:
        raise HTTPException(400, "Paste a valid HTTPS video URL from a supported platform.") from None
    if parsed.scheme.lower() != "https" or not hostname or parsed.username or parsed.password or port not in (None, 443):
        raise HTTPException(400, "Paste a valid HTTPS video URL from a supported platform.")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass  # A normal DNS hostname, not an IP literal.
    else:
        raise HTTPException(400, "IP addresses are not supported.")
    for domain, label in ALLOWED_DOMAINS.items():
        if hostname == domain or hostname.endswith("." + domain):
            return url, label
    raise HTTPException(400, "This website is not yet supported. Try a link from the platforms below.")


def check_rate(request: Request, *, limit: int = 16, window: int = 3600):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    with lock:
        hits = rate_events[ip]
        while hits and hits[0] <= now - window:
            hits.popleft()
        if len(hits) >= limit:
            raise HTTPException(429, "Too many requests. Please try again later.")
        hits.append(now)


def options(**kwargs):
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "playlistend": 1,
        "cachedir": False,
        "socket_timeout": 15,
        "retries": 2,
        "fragment_retries": 1,
        "extractor_retries": 1,
        "skip_download": True,
        "ignoreerrors": False,
        **kwargs,
    }


def clean_error(error: Exception) -> str:
    message = str(error).lower()
    if any(t in message for t in ("sign in to confirm", "not a bot", "unusual traffic")):
        return "YouTube is blocking this server's access. Try another permitted public video; some servers cannot access YouTube."
    if any(t in message for t in ("javascript runtime", "challenge solving", "no supported javascript")):
        return "YouTube playback checks could not run. The server's yt-dlp/Deno setup may need an update."
    if any(t in message for t in ("login", "sign in", "private", "cookies", "authentication")):
        return "This video may require sign-in or be private. Try a public video you have permission to save."
    if any(t in message for t in ("unsupported url", "no suitable extractor")):
        return "This particular link isn't supported yet. Try a direct public video link."
    if any(t in message for t in ("requested format", "format is not available")):
        return "That quality isn't available for this video. Try Best available."
    if "larger than" in message or "too large" in message:
        return "This video exceeds the free 200 MB file limit."
    if "duration" in message or "too long" in message:
        return "This demo supports videos up to 30 minutes long."
    return "We couldn't access that video. It may be restricted, unavailable, or blocked by the platform."


def best_thumbnail(info: dict) -> str | None:
    thumbnails = info.get("thumbnails") or []
    thumbs = [x.get("url") for x in thumbnails if isinstance(x, dict) and x.get("url", "").startswith("https://")]
    thumb = info.get("thumbnail")
    if thumb and isinstance(thumb, str) and thumb.startswith("https://"):
        return thumb
    return thumbs[-1] if thumbs else None


def normalize_info(info: dict, platform: str) -> dict:
    if not info or "entries" in info:
        raise HTTPException(400, "Please paste a single video link, not a playlist or profile.")
    duration = info.get("duration")
    if isinstance(duration, (int, float)) and duration > MAX_DURATION_SECONDS:
        raise HTTPException(413, "This demo supports videos up to 30 minutes long.")
    if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
        raise HTTPException(400, "Live streams aren't supported. Try a recorded public video.")
    return {
        "title": str(info.get("title") or "Untitled video")[:180],
        "platform": platform,
        "duration": round(duration) if isinstance(duration, (int, float)) else None,
        "thumbnail": best_thumbnail(info),
        "uploader": str(info.get("uploader") or "")[:80],
    }


def format_for(quality: str) -> str:
    if quality == "best":
        return "bv[ext=mp4]+ba[ext=m4a]/bv+ba/b[ext=mp4]/b"
    return (
        f"bv[height<={quality}][ext=mp4]+ba[ext=m4a]/"
        f"b[height<={quality}][ext=mp4]/"
        f"bv[height<={quality}]+ba/"
        f"b[height<={quality}]"
    )


def update_job(job_id: str, **fields):
    with lock:
        if job_id in jobs:
            jobs[job_id].update(fields)


def cleanup_jobs():
    expired = []
    with lock:
        now = time.time()
        for job_id, job in list(jobs.items()):
            if job["status"] in ("ready", "error") and now - job["updated_at"] > JOB_TTL_SECONDS:
                expired.append((job_id, job["directory"]))
                del jobs[job_id]
    for _, directory in expired:
        shutil.rmtree(directory, ignore_errors=True)


def run_job(job_id: str, url: str, platform: str, quality: str):
    with lock:
        job = jobs[job_id]
        folder = Path(job["directory"])
    update_job(job_id, status="downloading", updated_at=time.time())

    def progress_hook(data: dict):
        status = data.get("status")
        if status == "finished":
            update_job(job_id, status="processing", progress=100, updated_at=time.time())
            return
        if status != "downloading":
            return
        downloaded = data.get("downloaded_bytes", 0)
        if downloaded > MAX_BYTES:
            raise DownloadError("File is too large")
        total = data.get("total_bytes") or data.get("total_bytes_estimate")
        percent = min(99, round(downloaded / total * 100)) if total else None
        update_job(job_id, progress=percent, eta=data.get("eta"), updated_at=time.time())

    def match_filter(info, *, incomplete):
        duration = info.get("duration")
        if duration and duration > MAX_DURATION_SECONDS:
            return "Video duration is too long"
        filesize = info.get("filesize") or info.get("filesize_approx")
        if filesize and filesize > MAX_BYTES:
            return "Video is too large"
        return None

    try:
        with YoutubeDL(options(
            skip_download=False,
            outtmpl=str(folder / "%(title).100B [%(id)s].%(ext)s"),
            format=format_for(quality),
            merge_output_format="mp4",
            progress_hooks=[progress_hook],
            match_filter=match_filter,
            max_filesize=MAX_BYTES,
            # Sites requiring a login or site cookies aren't supported.
        )) as ydl:
            info = ydl.extract_info(url, download=True)
        if not info or "entries" in info:
            raise DownloadError("No single video found")
        candidates = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() not in (".part", ".ytdl", ".json")]
        if not candidates:
            raise DownloadError("No file created")
        file = max(candidates, key=lambda p: p.stat().st_size)
        if file.stat().st_size > MAX_BYTES:
            raise DownloadError("File is too large")
        update_job(
            job_id,
            status="ready",
            progress=100,
            filename=file.name,
            path=str(file),
            size=file.stat().st_size,
            updated_at=time.time(),
        )
    except Exception as exc:
        logger.warning("Video processing failed: %s", exc)
        update_job(job_id, status="error", error=clean_error(exc), updated_at=time.time())
        shutil.rmtree(folder, ignore_errors=True)


@app.get("/", include_in_schema=False)
def homepage():
    return FileResponse(STATIC / "index.html", media_type="text/html")


@app.get("/privacy", include_in_schema=False)
def privacy():
    return FileResponse(STATIC / "privacy.html", media_type="text/html")


@app.get("/terms", include_in_schema=False)
def terms():
    return FileResponse(STATIC / "terms.html", media_type="text/html")


@app.get("/api/health")
def health():
    return {"ok": True, "service": "ClipNest"}


@app.post("/api/info")
def video_info(payload: LinkRequest, request: Request):
    check_rate(request)
    url, platform = check_url(payload.url)
    try:
        with YoutubeDL(options()) as ydl:
            info = ydl.extract_info(url, download=False)
        return normalize_info(info, platform)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Metadata extraction failed: %s", exc)
        raise HTTPException(422, clean_error(exc)) from None


@app.post("/api/download", status_code=202)
def create_download(payload: DownloadRequest, request: Request):
    check_rate(request)
    url, platform = check_url(payload.url)
    cleanup_jobs()
    with lock:
        active = sum(1 for job in jobs.values() if job["status"] in ("queued", "downloading", "processing"))
        if active >= MAX_CONCURRENT_JOBS:
            raise HTTPException(429, "The free server is busy. Please try again shortly.")
        job_id = uuid.uuid4().hex
        folder = DOWNLOAD_ROOT / job_id
        folder.mkdir(parents=True, exist_ok=False)
        jobs[job_id] = {
            "status": "queued", "progress": None, "eta": None,
            "directory": str(folder), "created_at": time.time(), "updated_at": time.time(),
            "filename": None, "path": None, "size": None, "error": None,
        }
    executor.submit(run_job, job_id, url, platform, payload.quality)
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    cleanup_jobs()
    with lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Download expired or not found.")
        return {
            "status": job["status"], "progress": job["progress"], "eta": job["eta"],
            "error": job["error"], "filename": job["filename"], "size": job["size"],
            "download_url": f"/api/files/{job_id}" if job["status"] == "ready" else None,
        }


@app.get("/api/files/{job_id}")
def serve_file(job_id: str):
    cleanup_jobs()
    with lock:
        job = jobs.get(job_id)
        if not job or job["status"] != "ready":
            raise HTTPException(404, "File not found or expired.")
        path = Path(job["path"])
        filename = job["filename"]
    if not path.is_file():
        raise HTTPException(404, "File is no longer available.")
    return FileResponse(path, filename=filename, media_type="application/octet-stream")
