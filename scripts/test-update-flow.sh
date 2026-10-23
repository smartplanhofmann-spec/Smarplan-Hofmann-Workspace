#!/usr/bin/env bash
# Runs the actual operator shell against synthetic services in a disposable FS.
set -euo pipefail
smartplan_repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH \
  docker --host=unix:///var/run/docker.sock run --rm --network none \
  --mount "type=bind,src=$smartplan_repo,dst=/source,readonly" \
  -e SMARTPLAN_UPDATE_FLOW_CONTAINER=1 \
  python:3.12-slim \
  /bin/bash -c 'touch /SMARTPLAN_UPDATE_FLOW_FIXTURE; exec /usr/local/bin/python3 /source/tests/update_flow/test_update_flow.py'
