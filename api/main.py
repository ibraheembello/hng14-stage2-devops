import os
import time
import uuid

import redis
from fastapi import FastAPI, HTTPException

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD") or None

app = FastAPI()

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
)


@app.on_event("startup")
def _wait_for_redis():
    max_attempts = 10
    for attempt in range(1, max_attempts + 1):
        try:
            r.ping()
            print(
                f"[startup] connected to redis at {REDIS_HOST}:{REDIS_PORT}",
                flush=True,
            )
            return
        except redis.ConnectionError as exc:
            print(
                f"[startup] redis not ready ({attempt}/{max_attempts}): {exc}",
                flush=True,
            )
            time.sleep(2)
    raise RuntimeError("Redis unreachable after retries")


@app.get("/health")
def health():
    try:
        r.ping()
    except redis.RedisError as exc:
        raise HTTPException(
            status_code=503, detail=f"redis unreachable: {exc}"
        )
    return {"status": "ok"}


@app.post("/jobs")
def create_job():
    job_id = str(uuid.uuid4())
    r.lpush("job", job_id)
    r.hset(f"job:{job_id}", "status", "queued")
    return {"job_id": job_id}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    status = r.hget(f"job:{job_id}", "status")
    if not status:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": job_id, "status": status}
