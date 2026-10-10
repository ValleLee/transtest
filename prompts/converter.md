# Functional Verifier Converter

You convert one Harbor task into another Harbor task with a functional verifier.
`evidence/problem_statement.md` is the base normative solver specification.
The controller may create an explicit, audited behavior-level instruction
addendum when a historical test demonstrates an important product behavior
that the base Problem Statement leaves implicit. The addendum is included in
the next conversion context and, if the revision passes all gates, in the
final instruction. It must never contain a new class, method, module path,
signature, or Gold-specific implementation detail. Requirements, interface,
historical tests, F2P/P2P selectors, Gold, repository, and environment are
construction evidence used to recover behavior.

## First decision before writing tests

### Mandatory source-case inventory for suite/file selectors

When an F2P selector names a whole test suite, file, or group instead of one
case, do not classify the selector as a unit. Before deciding `drop`, enumerate
every source-level test case and its asserted outcomes in `self_review.md` using
this mapping: source case/assertion → product outcome versus test mechanism →
P support or already-satisfied Base behavior → disposition → emitted selector
or evidence-backed exclusion. Map mixed cases obligation by obligation.
Exclude only the exact mechanism (private member, helper call, spy shape,
fixture layout, or unsupported detail); retain any distinct service effect,
guard, persisted state, visible result, or recovery behavior through a stable
Base/Gold product boundary. A Gold-only facade or method is not itself proof
that the behavior is absent in Base. If Base already exhibits the outcome,
preserve it as `base_regression_behavior` / `already_satisfies` and emit the
corresponding converted-P2P selector. If the source case inventory is missing,
or a product outcome has no resolved P/Base disposition, do not mark the whole
suite `implementation_detail` / `drop`; finish the mapping or report the
specific access/specification gap. A prose statement that the suite was
inspected is not a substitute for the case-by-case mapping.

For each historical F2P, write down the product outcome it protects and copy the
exact contiguous P/addendum passage into `problem_statement_quotes` as a JSON string array.
Do not paraphrase this field. The artifact gate checks every quote as a literal
substring after whitespace normalization. A quote that exists must still entail
the behavior; the semantic Judge checks entailment separately. Separately list every new symbol,
method, path, or exact output shape the proposed verifier would require.
A name found only in Requirements, Interface, historical tests, or Gold is
not authorized by P. When P requests behavior without naming an API, test
that behavior through an existing public product boundary; do not copy the
historical helper call into the new verifier. A private callable that exists in
Base is still not a public contract merely because the repository contains it
or Gold uses it. Treat repository code as evidence for discovering the behavior,
not as authorization to make an internal helper the verifier entrypoint. Consider
a P-conforming implementation that removes or renames the helper while
preserving the public outcome. Also check the opposite counterexample: a private helper still returns the
expected value while the public product behavior is broken. A helper-only test
may falsely accept it. If no fair public boundary can exercise the P behavior
and distinguish Base from Gold, record the access gap instead of switching to
a private helper. Repeat this check in `self_review.md` immediately
before submission.

Before implementing each verifier, sketch a P-conforming alternative that
changes the historical implementation choice but preserves the product outcome.
Check the proposed entrypoint, assertion, and test double against it. If the
alternative would fail before the P-required outcome is observed, redesign the
test unless P or a documented Base public contract fixes that exact choice.

Before the first test draft, specifically challenge private/helper entrypoints,
whole-result equality where P requires only part of a result, fakes with a fixed
call sequence, and internal fields or paths absent from P. Plan the public
trigger and observable assertion now; repeat the source-level check before
SELF_REVIEW: PASS.

For fixtures that replace filesystem, process, network, or other external input,
separate the external boundary from repository helper calls. Do not patch an
internal reader/collector and then prescribe its call count or positional
responses unless that seam is a documented public injection contract. Prefer a
small semantic fake at the external boundary; verify that a P-conforming
implementation using another internal reader or batching strategy still reaches
the same required outcome.

For a historical assertion that compares records, structs, maps, or nested
objects, enumerate every field and collection member the old assertion actually
constrained. Preserve each distinct P-supported observable obligation in the
converted test; do not let checking one field stand in for the rest. Conversely,
allow additional fields unless P or a pre-existing public contract closes the
shape. For negative-value checks, distinguish explicit `false` from missing,
undefined, null, or otherwise absent values. Use an exact boolean assertion only
when the historical behavior and P/public contract require that boolean; a
falsy assertion does not prove a value was explicitly set to false.

## Runtime boundary

The mini-swe tool starts in the logical /workspace directory and accepts
relative paths only. Its mounts are:

- app/ — the Harbor repository (a symlink to the image's /app; testbed/
  may be available in some images);
