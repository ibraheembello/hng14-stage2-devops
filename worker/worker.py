import os
import signal
import sys
import time

import redis

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD") or None
HEARTBEAT_INTERVAL = int(os.environ.get("WORKER_HEARTBEAT_INTERVAL", "10"))
HEARTBEAT_KEY = "worker:heartbeat"

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
)

_shutdown = False


def _handle_shutdown(signum, _frame):
    global _shutdown
    print(
        f"Received signal {signum}, finishing current job then stopping",
        flush=True,
    )
    _shutdown = True


signal.signal(signal.SIGTERM, _handle_shutdown)
signal.signal(signal.SIGINT, _handle_shutdown)


def write_heartbeat():
    r.set(HEARTBEAT_KEY, int(time.time()), ex=HEARTBEAT_INTERVAL * 3)


def process_job(job_id):
    print(f"Processing job {job_id}", flush=True)
    time.sleep(2)
    r.hset(f"job:{job_id}", "status", "completed")
    print(f"Done: {job_id}", flush=True)


def main():
    print(
        f"Worker starting (heartbeat every ~{HEARTBEAT_INTERVAL}s)",
        flush=True,
    )
    write_heartbeat()
    while not _shutdown:
        write_heartbeat()
        job = r.brpop("job", timeout=HEARTBEAT_INTERVAL)
        if job:
            _, job_id = job
            process_job(job_id)
    print("Worker stopped cleanly", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    main()
