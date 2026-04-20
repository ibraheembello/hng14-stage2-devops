"""Container healthcheck: verify the worker heartbeat in Redis is fresh.

The Dockerfile's HEALTHCHECK runs this script. Exit 0 = healthy.
"""
import os
import sys
import time

import redis

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD") or None
HEARTBEAT_INTERVAL = int(os.environ.get("WORKER_HEARTBEAT_INTERVAL", "10"))
MAX_AGE_SECONDS = HEARTBEAT_INTERVAL * 3
HEARTBEAT_KEY = "worker:heartbeat"


def main():
    r = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
        socket_timeout=2,
    )
    try:
        raw = r.get(HEARTBEAT_KEY)
    except Exception as exc:
        print(f"healthcheck: redis unreachable: {exc}")
        sys.exit(1)
    if raw is None:
        print("healthcheck: no heartbeat recorded yet")
        sys.exit(1)
    age = int(time.time()) - int(raw)
    if age > MAX_AGE_SECONDS:
        print(f"healthcheck: heartbeat stale ({age}s old)")
        sys.exit(1)
    print(f"healthcheck: ok (heartbeat age {age}s)")
    sys.exit(0)


if __name__ == "__main__":
    main()