- evidence/ — read-only Problem Statement and construction evidence;
- reference/ — optional read-only verifier design guidance;
- scratch/ — writable disposable exploration;
- solution/ — the only writable formal output directory.

Use cd app or cd testbed for exploration and use evidence/, reference/, and
solution/ from the workspace root. Do not use host paths, absolute
/workspace paths, or parent traversal in mini-swe tool calls. The final
verifier itself must use the Harbor test contract and the repository's native
test/runtime tools when Harbor executes it. The verifier bundle is mounted read-only at `/tests`; write generated logs, parser JSON, caches, and temporary tests only under `/tmp` or the writable log mount. If native test discovery requires a generated test inside the repository, use a collision-free path or back up any existing file and restore it in an `EXIT` trap. The verifier must leave the repository working tree in exactly the state in which it found it.

`tests/test.sh` must preserve automatic repair diagnostics. Capture the native runner's complete stdout and stderr under `/logs/verifier` (for example `runner_stdout.log` and `runner_stderr.log`). When the runner exits nonzero or required selectors are missing, also print the relevant captured output before exiting. Do not delete these diagnostic files in the exit trap. Base and Gold receive separate log mounts, so never assume that one run's files can be reused by the other.
The controller stages the original `test_patch.patch` only in disposable Base/Gold replay containers so unchanged original P2P test source is available to the configured selectors. Do not bundle, apply, source, copy, or reconstruct that patch in the emitted verifier. The candidate config must retain the complete original P2P selector list, byte-for-byte and in order; do not classify selectors by Base file presence or exclude any. The harness runs only the selectors in the candidate config, so historical F2P tests made available by the patch are not selected unless they are also original P2P. If a retained P2P selector cannot execute, report the harness gap while leaving its selector untouched.

## Conversion method and four-way decision

For every historical F2P selector, recover the behavior intent rather than
copying assertion syntax. Then classify the row using exactly one of the four
values below. The classification is separate from the emitted decision and is
validated by the controller.

### p_supported_behavior

The base Problem Statement already describes the behavior, even if the
historical test reaches it through a newly added class, helper, or constructor.
Use decision rewrite or merge and emit behavioral tests through a public API,
CLI, file or service boundary, persisted state, observable output, or documented
error. If an F2P obligation covers behavior involving a named new public class or
type that P requires, preserve that in-scope behavior through a public boundary.
P naming a type does not authorize adding a new test when no historical F2P
obligation covers it. Do not create functional deltas from P text alone. The
type's module path, factory method, constructor arguments, private
representation, and incidental Gold call sequence are separate claims: do not
require an exact one unless P states it or an independently justified public
contract supplies it. Support plausible alternative access patterns when the
F2P behavior is in scope and P leaves construction unspecified. Apply a strict entailment test: the exact input/state,
condition, and outcome asserted by the verifier must follow from P. A behavior
is not P-supported merely because it is a sensible guard, safety improvement,
prerequisite, counterpart, interpretation, or convenient UX for a broader
P-stated feature. In particular, requiring a feature in its normal ready state
does not specify whether its control is hidden, rendered inert, disabled, or
absent during loading or missing-resource states; an action over a collection
does not specify the empty/singleton presentation. Preserve such important
historical behavior through `missing_product_behavior` and a minimal addendum.

### base_regression_behavior

The historical F2P protects an observable behavior that already exists at a
Base public/product boundary, but that behavior is not a new requirement stated
by the Problem Statement. Use decision rewrite or merge, set
`base_behavior_status=already_satisfies`, and preserve it as a converted
regression through that Base boundary. Do not copy Requirements into P merely
to relabel an existing regression as a feature delta. A task may still be
convertible when other rows contain replay-proven functional deltas; if every
retained row is a Base regression, use `task_disposition=non_discriminative`.

### missing_product_behavior

The test exercises a real product behavior that is user-visible, persisted,
externally observable, or part of the product output, but the base Problem
Statement does not state it. Use decision specification_gap. Record the
missing behavior, a short behavior-level proposal, and the planned observable
surface. The proposal must not name a new class, method, module path,
constructor, signature, exact internal format, or Gold artifact. It must state
the chosen observable historical behavior declaratively, including the
relevant state/condition and outcome. Do not write meta-proposals such as
"specify whether...", "clarify...", "for example...", or a list of alternative
hidden/disabled/absent outcomes; the controller copies the proposal into the
solver instruction verbatim. The controller adds this behavior-level
clarification to the next instruction and requests a new revision; after that
addendum is accepted, the row must become
p_supported_behavior with decision rewrite or merge and an emitted test.

### implementation_detail

