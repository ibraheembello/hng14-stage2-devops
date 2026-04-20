# hng14-stage2-devops

A containerized job-processing microservice app with a full CI/CD
pipeline on GitHub Actions.

Built for the **HNG Internship — DevOps track, Stage 2**.

---

## What this repo is

Three small services backed by Redis:

- **frontend** — Node/Express. Serves a page at `/` that lets a user
  submit a job and poll its status. Proxies those calls to the API.
- **api** — Python/FastAPI. Accepts `POST /jobs`, assigns a UUID,
  pushes the id onto a Redis list, and exposes `GET /jobs/{id}`.
- **worker** — Python. Blocks on `BRPOP` for the Redis list, takes
  ~2 s to "process" a job, writes `status=completed` back.
- **redis** — queue + status store. Internal only, never exposed
  to the host.

```
 ┌──────────┐  HTTP  ┌─────┐  LPUSH/HGET   ┌────────┐  BRPOP/HSET   ┌────────┐
 │ browser  ├───────►│ fe  │──────────────►│ redis  │◄──────────────┤ worker │
 └──────────┘        └──┬──┘               └────────┘               └────────┘
                        │  HTTP (internal)
                        ▼
                    ┌───────┐
                    │  api  │
                    └───────┘
```

Every service runs as a non-root user inside a multi-stage image,
has a working `HEALTHCHECK`, and is brought up via Docker Compose
with strict `depends_on: service_healthy` ordering.

---

## Prerequisites

- **Docker Engine** ≥ 24 (ships with Docker Desktop ≥ 4.25)
- **Docker Compose** v2.20+ (included with Docker Desktop)
- **git**
- A POSIX shell (bash / zsh / Git Bash on Windows) for the helper
  scripts under `scripts/`.

That's everything. All language toolchains (Python, Node, npm, pip)
live inside the Docker images — you do not install them on the host.

---

## Quickstart

```bash
git clone https://github.com/ibraheembello/hng14-stage2-devops.git
cd hng14-stage2-devops

cp .env.example .env
# Edit .env — at minimum set a real REDIS_PASSWORD.

docker compose up -d --wait
```

`--wait` blocks until every service's healthcheck reports `healthy`,
so when the command returns you know the stack is actually ready.

Open the frontend:

- <http://localhost:3000> in a browser, **or**
- submit a job from the terminal (example below).

Shut everything down with:

```bash
docker compose down -v
```

`-v` also drops the Redis append-only-file volume so a next `up`
starts with an empty queue.

---

## Submitting a job

```bash
# Create a job and capture the id
JOB_ID=$(curl -s -X POST http://localhost:3000/submit | jq -r .job_id)
echo "job: $JOB_ID"

# Poll status every second until it completes
while : ; do
  curl -s "http://localhost:3000/status/$JOB_ID" | tee /dev/null
  echo
  sleep 1
done
```

The worker sleeps 2 s before marking each job `completed`, so the
terminal status arrives within a few seconds.

---

## Running the tests

API unit tests use [fakeredis] so no Redis process is needed.

```bash
cd api
python -m venv .venv && source .venv/bin/activate  # .venv\Scripts\activate on Windows
pip install -r requirements-dev.txt
pytest --cov=main --cov-report=term-missing
```

5 tests, ~85% coverage on `main.py`.

[fakeredis]: https://pypi.org/project/fakeredis/

---

## CI/CD pipeline

The workflow at `.github/workflows/ci.yml` runs six stages in a
strict `needs:` chain — a failure in any stage blocks every later
stage.

