"""Container healthcheck for the api.

Exit 0 when GET /health returns HTTP 200, otherwise exit 1.
"""
import sys
import urllib.request

URL = "http://127.0.0.1:8000/health"


def main():
    try:
        resp = urllib.request.urlopen(URL, timeout=3)
    except Exception as exc:
        print(f"healthcheck failed: {exc}")
        sys.exit(1)
    if resp.status != 200:
        print(f"healthcheck failed: http {resp.status}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
