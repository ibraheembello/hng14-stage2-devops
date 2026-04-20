# FIXES.md

Every bug found in the starter repo, what was wrong, and what was changed.
Line numbers refer to the **original** upstream state of each file.

---

## 1. `api/.env` — committed secret in git history

- **File:** `api/.env`, line 1 (`REDIS_PASSWORD=supersecretpassword123`)
- **Problem:** The starter repo shipped a real `.env` file containing a hard-coded password. It was tracked by git and present in the history (`a98a2d1` "first commit"). The task explicitly says `.env` must never appear in the repo or its history.
- **Fix:**
  1. Deleted the file from the working tree and git index.
  2. Added a root-level `.env.example` with placeholder values for every variable the stack needs.
  3. Added a comprehensive `.gitignore` excluding `.env` (and permitting only `.env.example`).
  4. Ran `git filter-branch --index-filter "git rm --cached --ignore-unmatch api/.env" -- --all` and force-pushed to purge the file from every historical commit. Confirmed with `git log --all --full-history -- api/.env` returning empty.

## 2. `api/main.py:8` — Redis host hardcoded to `localhost`

- **Problem:** `r = redis.Redis(host="localhost", port=6379)`. Works on a dev laptop but fails inside docker-compose, where Redis is reachable only by its service name (`redis`) on the internal network.
- **Fix:** Read `REDIS_HOST`, `REDIS_PORT`, and `REDIS_PASSWORD` from environment variables, with sensible defaults (`redis`, `6379`, no password). Also set `decode_responses=True` to avoid manual `.decode()` calls downstream.

## 3. `worker/worker.py:6` — Redis host hardcoded to `localhost`

- **Problem:** Identical to #2 — `redis.Redis(host="localhost", port=6379)` in the worker. Fails in containers.
- **Fix:** Same env-var configuration pattern as the API.

## 4. `frontend/app.js:6` — API URL hardcoded to `http://localhost:8000`

- **Problem:** `const API_URL = "http://localhost:8000";`. Inside a container, `localhost` refers to the container itself, not the API service — the frontend would never find the API.
- **Fix:** `const API_URL = process.env.API_URL || 'http://api:8000';`. Default assumes docker-compose service name.

## 5. `api/main.py` — no `/health` endpoint

- **Problem:** A Dockerfile `HEALTHCHECK` requires something to hit. The starter API exposed only `POST /jobs` and `GET /jobs/{id}`.
- **Fix:** Added `GET /health` that pings Redis and returns `{"status": "ok"}` (HTTP 200) when reachable or HTTP 503 otherwise.

## 6. `frontend/app.js` — no `/health` endpoint

- **Problem:** Same as #5 — the frontend container needs a liveness endpoint.
- **Fix:** Added `GET /health` returning `{status: 'ok'}`. Kept shallow because the frontend's only real dependency is the API, and any real failure surfaces when a user submits a job.

## 7. `worker/worker.py` — no healthcheck mechanism

- **Problem:** The worker is a long-running background loop with no HTTP port. Docker's `HEALTHCHECK` needs something to invoke, but `curl localhost` cannot be used.
- **Fix:**
  - The worker now writes the current Unix timestamp to a `worker:heartbeat` Redis key on every loop iteration, with a TTL of three heartbeat intervals (controlled by `WORKER_HEARTBEAT_INTERVAL`).
  - Added `worker/healthcheck.py` which reads the key, compares the age to `MAX_AGE_SECONDS`, and exits `0` (healthy) or `1` (stale/missing/redis-unreachable). The Dockerfile's `HEALTHCHECK` invokes this script.

## 8. `api/main.py:8` / `api/.env:1` — password configured but unused

- **Problem:** The `.env` shipped with `REDIS_PASSWORD=supersecretpassword123` but the code never read it, and Redis itself was not configured to require authentication. Dead, misleading config.
- **Fix:** API and worker now read `REDIS_PASSWORD` from env and pass it to the Redis client. The Redis service in `docker-compose.yml` will be configured with `--requirepass "$REDIS_PASSWORD"` (Phase 5).