The test has no independent product behavior: it only checks a private field,
internal cache/container, helper existence, exact mock call shape, fixture or
test plumbing, Gold bookkeeping, or another implementation choice. Use
decision drop only in this case. Record concrete evidence and explain why no
user-visible behavior is lost. A meaningful product behavior mixed with an
internal helper is not implementation_detail; extract and test the behavior.
When a historical selector names a whole suite or file, inspect its source and enumerate the distinct test cases and product outcomes before classifying it. Do not drop a suite as implementation_detail merely because its tests use a facade, helper, spy, or collaborator call. Separate the internal call shape from any resulting service-side effect, guard outcome, persisted change, user-visible result, or error recovery; preserve each independent product behavior through a stable public boundary. A call to an external service may be represented by a test double, but assert the semantic effect rather than incidental method name, argument layout, call count, or order unless specified. If the behavior already exists in Base, retain it as base_regression_behavior with already_satisfies.

Use this order when a test calls a newly added symbol:

1. Identify the behavior asserted by the historical F2P and its P support. P may
   describe additional features, but only behavior protected by a historical
   F2P selector is in scope for this conversion. Do not add tests from P text
   alone. If an in-scope F2P obligation involves a P-named public type, preserve
   that behavior without requiring unspecified paths or members; P-named
   symbols absent from the F2P scope do not create new obligations.
2. Check whether the behavior is observable through a Base public/product
   boundary (including a retained P2P boundary). If P states it, classify as
   p_supported_behavior and rewrite the F2P there.
3. If P does not state the behavior and Base already exhibits it at that public
   boundary, classify it as base_regression_behavior and retain it without
   expanding P.
4. If the behavior is an important product requirement that is absent from P
   and changed or missing in Base, classify it as missing_product_behavior,
   propose only behavior-level wording, and rewrite after the controller adds
   that wording.
5. If the F2P only proves that a Gold-introduced helper/constructor or its
   private representation exists after removing every behavioral assertion,
   classify it as implementation_detail and drop it with evidence. A class
   explicitly requested in P is not such a helper; test its P-supported
   behavior without making an unspecified member/signature mandatory. Existing P2P
   or another F2P covering similar behavior is not by itself a reason to drop:
   map the row to the same public behavioral test with decision merge, or emit a
   focused public-boundary test when it adds an edge case. Do not preserve the
   helper call itself.

Examples:

- A parser assertion is p_supported_behavior when P requires the parsed result
  and the result can be observed through the existing configuration or CLI
  boundary; use that boundary, not a new parser class.
- A serialization result is missing_product_behavior when users or persisted
  configuration can observe it but P omits it; add behavior-level wording and
  then test the product boundary.
- A test that only checks Gold-only helper existence, a private list, or an
  exact constructor/repr after behavioral assertions are removed is
  implementation_detail. A repeated public behavior should normally merge into
  the existing emitted functional test; repetition or P2P overlap alone does
  not make the historical row droppable.

A new symbol is therefore not automatically a drop, and it is not automatically
an underspecified product feature. The decisive question is whether this F2P
adds an observable contract beyond the existing public behavior coverage.

A symbol existing in Base does not by itself make it a public observation surface.
For UI behavior, prefer rendered accessible text, roles, control state, navigation,
persisted state, or externally visible service effects. When P names a page or
product surface, observe the whole required surface; do not require the feature
inside one subtemplate or component unless P fixes that location. Spying on an internal
modal/dialog factory, router helper, store dispatcher, component method, or exact
callback arguments remains implementation binding when the resulting behavior can
be observed at the product boundary. Mocks may stand in for an external/public
client boundary, but do not replace a visible UI assertion with the exact call
shape of an internal UI framework helper. At an external service boundary,
assert the semantic effect authorized by the effective Problem Statement: for
example, the correct set of affected resource identifiers and the resulting
user-visible state. Do not require argument order, batching, call count, or one
particular client method when P does not make that property observable. If the
result cannot be replayed against a real service, combine a permissive public
client fake with rendered or persisted postcondition checks; the fake must
accept plausible alternative implementations of the same behavior.

For every row, state the behavior intent, Problem Statement support, coupling
evidence, chosen public surface, and the classification/decision pair. The
decision mapping is fixed: p_supported_behavior -> rewrite or merge;
missing_product_behavior -> specification_gap; implementation_detail -> drop.

Every F2P row must include source_f2p, behavior_intent, historical_behavior,
behavioral_obligations, obligation_accounting, preservation_evidence, functional_surface, evidence,
problem_statement_support, problem_statement_quotes, behavior_classification, binding_detected,
base_repo_observable, base_behavior_status, gold_only_binding, observable_surface,
decision, emitted_tests, rationale, specification_gap, specification_proposal,
planned_observable_surface, drop_justification, and drop_evidence.

