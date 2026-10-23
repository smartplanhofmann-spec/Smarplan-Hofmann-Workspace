#!/usr/bin/env bash
# Only code/synthetic fixtures enter the container; evaluation has no network.
set -euo pipefail
smartplan_worker_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
smartplan_test_image="${SMARTPLAN_IMPORT_TEST_IMAGE:-smartplan-plan-import-tests:local}"
smartplan_docker=(env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH
  docker --host=unix:///var/run/docker.sock)
smartplan_build_args=(--file "$smartplan_worker_source/Dockerfile.test" --tag "$smartplan_test_image"
  --build-arg "SMARTPLAN_OCR_DEU=${SMARTPLAN_OCR_DEU:-0}")

"${smartplan_docker[@]}" info --format '{{.ServerVersion}}' >/dev/null
if [[ -r /etc/ssl/certs/ca-certificates.crt ]]; then
  smartplan_build_args+=(--secret id=system_ca,src=/etc/ssl/certs/ca-certificates.crt)
fi
if [[ -n "${CODEX_PROXY_CERT:-}" ]]; then
  [[ -r "$CODEX_PROXY_CERT" ]] || { echo 'Configured proxy CA is not readable.' >&2; exit 1; }
  smartplan_build_args+=(--secret "id=proxy_ca,src=$CODEX_PROXY_CERT")
fi
"${smartplan_docker[@]}" build "${smartplan_build_args[@]}" "$smartplan_worker_source"
# Executable synthetic OCR fixtures live in private temporary directories.
"${smartplan_docker[@]}" run --rm --network none --read-only \
  --user "$(id -u):$(id -g)" --cap-drop ALL --security-opt no-new-privileges \
  --memory 1536m --cpus 2 --pids-limit 128 \
  --tmpfs /tmp:rw,exec,nosuid,nodev,size=256m,mode=1777 \
  --mount "type=bind,src=$smartplan_worker_source,dst=/source/backend/plan_import,readonly" \
  "$smartplan_test_image"
