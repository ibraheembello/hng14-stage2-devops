#!/usr/bin/env bash
# scripts/rolling-deploy.sh
#
# Rolling-update a single service: start the new container, wait up
# to HEALTH_TIMEOUT seconds for it to become healthy, then stop the
# old one. If the new container never becomes healthy the script
# aborts, removes the new container, and leaves the old one running
# — exactly the "abort leaves old running" contract.
#
# Arguments:
#   $1  service short-name (api | worker | frontend)
#   $2  image reference to deploy (e.g. hng-api:abcd123)
#
# Environment:
#   NETWORK         docker network the containers share (default: appnet)
#   HEALTH_TIMEOUT  seconds to wait for the new container healthcheck
#                   to transition to "healthy" (default: 60)
#
# Notes:
#   * Uses a running/previous naming convention rather than a real
#     load balancer. Traffic cut-over is a single-step rename.
#   * `docker inspect --format` reads the healthcheck status that
#     the image's HEALTHCHECK directive emits.
set -euo pipefail

SERVICE="${1:?service name required (api|worker|frontend)}"
IMAGE="${2:?image reference required}"

NETWORK="${NETWORK:-appnet}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-60}"

OLD_NAME="${SERVICE}"
NEW_NAME="${SERVICE}-new"

log() { printf '[deploy %s] %s\n' "${SERVICE}" "$*"; }

cleanup_new_on_abort() {
    log "aborting — removing ${NEW_NAME}"
    docker rm -f "${NEW_NAME}" >/dev/null 2>&1 || true
    log "old container ${OLD_NAME} left running unchanged"
}

log "starting new container ${NEW_NAME} from ${IMAGE}"
docker run -d \
    --name "${NEW_NAME}" \
    --network "${NETWORK}" \
    --env-file .env \
    "${IMAGE}" >/dev/null

# Wait for healthcheck to flip from "starting" to "healthy". Abort
# on "unhealthy" or on timeout; either keeps the old container.
DEADLINE=$(( $(date +%s) + HEALTH_TIMEOUT ))
while : ; do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' "${NEW_NAME}" 2>/dev/null || echo "missing")
    log "  ${NEW_NAME} health: ${STATUS}"
    case "${STATUS}" in
        healthy)
            log "new container is healthy"
            break
            ;;
        unhealthy)
            cleanup_new_on_abort
            exit 1
            ;;
        missing)
            cleanup_new_on_abort
            exit 1
            ;;
    esac
    if [ "$(date +%s)" -ge "${DEADLINE}" ]; then
        log "timeout after ${HEALTH_TIMEOUT}s waiting for healthy"
        cleanup_new_on_abort
        exit 1
    fi
    sleep 2
done

# Cut over: stop+remove old, rename new to take its place.
if docker ps -a --format '{{.Names}}' | grep -qx "${OLD_NAME}"; then
    log "stopping old container ${OLD_NAME}"
    docker stop "${OLD_NAME}" >/dev/null
    docker rm "${OLD_NAME}" >/dev/null
fi

log "promoting ${NEW_NAME} -> ${OLD_NAME}"
docker rename "${NEW_NAME}" "${OLD_NAME}"

log "deploy complete: ${OLD_NAME} is now running ${IMAGE}"