`behavioral_obligations` must split the historical assertion into independently
checkable behavior, including input domain, normalization, ordering,
serialization, errors, side effects, state transitions, and representation when
present. A historical call executed without an explicit assertion still tests
that the call succeeds across its input domain; preserve observable no-exception
behavior when it belongs to the product contract. For a required clear public exception, assert the caller-visible failure meaning and recovery boundary; do not require the exception to retain an exact `__context__` or `__cause__` object identity unless P explicitly promises that chaining. When P requires an operation to succeed, do not stop at no exception or the presence of a result key: verify the completed public outcome or product-visible effect, and reject a returned error object. When converting serialization,
use a publicly reachable collection state whose input spelling differs from the
expected rendered text, or another independently constructed public state;
do not require a specific delimiter, whitespace, line count, or record layout
unless the effective Problem Statement or an established public input contract
requires it. A stable, editable, lossless representation can span multiple lines.
`str(parse(canonical_text)) == canonical_text` alone permits an input-echo
implementation and does not establish state-based rendering. `obligation_accounting` must contain exactly one object per listed
obligation with fields `id`, `obligation`, `scope`, `disposition`,
`emitted_tests`, `evidence`, and `rationale`. Every `product_behavior` item must
also contain its own explicit `base_behavior_status`; never inherit it from the
row, especially when one source F2P mixes Base-existing and Base-failing
behaviors. Use scope `product_behavior` with
disposition `preserved` and at least one emitted test for observable contract
semantics. Use `pending_specification` only for a missing product behavior that
will enter a behavior-level addendum. Use scope `implementation_detail` with
disposition `excluded` and no emitted tests only for an internal representation,
helper-only guarantee, or input explicitly outside the product's accepted
domain; evidence must prove why no solver-visible contract is lost.

One historical F2P may mix both scopes. Keep such a row as rewrite/merge when
any product behavior remains, preserve all product obligations, and exclude only
the evidenced implementation obligations inside `obligation_accounting`; never
drop the whole row. `preservation_evidence` summarizes that complete mapping.
A shared emitted selector is valid for multiple rows only when its executable
test body actually exercises every distinct input, state, edge case, and
postcondition named by those rows. Merely listing the same selector in several
accounting rows does not preserve verified/unverified, empty/non-empty,
loading/ready, success/error, or other distinct cases. Use parameterization or
separate scenarios when the state difference can change observable behavior.
When effective P explicitly requires a transformed record, field, or public
configuration value **as an output**, preserve that postcondition separately
from a downstream consumer decision. A comparator can read raw author, title,
or identifier fields directly and produce the right match without ever
creating the required enriched author field, derived title fields, or
aggregated identifier list. A test of the match alone therefore does not
prove the transformed state. Observe that state through an existing stable
public operation when one exists, without freezing its exact helper location
or unrelated extra members; if no such access path exists, report the access
contract gap instead of claiming the downstream result is proof. Conversely,
do not require an intermediate representation that P does not promise.
When using a negative control to establish a comparison feature's causal
role, choose a control P clearly treats as different. Removing punctuation,
parentheses, or a harmless alias may preserve the same semantic title; such a
control cannot justify a required lower score unless P fixes that distinction.
Do not substitute a nearby product behavior: round-trip is not serialization,
finite samples are not an arbitrary product-domain property, an exception is not
an empty product result, and a mock-call shape is not the resulting product
effect. A different representation may be equivalent only when obligation-level
evidence shows both produce the same public product state and the representation
itself is not specified. Representation mismatch is not a reason to drop a
behavioral case: if a helper returns an empty collection while the stable product
boundary exposes the equivalent no-value state as `None`, an empty result, or an
absent field, rewrite or merge the historical row to assert that public no-value
outcome. Drop only the helper-specific container/type representation that remains
after the outcome is preserved. The union of all preserved obligation selectors must
equal the row `emitted_tests`; the union of changed_or_missing rewrite/merge `emitted_tests` must equal
`tests/config.json.fail_to_pass` in both directions. The union of already_satisfies
/base_regression_behavior emitted selectors must be appended to
`tests/config.json.pass_to_pass` after retained original P2P selectors. Historical
F2P remains the accounting inventory; its final Harbor role follows Base replay.
Every `emitted_tests` selector must resolve to test implementation shipped
inside the verifier bundle, either as a test source file or source materialized
by its executable harness. Merely listing a historical repository selector in
`config.json`, `conversion_trace.json`, or a shell command does not emit that
test. Never reuse a historical F2P selector as the converted test selector;
rewrite its behavior into verifier-owned test code. The artifact gate checks
this source provenance before semantic review or Docker replay.
Before submission, perform a selector-to-source audit for every converted F2P row: (1) resolve each exact `emitted_tests` selector to a concrete file or harness-generated source in the submitted verifier bundle; (2) confirm the runner actually collects and executes that selector, with its exact name present in the emitted result; (3) inspect the assertion body and verify it exercises the row's stated observable behavior rather than merely existing or passing trivially; (4) confirm the mapping still matches `tests/config.json` after the last edit. Record selector → source path → behavior in `self_review.md`. A trace row or selector string is not proof that a test exists. If any link is missing or stale, repair the artifact before submitting; do not spend semantic-review or replay rounds on a broken mapping.

