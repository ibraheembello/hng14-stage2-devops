# syntax=docker/dockerfile:1.7
# ---------- deps stage ----------
# Install production dependencies in an isolated layer. Dev deps and
# the npm cache never make it into the final image.
FROM node:20-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json* ./

# Use npm ci when a lockfile exists for deterministic installs; fall
# back to npm install for the starter layout that may lack one.
RUN if [ -f package-lock.json ]; then \
      npm ci --omit=dev; \
    else \
      npm install --omit=dev; \
    fi

# ---------- final stage ----------
FROM node:20-alpine AS final

# Alpine images already ship with BusyBox wget, which the HEALTHCHECK
# below uses. No extra apk add is needed.

RUN addgroup -S app \
 && adduser -S -G app -H -s /sbin/nologin app

WORKDIR /app

COPY --from=deps --chown=app:app /app/node_modules ./node_modules
COPY --chown=app:app package.json app.js ./
COPY --chown=app:app views ./views

USER app

EXPOSE 3000

# --spider makes wget ignore the response body; we only care about
# the http status. BusyBox wget exits non-zero on 4xx/5xx.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["wget", "--spider", "-q", "http://127.0.0.1:3000/health"]

CMD ["node", "app.js"]