## 9. `worker/worker.py:4,14-18` — no SIGTERM handling

- **Problem:** `import signal` was present but unused; the `while True:` loop never checked for a shutdown signal. Docker sends `SIGTERM` on `docker stop`, waits 10 s, then sends `SIGKILL`. The worker would be force-killed mid-job.
- **Fix:** Registered `_handle_shutdown` for `SIGTERM` and `SIGINT`. The loop condition is now `while not _shutdown:`, so the worker finishes its current job and exits cleanly.

## 10. `api/main.py` — no Redis startup readiness check

- **Problem:** `r = redis.Redis(...)` does not actually open a connection; that happens lazily on the first command. If Redis was not ready when the API received its first request, the request crashed with a `ConnectionError`.
- **Fix:** Added a FastAPI `@app.on_event("startup")` hook that retries `r.ping()` up to 10 times with a 2-second delay, raising if Redis never becomes reachable. Combined with docker-compose's `depends_on: condition: service_healthy`, this gives defence in depth.

## 11. `api/main.py:4` — `import os` unused

- **Problem:** `import os` was present but never referenced.
- **Fix:** Resolved organically — the module now uses `os.environ.get(...)` for every runtime config value.

## 12. `worker/worker.py:3,4` — `import os` and `import signal` unused

- **Problem:** Both imports were present but never referenced.
- **Fix:** `os` is now used for `os.environ.get(...)` (see #3), and `signal` is used by the SIGTERM handler (see #9).

## 13. `api/main.py:20-22` — 200 response for missing job

- **Problem:** `GET /jobs/{job_id}` returned `{"error": "not found"}` with HTTP 200 when the job didn't exist. Client code cannot easily distinguish success from not-found.
- **Fix:** Raise `HTTPException(status_code=404, detail="job not found")` so the response carries the correct status.

## 14. `api/requirements.txt` — unpinned dependencies

- **Problem:** `fastapi`, `uvicorn`, and `redis` had no version specifiers. Two builds a week apart could install different versions and behave differently — a reproducibility red flag.
- **Fix:** Pinned to `fastapi==0.115.6`, `uvicorn[standard]==0.32.1`, `redis==5.2.1`. Used `uvicorn[standard]` for full websocket/HTTP-tools support.

## 15. `worker/requirements.txt` — unpinned dependency

- **Problem:** `redis` with no version specifier.
- **Fix:** Pinned to `redis==5.2.1`.

## 16. `api/requirements.txt` — no test dependencies

- **Problem:** The task requires pytest unit tests with Redis mocked and a coverage report. The starter had no pytest/coverage/fakeredis in the deps file, and putting them in `requirements.txt` would bloat the production image.
- **Fix:** Added `api/requirements-dev.txt` referencing `-r requirements.txt` and adding `pytest`, `pytest-cov`, `fakeredis`, `httpx` (for FastAPI's TestClient), and `flake8` for lint. The production Docker image installs only `requirements.txt`; the CI test job installs the dev file.

## 17. `frontend/app.js:29` — listen port hardcoded

- **Problem:** `app.listen(3000, ...)`. Inflexible, and contradicts the rule "all configuration must come from environment variables."
- **Fix:** `const PORT = parseInt(process.env.FRONTEND_PORT || process.env.PORT || '3000', 10);` then `app.listen(PORT, ...)`.

## 18. `frontend/views/index.html:31-38` — poll loop runs forever on non-completed states

- **Problem:** `if (data.status !== 'completed') setTimeout(..., 2000)` meant the browser polled every 2 seconds forever for any status that was not exactly `'completed'` — including `undefined`, `null`, or a future `'failed'` state. Also no handling when `/status` returned a non-ok HTTP response (a 404 would still trigger another poll).
- **Fix:**
  - Defined `TERMINAL_STATES = ['completed', 'failed', 'error']`; stop polling if the current status is in that list.
  - Stop on any non-ok HTTP response (e.g. a 404 bubbled up from the API's new behaviour — see #13).
  - Cap at `MAX_POLL_ATTEMPTS = 60` (~2 minutes) so nothing can loop indefinitely even if a new state is introduced later.