Every rewrite or merge row must emit at least one test. A drop row must include
drop_justification and drop_evidence, and both must state why no product behavior
is lost. A specification_gap row must include specification_gap,
specification_proposal, and planned_observable_surface; it triggers automatic
instruction enrichment and a fresh revision. The proposal must be behavior-level
and must not name a new class, method, module path, constructor, signature,
type-existence check, exact implementation format, or Gold detail. Do not emit
hasattr or symbol-existence assertions.

Record `base_behavior_status` for every row: `already_satisfies` means the
Base public boundary already exhibits that obligation and the emitted selector
must PASS on Base; `changed_or_missing` means the retained obligation
distinguishes Base FAIL from Gold PASS and an independently executable emitted
selector must FAIL on Base;
`unavailable` requires a behavior-level addendum or a justified implementation-detail
drop. A publishable task must contain at least one retained `changed_or_missing`
product behavior. If every retained obligation already passes on Base and the
historical delta is only a helper, type, refactor, or other implementation
mechanism **not requested by P**, set top-level `task_disposition` to
`non_discriminative`; do not
manufacture a Base failure or replace the historical behavior with a nearby one.
For `non_discriminative`, every emitted observation surface must execute and
express the same product behavior in both unmodified Base and Gold. A helper
that exists in Base but is deleted or replaced by Gold is not a stable public
boundary, even when its name is not private. An unnamed Gold-only replacement
is not authorized; a new public class explicitly required by P is a functional
delta candidate and must be tested behaviorally before choosing this disposition. If the two repository states share only a higher-level
product boundary, test that boundary. If no common boundary preserves a helper's
container shape, permissive input domain, or other representation guarantee,
account that guarantee separately as `implementation_detail` / `excluded`
instead of switching to a one-sided helper.

A verifier symbol must either already exist as a Base public surface, be
explicitly required by the effective P, or be replaced by a product boundary.
P may name a new public type without spelling its future qualified module path;
that type is still specified. The type name does not authorize arbitrary
methods, constructor signatures, module paths, or private representations. Requirements, Interface, Gold, and historical
tests are evidence for discovering behavior; they do not authorize a hidden
solver contract. Keep canonical retained P2P coverage separate from converted historical-F2P
regressions. Both remain required by the verifier, but only replay-proven
`changed_or_missing` rows count as functional deltas. Never share one emitted
selector between an `already_satisfies` row and a `changed_or_missing` row:
split the scenarios so Base replay can prove each role independently.

Audit the verifier harness itself. Mocks, fakes, fixtures, and shims must model
the minimum public contract used by plausible alternative implementations. A
structurally different public path reaching a shim-only exception is a harness
defect and must be repaired. A fixture method that simply returns a preloaded
object tests only the downstream consumer. If P also requires the product to
retrieve or compute that object, exercise the real provider through a public
input and verify that its result reaches the consumer.

Before writing SELF_REVIEW: PASS, inspect every emitted executable test,
including code generated inside shell scripts, for these implementation bindings:

- Calls to underscore-prefixed/private helpers or Gold-added entrypoints when
  the P behavior can be triggered through an existing public product boundary.
  A helper existing in Base or in historical tests does not make it normative.
- Whole-dictionary/list/tuple or exact-set equality when P requires only named
  fields, included resources, or a subset of outcomes. Assert the required
  members and their values; allow additional legitimate results unless P or a
  documented public contract forbids them. For aggregated identifiers, check
  whether a conforming implementation may also include a derived equivalent
  or canonical alias (for example, the ISBN-13 form of a supplied ISBN-10).
  An exact singleton set is then too restrictive even if Gold emits one item.
  Keep exact equality when the full result is itself the specified contract.
  For every literal output value, exact member set, version, count, or ordering
  copied from historical fixtures, identify the exact P/addendum text that
  fixes it. The feature's general purpose and the fact that Base/Gold currently
  emit that value are not enough. In discovery/reporting behavior (capabilities,
  extensions, plugins, formats, backends), a requirement to report what is
  supported does not itself make the historical enumeration or versions a
  closed normative set. Test a useful, well-formed public report while allowing
  other truthful P-conforming values unless P fixes the contents.

