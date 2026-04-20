"""Unit tests for the api service.

Redis is mocked via fakeredis (see conftest.py); no external services
are touched. These tests exercise every endpoint and verify the
expected redis state transitions.
"""
import uuid


def test_create_job_returns_uuid_job_id(client):
    response = client.post("/jobs")
    assert response.status_code == 200

    body = response.json()
    assert "job_id" in body

    parsed = uuid.UUID(body["job_id"])
    assert parsed.version == 4


def test_create_job_enqueues_and_marks_status_queued(client, fake_redis):
    response = client.post("/jobs")
    job_id = response.json()["job_id"]

    # The worker pops from this list - the job should be on it.
    queue_contents = fake_redis.lrange("job", 0, -1)
    assert job_id in queue_contents

    # And the per-job status hash should have been initialised.
    assert fake_redis.hget(f"job:{job_id}", "status") == "queued"


def test_get_job_returns_status_for_existing_job(client, fake_redis):
    job_id = "11111111-2222-3333-4444-555555555555"
    fake_redis.hset(f"job:{job_id}", "status", "queued")

    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json() == {"job_id": job_id, "status": "queued"}


def test_get_job_returns_404_for_missing_job(client):
    missing_id = "00000000-0000-0000-0000-000000000000"

    response = client.get(f"/jobs/{missing_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "job not found"


def test_health_returns_ok_when_redis_reachable(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