| # | Stage | Triggers on | What it does |
|---|-------|-------------|--------------|
| 1 | **lint** | every push + PR | `flake8` (python), `yamllint` (compose + workflows), `node --check` (JS), `hadolint` (Dockerfiles) |
| 2 | **test** | every push + PR | `pytest --cov` in `api/`, uploads coverage & JUnit XML |
| 3 | **build** | every push + PR | starts a `registry:2` service container on `localhost:5000`, builds the three images, tags each with `<git-sha>` **and** `latest`, pushes both to the local registry, saves images as an artifact |
| 4 | **security-scan** | every push + PR | Trivy matrix scan of all three images. Fails the pipeline on any `CRITICAL`. Uploads SARIF per image to the Security tab and as an artifact |
| 5 | **integration-test** | every push + PR | loads the built images, `docker compose up -d --wait`, submits a job via `/submit`, polls `/status/{id}` until `completed` or 120 s timeout, tears down in `always()` |
| 6 | **deploy** | **push to `main` only** | scripted rolling update via `scripts/rolling-deploy.sh`: starts the new container, waits up to 60 s for `healthy`, then swaps names. On timeout or unhealthy status the new container is removed and the old one keeps running |

### Running the integration-test flow locally

```bash
docker compose -f docker-compose.yml -f docker-compose.ci.yml up -d --wait
# ...submit a job and poll as above...
docker compose -f docker-compose.yml -f docker-compose.ci.yml down -v
```

`docker-compose.ci.yml` disables the `build:` section and pulls the
named images instead, which matches what CI does after the build
stage. For local use, build the images first:

```bash
docker compose build
```

---

## Project layout

```
.
├── api/                 # FastAPI service
│   ├── Dockerfile       # multi-stage, non-root, HEALTHCHECK
│   ├── main.py          # POST /jobs, GET /jobs/{id}, GET /health
│   ├── healthcheck.py   # used by the Dockerfile HEALTHCHECK
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── conftest.py      # fakeredis fixtures
│   └── tests/test_main.py
├── worker/              # background worker
│   ├── Dockerfile
│   ├── worker.py        # BRPOP loop, heartbeat, SIGTERM handling
│   └── healthcheck.py   # checks freshness of worker:heartbeat key
├── frontend/            # Node/Express UI + proxy
│   ├── Dockerfile
│   ├── app.js
│   └── views/index.html
├── scripts/
│   └── rolling-deploy.sh
├── .github/
│   ├── workflows/ci.yml # the 6-stage pipeline
│   └── hadolint.yaml
├── docker-compose.yml   # main stack definition
├── docker-compose.ci.yml# override: image: instead of build:
├── .env.example         # copy to .env before first up
├── .yamllint
├── FIXES.md             # every starter-repo bug and its resolution
└── README.md            # this file
```

---

## Bug fixes from the starter repo

The starter ships with 18 intentional bugs spanning config, security,
resilience, and healthchecking. Every one is documented in
**[FIXES.md](./FIXES.md)** — file, line, problem, and the change that
resolved it.

---

## Troubleshooting

**`docker compose up` fails with "REDIS_PASSWORD must be set in .env"**
The compose file uses `${REDIS_PASSWORD:?...}` which intentionally
refuses to start without it. Copy `.env.example` to `.env` and set a
value.

**Port 3000 or 8000 already in use**
Override in `.env`:
```
FRONTEND_PORT=3001
API_PORT=8001
```

**Worker is `unhealthy` in `docker compose ps`**
Its healthcheck reads a `worker:heartbeat` key the worker refreshes
every `WORKER_HEARTBEAT_INTERVAL` seconds. If Redis is also unhealthy
fix that first — the worker cannot heartbeat without it.

**`.env` accidentally committed**
The `.gitignore` excludes it. If you forced it in, remove and purge:
```bash
git rm --cached .env
git commit -m "security: remove committed .env"
# If already pushed, history must also be scrubbed.
```

**CI pipeline: `security-scan` fails on `CRITICAL`**
Task policy — the pipeline blocks on any `CRITICAL` finding. Either
upgrade the affected base image / library, or mark that specific CVE
as an accepted risk in `.trivyignore` with a link to justification.

---

## Submission

- Fork is **public** at <https://github.com/ibraheembello/hng14-stage2-devops>.
- This repo is not submitted as a PR against the upstream starter.
- Every commit follows Conventional Commits
  (`<type>(<scope>): <subject>` — imperative, ≤ 50 chars, no trailing
  period). Branch names follow the same `type/short-summary` shape.