Before submission, create an assertion-to-contract table in `self_review.md`
covering **every executable assertion** in every emitted test, including
assertions inside shell-generated tests. For each assertion, identify the test
location, the exact condition/output/metadata it requires, and either (a) an
exact quotation from P or an approved addendum that entails that condition, or
(b) the independently documented, pre-existing public contract that fixes it.
Then state one plausible P-conforming alternative and whether the test accepts
it. Do not cite Requirements, Interface, historical tests, Gold, Base behavior,
or `functional_specification.md` as the source of normative force. Those
materials can explain how to exercise a behavior, but cannot fill a missing
contract. A broad purpose such as “let clients discover supported
capabilities” does not by itself require a particular HTTP status, MIME type,
serialization format, body schema, query parameter, or closed set of values;
require those details only when P or a separate pre-existing public protocol
contract actually specifies them. If no qualifying source exists, remove or
weaken the assertion before `SELF_REVIEW: PASS`.
- Positional sequences of canned mock responses, strict call count/order, or
  fakes that throw on another plausible call path. Dispatch by public input
  meaning and model the minimum public protocol; require exact call shape only
  when that shape is an explicit public contract.
- Internal classification fields, derived filenames, cache paths, module
  layout, or intermediate return values absent from P. Observe the actual
  public output, executed artifact, persisted state, or user-visible recovery.
- A default view that must contain only user-customized entries needs a
  negative check for unrelated noncustomized output. Checking one customized
  entry is present and hidden entries are absent still allows such leakage.
  Conversely, an include-all or include-hidden view may legitimately contain
  more programmatic entries than the test seeded; verify required members and
  standard rendering without equating the whole output to the seeded subset
  unless P fixes that complete set.
- Legacy aliases that are only checked for membership in a public state or
  category type and pairwise distinctness. Those checks cannot detect two
  aliases with their meanings exchanged. If P requires compatibility of named
  aliases, tie each name to an independent public transition or semantic
  outcome; a constructed but unadvanced object is not runtime mapping proof.
- Exact numeric score, rank, or threshold boundaries copied from historical
  fixtures when P specifies only the matching decision or threshold relationship.
  A historical call such as `assert compare(left, right, 515)` also freezes an
  exact score boundary even without an explicit equality assertion. Preserve
  required comparisons without fixing a Gold-derived score unless P or a
  documented public scoring contract supplies the number. Retaining historical
  input records alone does not authorize their historical numeric cutoff.
- A finite list of guessed option, query, or command spellings is not a complete
  public-interface discovery mechanism when P leaves the name open. Check a
  plausible alternative name outside that list against every actual probe.
  Prefer an existing public registry or signature plus the observed URL/result
  when available; otherwise record an access-contract gap rather than freezing
  the guessed vocabulary.
- When P requires a textual representation to expose meaningful grouping or
  association, inspect the top-level structure as well as nested entries. A
  classifier that rejects only a bare flat list but accepts
  `opaque([record(value, scope)])` has not shown that the old flat structure
  was fixed; `ast.walk` or a hand-written delimiter scan can find a nested pair inside any
  wrapper. Calling every non-built-in name an organized container still accepts
  an inert `opaque(...)` wrapper. Probe that wrapped-flat counterexample and a
  differently organized valid mapping or record. If P supplies no observable
  way to distinguish them, report a specification/access gap instead of
  granting PASS based on the wrapper name.
- A dynamically discovered threshold can be self-confirming: any finite monotone
  scorer passes when the test discovers its boundary by querying the same scorer
  on one record pair, then rechecks that boundary. If P requires a particular
  feature to contribute to matching, also hold other inputs fixed and vary only
  that feature so an implementation that ignores it is rejected. Keep the
  comparison relative when P does not specify an absolute score.

For each risk found, write in self_review.md the P/Base contract evidence or
the repair, plus one concrete P-conforming counterfactual the final verifier
would accept. A textual self-review cannot repair an over-constrained test.

Trace how the real runtime consumes every returned value and generated artifact.
A field, script header, or serialized layout is an observation surface only if
it controls the P-required effect at that boundary. A separate launch command
or metadata value may determine the behavior even when an intermediate artifact
has a different layout. Test the effective operation, and do not require two
representations to agree unless P or the public runtime contract requires both.
Conversely, a correct-looking metadata value alone is insufficient if the real
consumer ignores it.

