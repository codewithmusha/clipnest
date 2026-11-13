# ClipNest: Python + yt-dlp + Deno for YouTube JS challenges
FROM denoland/deno:bin-2.9.7 AS deno
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000 \
    DENO_NO_UPDATE_CHECK=1 \
    DENO_DIR=/tmp/deno-cache

# yt-dlp now needs a modern JS runtime to handle YouTube's player scripts.
COPY --from=deno /deno /usr/local/bin/deno
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && deno --version

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py ./
COPY static/ ./static/
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /tmp/clipnest-downloads /tmp/deno-cache \
    && chown -R appuser:appuser /tmp/clipnest-downloads /tmp/deno-cache /app
USER appuser
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
