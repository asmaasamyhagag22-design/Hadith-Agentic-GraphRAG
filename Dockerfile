# syntax=docker/dockerfile:1

# --- Stage 1: slim cloud dependency builder (no torch / sentence-transformers / faiss / bm25) ---
FROM python:3.13-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /build

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir uv \
    && uv sync --locked --no-dev --no-install-project --only-group cloud \
    && rm -rf /root/.cache /tmp/*


# --- Stage 2: non-root runtime image ---
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH="/app:/app/src" \
    HOME="/home/musnad" \
    MUSNAD_CLOUD="1" \
    MUSNAD_RETRIEVAL_PIPELINE="upgraded" \
    MUSNAD_DEMO_REPLAY="0" \
    MUSNAD_REPLAY_SPEED="1.0" \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS="false"

RUN groupadd --system musnad \
    && useradd --system --gid musnad --home-dir /home/musnad --create-home --shell /sbin/nologin musnad

WORKDIR /app

COPY --from=builder --chown=musnad:musnad /opt/venv /opt/venv

# Copy application code & runtime-only data artifacts
COPY --chown=musnad:musnad app /app/app
COPY --chown=musnad:musnad src /app/src
COPY --chown=musnad:musnad data/demo/recorded_runs.json /app/data/demo/recorded_runs.json
COPY --chown=musnad:musnad data/processed/vectors_matn_gemini001_3072.npy /app/data/processed/vectors_matn_gemini001_3072.npy
COPY --chown=musnad:musnad data/processed/chunk_ids_matn.json /app/data/processed/chunk_ids_matn.json
COPY --chown=musnad:musnad data/processed/muslim_chunks.json /app/data/processed/muslim_chunks.json
COPY --chown=musnad:musnad data/processed/sanad_graph.sqlite /app/data/processed/sanad_graph.sqlite

USER musnad

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4).status == 200 else 1)"]

CMD ["streamlit", "run", "app/streamlit_app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true", \
     "--server.enableCORS=false", \
     "--server.enableXsrfProtection=false", \
     "--server.enableWebsocketCompression=true", \
     "--server.fileWatcherType=none", \
     "--browser.gatherUsageStats=false"]