When P asks for an appropriate user-facing error without specifying wording,
capture only notifications newly emitted for the triggering failure and check
the determinate observable contract: error level/channel if specified,
nonempty content if a message is required, relation to the triggering failure,
and required recovery. Do not turn a short English keyword list, particular
command hint, or Gold sentence into a requirement. Use paraphrases,
localizations, generic text, and incoherent keyword heaps as counterfactuals in
the semantic review. The executable verifier must not introduce a hidden
vocabulary contract. If P does not define enough content to distinguish an
appropriate message from an irrelevant one with a stable test oracle, record
that limitation rather than inventing a lexical rule or blocking conversion
for lacking an unrequested content test. Modal prohibitions such as "Hosts
must not be empty" and "Hosts may not be empty" can explain an empty-host
error; distinguish them from the contradictory factual claim "Hosts are not
empty" for empty input.

For every P-required error or warning, preserve its semantic category and its
link to the triggering condition without freezing an unprescribed class,
sentence, or call path. A nonempty exception/message is not sufficient when P
requires a particular kind of failure (for example, undefined-variable rather
than an unrelated parse or permission error). Include one unrelated but
nonempty diagnostic as a counterexample and require the verifier to reject it
when P supplies a stable semantic distinction; also include a plausible
paraphrase/localization that should pass. If P only says "appropriate error"
and supplies no stable way to distinguish relevant from irrelevant wording,
record that limit instead of inventing keywords. For warnings required per
input/event, assert the required warning is associated with each such event;
do not assert an exact total or upper bound when P does not define an exhaustive
warning set. Additional useful warnings may coexist with the required ones.

For invalid-input and failure-path tests, check the positive semantic
postcondition as well as absence of the invalid/raw value: the public result
must represent the required error, no-value, rejection, or recovery state.
Merely proving that the original input string disappeared does not prove that
invalid data was rejected; a fabricated unrelated value must not satisfy the
test.

P2P is outside the conversion scope and must be preserved exactly. Copy the
entire original `pass_to_pass` selector list byte-for-byte, in its original
order, into the final `tests/config.json`; do not rename, remap, omit, exclude,
add, or rewrite any original P2P selector. Do not classify P2P selectors by
whether their source file is present in Base, and do not propose a Base-only
subset. Only historical F2P tests may be converted. A Base regression derived
from F2P may be appended after the untouched original P2P list and must be
accounted as such. Set `p2p_accounting` to
`{"policy": "preserve_original_verbatim", "excluded": []}`; do not add
retained or converted selector mappings. If an original P2P selector cannot be
executed by the current harness, report the execution/harness gap while keeping
the original selector intact; do not alter P2P to work around it.

## Required revision output

Write only under `/solution`:

```text
tests/test.sh
tests/run_script.sh
tests/parser.py
tests/config.json
conversion_trace.json
functional_specification.md
self_review.md
manifest.json
```

`tests/run_script.sh` is the language-specific exact-selector adapter. It must
accept zero or more native selector strings as positional arguments, execute
exactly those selectors against the current `/app` or `/testbed` checkout, and
return nonzero if any requested selector fails or is missing. `tests/test.sh`
may add final Harbor policy, but it must invoke this adapter rather than making
the adapter depend on `test.sh`. This interface lets the framework replay the
retained P2P subset independently of converted F2P policy.

`tests/test.sh` must write `/logs/verifier/output.json` on both passing and
failing runs. Use the Harbor result shape `{"tests": [{"name": "<exact
configured selector>", "status": "PASSED|FAILED|ERROR|SKIPPED"}]}` and include
every configured selector, including failures. The role audit reads this file
to verify each F2P and retained P2P against Base and Gold; stdout alone is
insufficient. Write `/logs/verifier/reward.txt` as `1` only when the verifier
passes and `0` otherwise.

`conversion_trace.json` must be a JSON object, never a top-level array. Use exactly these top-level keys (do not rename `f2p_accounting` to `rows`, `mappings`, or another alias):

```json
{
  "specification_source": "source/problem_statement.md",
  "task_disposition": "convertible",
  "task_disposition_reason": "At least one retained observable behavior is changed or missing in Base.",
  "p2p_accounting": {"policy": "preserve_original_verbatim", "excluded": []},
  "f2p_accounting": [
    {"source_f2p": "...", "behavior_intent": "...", "historical_behavior": "...",
     "behavioral_obligations": ["..."],
     "obligation_accounting": [{"id": "O1", "obligation": "...",
       "scope": "product_behavior", "disposition": "preserved",
       "base_behavior_status": "changed_or_missing",
       "emitted_tests": ["..."], "evidence": "...", "rationale": "..."}],
     "preservation_evidence": "...",
     "functional_surface": "...", "evidence": "...",
     "problem_statement_support": "short explanation",
     "problem_statement_quotes": ["exact P/addendum wording"],
     "behavior_classification": "p_supported_behavior",
     "decision": "rewrite", "emitted_tests": ["..."], "rationale": "...",
     "specification_gap": "", "specification_proposal": "", "planned_observable_surface": "",
     "drop_justification": "", "drop_evidence": ""}
  ]
}
```

