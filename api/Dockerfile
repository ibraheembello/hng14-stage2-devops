# syntax=docker/dockerfile:1.7
# ---------- builder stage ----------
# Install python dependencies into an isolated virtualenv. This stage
# contains pip and build tools; it is discarded before the final image
# is built so none of that ships to production.
FROM python:3.12-slim AS builder

WORKDIR /build

# Copy only the requirements file first so the pip-install layer is
# cached across source-only changes.
COPY requirements.txt ./

RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --upgrade pip==24.3.1 \
 && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---------- final stage ----------
# A minimal runtime image with the virtualenv copied over and a
# dedicated non-root user. No build tools, no dev dependencies.
FROM python:3.12-slim AS final

# Create an unprivileged user; --no-create-home and nologin shell
# reduce the blast radius if the container is ever compromised.
RUN groupadd --system app \
 && useradd --system --gid app --no-create-home --shell /usr/sbin/nologin app

# Copy the prebuilt virtualenv from the builder stage and put it on
# PATH. PYTHONUNBUFFERED=1 keeps stdout/stderr unbuffered so logs
# show up in docker logs immediately.
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy only the application source (the .dockerignore keeps caches,
# .env, and editor files out of the build context entirely).
COPY --chown=app:app main.py healthcheck.py ./

USER app

EXPOSE 8000

# The script exits 0 when GET /health returns 200, otherwise 1.
# --start-period gives uvicorn time to boot before the first probe.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "healthcheck.py"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
