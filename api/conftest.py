"""Pytest fixtures shared by the api test suite.

The api module instantiates a redis client at import time. These
fixtures replace that client with an in-memory fakeredis instance so
tests never require a running redis server.
"""
import fakeredis
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def fake_redis(monkeypatch):
    """Replace main.r with a fakeredis client for the duration of a test."""
    import main

    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(main, "r", fake)
    return fake


@pytest.fixture
def client(fake_redis):
    """FastAPI TestClient bound to a freshly-faked redis."""
    import main

    with TestClient(main.app) as c:
        yield c