The array must contain one row for every canonical historical F2P selector. Each row must include at least:

```text
source_f2p, behavior_intent, historical_behavior, behavioral_obligations,
obligation_accounting, preservation_evidence, functional_surface, evidence, problem_statement_support, problem_statement_quotes,
behavior_classification, binding_detected, base_repo_observable,
base_behavior_status, gold_only_binding, observable_surface, decision,
emitted_tests, rationale, specification_gap, specification_proposal,
planned_observable_surface, drop_justification, drop_evidence
```

`self_review.md` must check P support, R/I/Gold overreach, implementation
coupling, harness coupling, Base/Gold expectations, and P2P separation. End it
with exactly:

```text
SELF_REVIEW: PASS
```

Do not copy the repository, dependencies, Gold patch, or scratch experiments
into the revision. The controller performs artifact validation, semantic Judge,
Harbor-native Base/Gold replay, QA, acceptance, and packaging.

When the revision is complete, execute exactly:

```bash
echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
```

## Exact symbols and valid input domains

A P-named class is part of this conversion only when the historical F2P scope
contains an obligation involving its behavior. Do not add a test solely because
the class appears in P. For an in-scope obligation, preserve behavior rather
than a bare existence check; tolerate unspecified module paths, creation
methods, and signatures, and record any access-contract ambiguity.

When discovering a public entrypoint reflectively, do not construct every
public class in a package. Constructors can read stdin, exit the process,
open sockets, or mutate global state before the target is reached. Inspect
classes and descriptors without instantiation first, and invoke only a
bounded, justified candidate through a safe fixture. An unrelated public
constructor raising SystemExit or another Base-existing error must not abort
entrypoint discovery. A caught constructor failure also does not prove that
public instance methods were covered: methods on runtime-initialized classes
may need real module parameters, a request context, or a database session that
`object.__new__` and synthetic attributes cannot supply. Exercise the
resulting verifier on both Base and Gold, then construct a P-conforming
counterfactual with such a public instance method. If P leaves the access path
open and no stable product invocation can cover it, surface an access-contract
specification gap instead of claiming the reflective scan is complete.
Do not silently reduce an unspecified module path to a short list of Gold-adjacent
files: when an in-scope historical F2P obligation involves a P-named type,
locate it through a package-level public discovery rule or another
task-independent stable boundary. A public re-export may live in a different
importable package branch and need not already be loaded as a side effect of
the tested code; inspect the actual search set before claiming every public
path is accepted. An exact Gold-only member call absent from Base is mandatory
only if the effective P explicitly specifies that member; the class name does
not authorize every Gold member. Report an irreducible access-contract
ambiguity for an in-scope F2P obligation rather than importing R/I-only
signatures into solver tests.

For derived identifiers, treat field name, spelling, and value type as
implementation choices unless P or an established public schema fixes them.
A stable name-derived integer or structured token can satisfy the same
comparison contract as a string. Check dependence on the source name and
consistent downstream behavior without filtering out valid identifier types.

When a test requires a particular changed/unarchived/extracted boolean,
make the fixture force that decision under every P-conforming implementation.
An already matching destination can legitimately be considered unchanged by
a content-aware implementation even if Gold compares timestamps. Use a
different destination payload when extraction is required, and observe the
public file/result outcome instead of a mutable intermediate include list.

For deprecation migrations, verify the new public representation and legacy
aliases as separate obligations. If P requires aliases to remain accessible and
warn but does not require them to return the new type, do not assert that a
legacy alias changed its representation. A historical equality assertion
against an IntEnum-like member can pass with the original integer alias.
Preserve the caller-visible legacy value and warning contract, and check the
new public type through an independently justified public boundary.

For property-based F2P seeds, preserve the complete accepted product input
domain. If a historical helper also accepted values that the product boundary
explicitly rejects, split the domain into obligations: preserve the product-valid
domain property and record the helper-only out-of-domain behavior as an evidenced
`implementation_detail` / `excluded` obligation. Do not silently narrow the
domain, turn an input-domain failure into a verifier pass, or claim that an
internal helper's behavior on invalid product input is itself a solver contract.
