"""Run with pytest after pip install -r requirements.txt and pip install pytest httpx."""
import time
from pathlib import Path
from unittest.mock import patch

import app as site
from fastapi.testclient import TestClient

client = TestClient(site.app)


class FakeYoutubeDL:
    def __init__(self, config):
        self.config = config
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def extract_info(self, url, download=False):
        info = {"title": "My sample clip", "id": "abc123", "duration": 55, "uploader": "Creator", "thumbnail": None}
        if download:
            directory = Path(self.config["outtmpl"]).parent
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "my-clip.mp4").write_bytes(b"mock sample")
            self.config["progress_hooks"][0]({"status": "downloading", "downloaded_bytes": 11, "total_bytes": 11})
            self.config["progress_hooks"][0]({"status": "finished"})
        return info


def test_homepage_and_health():
    assert client.get("/").status_code == 200
    assert "One simple place" in client.get("/").text
    assert client.get("/api/health").json()["ok"] is True


def test_url_allowlist():
    good = ["https://www.youtube.com/watch?v=example", "https://x.com/example/status/123", "https://instagram.com/reel/test"]
    for url in good:
        assert site.check_url(url)[1]
    bad = ["https://evil.com/v", "https://youtube.com.evil.net/watch", "http://youtube.com/watch", "https://youtube.com:444/watch", "https://127.0.0.1/test"]
    for url in bad:
        try:
            site.check_url(url)
        except Exception as exc:
            assert exc.status_code == 400
        else:
            assert False, url


def test_info_and_video_download(tmp_path):
    with patch.object(site, "YoutubeDL", FakeYoutubeDL):
        response = client.post("/api/info", json={"url": "https://youtube.com/watch?v=abc123"})
        assert response.status_code == 200, response.text
        assert response.json()["title"] == "My sample clip"
        response = client.post("/api/download", json={"url": "https://youtube.com/watch?v=abc123", "quality": "720"})
        assert response.status_code == 202, response.text
        id = response.json()["job_id"]
        for _ in range(100):
            status = client.get(f"/api/jobs/{id}").json()
            if status["status"] == "ready":
                break
            time.sleep(.02)
        assert status["status"] == "ready", status
        file = client.get(status["download_url"])
        assert file.status_code == 200
        assert file.content == b"mock sample"
