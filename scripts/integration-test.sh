#!/usr/bin/env bash
# scripts/integration-test.sh
#
# End-to-end smoke test. Assumes the full stack is already running
# (e.g. the CI workflow has just executed `docker compose up -d
# --wait`) and exercises the happy path through the frontend:
#
#   POST /submit -> api enqueues job in redis -> worker processes
#   it -> GET /status/{id} returns status=completed.
#
# The script exits 0 only if the job reaches `completed` within
# INTEGRATION_TIMEOUT seconds. Any other outcome (terminal error
# status, timeout, HTTP failure, missing job id) exits non-zero so
# the CI stage fails and later stages are skipped.
#
# Environment:
#   FRONTEND_URL         base URL of the frontend (default http://localhost:3000)
#   INTEGRATION_TIMEOUT  seconds to wait for the job to reach a
#                        terminal state (default 120)
#   POLL_INTERVAL        seconds between status checks (default 2)
set -euo pipefail

FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
INTEGRATION_TIMEOUT="${INTEGRATION_TIMEOUT:-120}"
POLL_INTERVAL="${POLL_INTERVAL:-2}"

log() { printf '[integration-test] %s\n' "$*"; }

log "submitting job to ${FRONTEND_URL}/submit"
JOB_ID=$(curl -fsS -X POST "${FRONTEND_URL}/submit" | jq -r .job_id)
log "received job_id=${JOB_ID}"

if [ -z "${JOB_ID}" ] || [ "${JOB_ID}" = "null" ]; then
    log "ERROR: frontend did not return a job_id"
    exit 1
fi

log "polling ${FRONTEND_URL}/status/${JOB_ID} every ${POLL_INTERVAL}s (timeout ${INTEGRATION_TIMEOUT}s)"
DEADLINE=$(( $(date +%s) + INTEGRATION_TIMEOUT ))

while : ; do
    if [ "$(date +%s)" -ge "${DEADLINE}" ]; then
        log "ERROR: timeout after ${INTEGRATION_TIMEOUT}s — job never completed"
        exit 1
    fi

    STATUS=$(curl -fsS "${FRONTEND_URL}/status/${JOB_ID}" | jq -r .status)
    log "  status=${STATUS}"

    case "${STATUS}" in
        completed)
            log "SUCCESS: job completed end-to-end"
            exit 0
            ;;
        failed|error)
            log "ERROR: job ended in terminal error state '${STATUS}'"
            exit 1
            ;;
    esac

    sleep "${POLL_INTERVAL}"
done
