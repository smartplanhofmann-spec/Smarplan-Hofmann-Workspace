#!/usr/bin/env bash
set -euo pipefail

# Use the existing isolated checkout. Do not create a Git worktree.
smartplan_repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
smartplan_flutter="${SMARTPLAN_FLUTTER_ROOT:-/workspace/toolchains/flutter}"
export CI=true
export FLUTTER_SUPPRESS_ANALYTICS=true
export XDG_CONFIG_HOME=/workspace/toolchains/config
export ANALYZER_STATE_LOCATION_OVERRIDE=/workspace/toolchains/analyzer-cache
export PUB_CACHE=/workspace/toolchains/pub-cache
export PIP_NO_CACHE_DIR=1

cd "$smartplan_repo"
python -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
if [ ! -x backend/.venv/bin/python ]; then
  python -m venv backend/.venv
fi
backend/.venv/bin/python -m pip install --disable-pip-version-check --no-cache-dir -r backend/requirements.lock
backend/.venv/bin/python -m pip check
backend/.venv/bin/python -m unittest discover -s backend -v

if [ ! -d "$smartplan_flutter" ]; then
  mkdir -p "$(dirname -- "$smartplan_flutter")"
  git clone --depth 1 --branch 3.47.7 https://github.com/flutter/flutter.git "$smartplan_flutter"
fi
if [ "$(git -C "$smartplan_flutter" rev-parse HEAD)" != abaf9c523780a608bd46686fd5e53740a07077f8 ]; then
  echo 'Flutter SDK differs from the tested 3.47.7 revision; inspect it instead of resetting existing files.' >&2
  exit 1
fi
"$smartplan_flutter/bin/flutter" --version
cd app
"$smartplan_flutter/bin/flutter" pub get --enforce-lockfile
"$smartplan_flutter/bin/flutter" analyze
"$smartplan_flutter/bin/flutter" test --reporter expanded
