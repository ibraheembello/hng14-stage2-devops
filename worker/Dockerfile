# syntax=docker/dockerfile:1.7
# ---------- builder stage ----------
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt ./

RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --upgrade pip==24.3.1 \
 && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---------- final stage ----------
FROM python:3.12-slim AS final

RUN groupadd --system app \
 && useradd --system --gid app --no-create-home --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --chown=app:app worker.py healthcheck.py ./

USER app

# The worker has no http port; its healthcheck script instead reads a
# heartbeat key the worker refreshes every WORKER_HEARTBEAT_INTERVAL
# seconds and exits non-zero when the key is missing or stale.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "healthcheck.py"]

CMD ["python", "worker.py"]
