"""Focused, risk-triggered counterfactual review of emitted verifier assertions.

The broad Semantic Judge can overlook a small implementation binding in a long
conversion trace. This second read receives only executable source files that
contain generic static risk signals and must account for every signal before a
PASS can be accepted. It is advisory about *where* to review; P decides whether
the assertion is justified.
"""
from __future__ import annotations

import re
from typing import Any, Callable


FOCUSED_KINDS = {
    "exact_observation_count", "direct_child_file_scan",
    "all_observations_required", "intermediate_value_exactness",
    "whole_result_exactness", "default_output_subset", "exact_numeric_boundary", "self_calibrated_threshold", "finite_option_vocabulary", "fixed_serialization_fixture", "serialization_shape_assertion", "subcomponent_location_binding", "reflective_entrypoint_scope", "public_type_origin_binding", "private_entrypoint_call", "legacy_alias_representation", "permutation_invariant_mapping", "representation_wrapper_acceptance", "decision_branch_binding", "derived_identifier_type_binding", "fixture_extension_hook", "fixture_preloaded_provider", "message_lexical_gate", "message_nonempty_only", "multiple_null_constructor_dependencies", "system_path_mutation", "unconditional_downstream_side_effect",
}

SYSTEM = """You are a focused adversarial audit of a functional verifier, independent of its Converter self-review and the broad Semantic Judge. Use only the effective Problem Statement as the solver contract. The risk signals locate executable assertions; they are not automatic defects.

For EACH (file, kind) signal, inspect the executable code and calculate two counterfactuals where relevant:
- exact_observation_count: an extra successful invocation/item while the required outcome still holds;
- direct_child_file_scan: the same valid persisted data under a nested layout;
- all_observations_required: one valid observation plus an additional irrelevant/empty observation; for a fixed file list, consider a P-conforming refactor in which one listed file no longer needs the asserted import or operation;
- intermediate_value_exactness: correct intermediate metadata that the downstream consumer ignores, and a different representation with the same effective outcome;
- whole_result_exactness: construct a concrete P-conforming result that *differs from the asserted whole value*: an additional legitimate member, duplicate, or order variation when P fixes only inclusion or meaning. This includes `set(lines) == {seeded lines}` in an include-all or include-hidden mode: consider an additional valid programmatic setting line. If the result maps a named group to a list of independent setting pairs, vary their order inside the allowed group, not only the top-level group set. For an identifier aggregation list, consider an additional derived but equivalent identifier or canonical alias when P requires inclusion of input variants but does not forbid derived equivalents; do not infer a closed set merely from the historical fixture or Gold output. A concrete example is a valid ISBN-10 represented alongside its convertible ISBN-13. Reject a vacuous valid_alternative that exactly repeats the asserted result. Cite P or a documented public consumer contract if order or exact members are truly required;
- default_output_subset: a P-violating default result that contains the expected customized entry and omits hidden entries but also leaks a noncustomized, nonhidden entry. If P or a retained historical public behavior says default output contains only customized entries, determine whether the executable test rejects this counterexample; also consider a correct output with a different allowed order;
- exact_numeric_boundary: a P-conforming scoring or matching implementation with a different numeric score while preserving the stated relative decision and threshold behavior. A truth assertion on `compare(left, right, 515)` fixes a numeric boundary just as an explicit `==` does; nested argument calls do not change that. A historical test value or Gold score does not by itself make the exact boundary part of P. Check whether a documented public scoring contract fixes that number; for invalid_alternative, use a matcher that ignores the threshold or fails to compare the required records;
- self_calibrated_threshold: a matcher that returns a finite monotone score for the tested record pair but ignores the P-required feature (for example author identity). If the test discovers a boundary only by repeatedly calling that same matcher on one pair and then asserts True at the discovered boundary and False above it, determine whether this incorrect matcher still passes. Require an independent causal control that changes only the required feature while retaining the rest of the fixture; do not fix an undocumented absolute score;
- finite_option_vocabulary: a P-conforming public feature exposed with a plausible user-visible option/query/command name outside the test's hard-coded seed and prefix list (for example `internal` where the list contains only `hidden` and `all`). Trace every executable discovery path, including URL probes, method-signature checks, and command registry access, to see whether it can reach that alternative. If P or a documented public contract does not fix the spelling and no broader stable discovery path exists, the verifier overconstrains the interface; for invalid_alternative, use an option that produces the old result or only echoes a preloaded fixture;
- subcomponent_location_binding: a P-conforming feature rendered elsewhere on the same required page or product surface rather than the exact nested template under test. Decide whether P or a pre-existing public contract fixes that component location. Do not treat a Gold template location or a historical helper as normative; for invalid_alternative, use a page missing the required visible behavior;
- reflective_entrypoint_scope: an otherwise P-conforming feature exposed through an existing public method, class method, or opt-in option instead of a standalone function found by reflective package scanning. Check whether the verifier excludes that plausible access path or selects a different entrypoint per expected test answer. Include an existing public instance method whose class requires real product/runtime initialization (for example module parameters, a database session, or application context): `object.__new__` plus synthetic attributes and speculative constructor keywords may not make that method callable. Trace whether the verifier can invoke it with valid state, not merely enumerate its name. If this plausible public path is excluded and P does not identify another stable entrypoint, report an access-contract ambiguity instead of treating a package-wide reflective scan as complete. If P names one access path, cite it; otherwise require a stable public behavior boundary without freezing topology;
- private_entrypoint_call: first distinguish a test-local fixture helper from a callable imported from or accessed on the repository. A private repository method is not a product contract merely because it exists in Base or is used by Gold. Construct a P-conforming implementation that removes or renames that helper while preserving the same public outcome. If the verifier directly invokes the helper and that alternative cannot pass, require a public product trigger and observation instead. Also test a P-violating implementation where the private helper still works but the public product behavior is broken; a helper-only test may falsely pass it. Permit direct use only when P or an existing documented public contract explicitly makes that callable part of the contract; if no public boundary can both exercise the historical behavior and fairly distinguish Base from Gold, report an access-contract ambiguity rather than moving down to a private helper;
- multiple_null_constructor_dependencies: construct a P-conforming implementation whose public behavior is unchanged but whose router/service requires initialized dependencies, a different factory, or a changed constructor. If the test fails before reaching the required public observation because setup passes several null dependencies, treat that setup as an undocumented binding unless P or a documented public contract fixes it. For the violating counterfactual, keep valid initialization but remove/break the required public behavior; the verifier must still fail;
- public_type_origin_binding: a public type defined in a private implementation module but re-exported through an importable public namespace. Include a counterfactual re-export from a different public package branch that is not imported as a side effect of the tested code, not only a re-export from the nearest package or tested module. Trace the executable scanner to verify it would actually visit that branch; do not accept comments claiming a complete public scan as evidence. Decide whether the test demands the definition site or an incomplete discovery path rather than public access promised by P. For invalid_alternative, use an implementation with no public namespaced access at all;
- representation_wrapper_acceptance: when P requires a meaningful top-level organization in a textual representation, wrap the old flat list in an arbitrary unrelated call such as `opaque([record(value, scope)])`. Trace the actual classifier, including AST walks and hand-written delimiter parsers: finding a nested pair or treating every non-built-in call name as an organized container does not prove that the outer representation is organized. The P-violating wrapped flat list must fail; an independently organized mapping or record with the same semantic entries must pass. Do not require a particular constructor or spelling unless P fixes it;
- legacy_alias_representation: a migration that introduces and uses the P-required public namespaced type while deprecated legacy aliases still return their original plain values and notify callers. Decide whether P explicitly requires the aliases themselves to return the new type. Equality with a new IntEnum member in a historical test does not prove a return-type requirement because old integers compare equal to IntEnum members. For invalid_alternative, remove the public type or omit the deprecation notification; test the new representation separately from legacy compatibility.
- permutation_invariant_mapping: swap two named legacy aliases or category labels while keeping their values distinct, within the same public member set, and preserving every warning. A membership predicate such as `any(alias == member for member in public_members)` plus `len(set(aliases)) == N` cannot detect this wrong mapping. Trace executable tests, including retained regressions, to identify exactly which named states are observed through an independent public transition or role-specific outcome. Do not credit comments claiming runtime mapping when the code only constructs an object. If P requires named meanings, PASS requires an executable assertion that distinguishes the swapped mapping. For a valid alternative, use different public member names or representation while preserving each named alias meaning.
- decision_branch_binding: a P-conforming implementation that makes a different idempotence or change-detection decision for the exact fixture while preserving the required final product state. Check whether the fixture actually makes the opposite branch wrong: if archive and destination contents match, a content-aware implementation may correctly report already extracted even when the Gold timestamp path reports changed. If a particular branch is required, construct a fixture with different final contents and observe the public result. Do not use a mutable staging field such as an includes cache as a substitute for the final product outcome. For invalid_alternative, use a decoder that still raises or fails to extract changed content; cite P if it fixes the branch.
- unconditional_downstream_side_effect: construct a concrete implementation that reports the claimed decision/registration result but omits the required registration, while the test double still performs a downstream action by default (for example, a fake command extracts every input when no selected names are passed). Trace whether the action is actually gated on the decision or consumes the registered subset; an unconditional action and its resulting side effect do not prove registration. A valid alternative may use a different routing strategy, but must still make the required decision control the observed action. For invalid_alternative, retain the fake and final output while making registration a no-op; determine whether the verifier rejects it.
- derived_identifier_type_binding: a stable, name-derived identifier represented by an integer hash, bytes token, or structured value that the public comparator consumes, rather than a newly added nonempty string field. If P does not specify string representation, check whether the emitted predicate would reject this valid alternative. For invalid_alternative, use a constant or absent identifier that fails to distinguish authors. Require evidence of name dependence and consistent matching behavior, not a Gold field type.
- fixture_extension_hook: production code that satisfies P using another observable communication or callback path while never calling the method added only by this test subclass. Also consider a safe direct output path if P requires reliability rather than a particular relay. For invalid_alternative, use a path that loses messages, interleaves them, or blocks shutdown;
- fixture_preloaded_provider: the INVALID alternative is ALWAYS a broken real provider that returns no data while the test fixture still supplies a preloaded object and the downstream renderer still works. Do not substitute a renderer that omits output; that only tests the downstream half. If P says a live product page/service shows information from an external source or asks for retrieval, acquisition is part of its observable behavior even when P does not prescribe the provider method. Verify an executable selector reaches the real product acquisition path with a public input; a preloaded fixture alone cannot prove it. If P explicitly scopes the feature to formatting an already supplied object, cite that exact P passage. For valid_alternative, use a different P-conforming acquisition path that still supplies the required result;
- fixed_serialization_fixture: a P-conforming serializer and parser that use a different stable, editable encoding for the same information. If the test parses a literal independent of the implementation output, decide whether P or an established public input contract actually requires that literal syntax. Historical test fixtures, Gold output, and the converted trace alone do not establish that contract. For invalid_alternative, use a serializer/parser pair that drops P-required data from its own canonical output;
- serialization_shape_assertion: a P-conforming serializer and parser using a different editable Markdown layout, delimiter, level marker, or multiple lines while preserving data and a stable round trip. Decide whether P or a pre-existing public input contract fixes the asserted shape, including line count. For invalid_alternative, use output that loses P-required data or cannot be parsed back;
- system_path_mutation: a task-scoped temporary fixture with the same declared behavior, and failure/side effects from modifying a system file;
- message_lexical_gate: a meaningful paraphrase or localization using words outside the predicate; explicitly test a modal prohibition such as "Hosts must not be empty" or "Hosts may not be empty" as valid for empty-host input, and distinguish it from the contradictory factual claim "Hosts are not empty"; also test a generic or incoherent bag of matched keywords;
- message_nonempty_only: a meaningful P-conforming message, plus a nonempty but context-free message such as "Oops". If P leaves message wording/content open and supplies no stable semantic oracle, accepting the context-free alternative is a residual limitation, not by itself a verifier defect. Record it without imposing a lexical/grammar requirement or failing the task solely for this open-text limitation.

Do not accept "documented limitation", a self-review PASS, Base FAIL/Gold PASS, or a single passing Gold sentence as proof that a false positive or false negative is harmless. If the code would reject a P-conforming alternative or accept a P-violating alternative, return FAIL with the specific executable line and repair direction. If P explicitly requires the suspicious exactness, quote its exact words. A generic phrase about a set of files or observations does not freeze the historical membership of that set after a valid refactor. If there is no such P passage, do not claim an exact count, top-level layout, every observation, intermediate representation, or system-path rewrite is required. For text, no finite lexicon proves natural-language appropriateness; assess the concrete predicate in both directions and state any residual limit.

Keep each assessment concise: valid_alternative and invalid_alternative should each be at most 35 words, reason at most 45 words, and p_contract_quote only the shortest exact supporting clause. Do not include chain-of-thought or repeat the supplied source. Return ONE compact JSON object with verdict PASS or FAIL, findings, and assessments. Include exactly one assessment for every supplied (file, kind) signal. Each assessment must contain file, kind, constraint_required_by_p (boolean), p_contract_quote (string, empty unless required), valid_alternative (string), predicted_valid_pass (boolean), invalid_alternative (string), predicted_invalid_fail (boolean), and reason (string). A PASS requires every P-conforming alternative to pass and every deterministically distinguishable P-violating alternative to fail. For an open-ended natural-language message with no stable content oracle in P, accepting an uninformative text is a residual limitation rather than a hard failure; record it explicitly. When a class has no meaningful invalid alternative, use an empty invalid_alternative and predicted_invalid_fail=true. Do not return prose outside JSON."""


def _pairs(signals: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {(str(s.get("file", "")), str(s.get("kind", ""))) for s in signals}


def validate_review(value: dict[str, Any], signals: list[dict[str, str]], problem: str) -> list[str]:
    """Check that a narrow Judge actually accounted for each detected risk."""
    errors: list[str] = []
    if value.get("verdict") not in {"PASS", "FAIL"}:
        return ["focused review has no closed PASS/FAIL verdict"]
    rows = value.get("assessments")
    if not isinstance(rows, list):
        return ["focused review omitted assessments"]
    expected = _pairs(signals)
    actual: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            errors.append("focused review has a non-object assessment")
            continue
        key = (str(row.get("file", "")), str(row.get("kind", "")))
        if key in actual:
            errors.append(f"duplicate focused assessment {key}")
        actual.add(key)
        if not isinstance(row.get("constraint_required_by_p"), bool):
            errors.append(f"{key}: missing P constraint decision")
            continue
        if row["constraint_required_by_p"]:
            quote = str(row.get("p_contract_quote", "")).strip()
            if not quote or quote not in problem:
                errors.append(f"{key}: claimed exact P constraint without a verbatim P quote")
        if not str(row.get("valid_alternative", "")).strip():
            errors.append(f"{key}: missing concrete P-conforming alternative")
        if not isinstance(row.get("predicted_valid_pass"), bool):
            errors.append(f"{key}: missing prediction for P-conforming alternative")
        if key[1] in {"intermediate_value_exactness", "default_output_subset", "exact_numeric_boundary", "self_calibrated_threshold", "finite_option_vocabulary", "fixed_serialization_fixture", "serialization_shape_assertion", "subcomponent_location_binding", "reflective_entrypoint_scope", "public_type_origin_binding", "private_entrypoint_call", "legacy_alias_representation", "permutation_invariant_mapping", "representation_wrapper_acceptance", "decision_branch_binding", "unconditional_downstream_side_effect", "derived_identifier_type_binding", "fixture_extension_hook", "fixture_preloaded_provider", "message_lexical_gate", "message_nonempty_only", "multiple_null_constructor_dependencies"}:
            if not str(row.get("invalid_alternative", "")).strip():
                errors.append(f"{key}: missing P-violating alternative")
        if not isinstance(row.get("predicted_invalid_fail"), bool):
            errors.append(f"{key}: missing prediction for P-violating alternative")
        if key[1] == "private_entrypoint_call":
            alternative = str(row.get("valid_alternative", "")).lower()
            if not re.search(r"public|product|observable|caller|boundary|entrypoint", alternative):
                errors.append(f"{key}: valid alternative must preserve the behavior through a public observable boundary")
            if not re.search(r"remove|rename|different|another|alternative|without", alternative):
                errors.append(f"{key}: valid alternative must vary or remove the private helper")
        if key[1] == "permutation_invariant_mapping":
            alternative = str(row.get("invalid_alternative", "")).lower()
            if not re.search(r"swap|permut|exchang|reassign|wrong[- ]state|wrong[- ]meaning", alternative):
                errors.append(f"{key}: mapping counterexample must change named meanings while preserving membership and distinctness")
        if key[1] == "fixture_preloaded_provider":
            # The counterexample must isolate the provider while keeping the
            # fixture and downstream rendering path functional.
            alternative = str(row.get("invalid_alternative", "")).lower()
            needed = (
                r"provider|fetch|retriev|acquir|source|upstream|connector|lookup|query|\bsearch\b",
                r"fixture|preload|stub|supplied|inject|seed|test double|test record|synthetic record",
                r"render|display|page|output|downstream|renderer|view|present|visible",
                r"fail|broken|none|empty|missing|unavailable|no data|error|returns? no|does not return|without data|returns? nothing",
            )
            if not all(re.search(pattern, alternative) for pattern in needed):
                errors.append(f"{key}: provider counterexample must keep the fixture and renderer working while the real provider fails")
        if not str(row.get("reason", "")).strip():
            errors.append(f"{key}: missing executable-code reasoning")
    if actual != expected:
        errors.append(f"focused review signal mismatch: missing={sorted(expected-actual)}, extra={sorted(actual-expected)}")
    return errors


def review_counterfactuals(
    *, config: dict[str, Any], credentials: dict[str, Any],
    problem: str, addendum: str, signals: list[dict[str, str]],
    tests: dict[str, dict[str, object]], trace_rows: list[dict[str, Any]],
    judge_fn: Callable[..., dict[str, Any]],
) -> dict[str, Any] | None:
    focused = [signal for signal in signals if signal.get("kind") in FOCUSED_KINDS]
    if not focused:
        return None

    # Keep risk review output bounded. A single source file can trigger several
    # independent signals; asking for a long assessment for every kind in one
    # response can truncate the required JSON and fail closed before the
    # Converter can receive actionable evidence.
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for signal in focused:
        key = (str(signal.get("file", "")), str(signal.get("kind", "")))
        if key not in seen:
            seen.add(key)
            unique.append(signal)
    batch_size = 2
    batches = [unique[index:index + batch_size] for index in range(0, len(unique), batch_size)]
    all_assessments: list[dict[str, Any]] = []
    all_findings: list[str] = []
    model_verdicts: list[str] = []
    protocol_retries: list[str] = []
    source_limit = 20000
    for batch_index, batch in enumerate(batches, start=1):
        sources = {
            name: str(tests[name].get("head", ""))[:source_limit]
            for name in sorted({str(signal.get("file", "")) for signal in batch})
            if name in tests
        }
        evidence = {
            "problem_statement": problem[:12000],
            "specification_addendum": addendum[:8000],
            "risk_signals": batch,
            "executable_sources": sources,
            "f2p_rows": trace_rows,
        }
        accepted: dict[str, Any] | None = None
        errors: list[str] = []
        for attempt in range(2):
            try:
                value = judge_fn(
                    config=config, credentials=credentials, role="semantic",
                    system=SYSTEM, evidence=evidence,
                )
                if not isinstance(value, dict):
                    errors.append(f"attempt_{attempt+1}: focused review was not a JSON object")
                    continue
                value.pop("raw_response", None)
                protocol = validate_review(value, batch, problem + "\n" + addendum)
                findings = value.get("findings")
                if isinstance(findings, str):
                    findings = [findings] if findings.strip() else []
                elif isinstance(findings, list):
                    # Findings are explanatory only; the closed verdict and
                    # validated per-signal assessments carry the gate result.
                    findings = [item for item in findings if isinstance(item, str)]
                else:
                    findings = []
                if protocol:
                    errors.append(f"attempt_{attempt+1}: {'; '.join(protocol)}")
                    continue
                value["findings"] = findings
                accepted = value
                break
            except (ValueError, RuntimeError) as exc:
                errors.append(f"attempt_{attempt+1}: {exc!r}")

        if accepted is None:
            protocol_retries.extend(f"batch_{batch_index}: {error}" for error in errors)
            return {
                "verdict": "FAIL", "review_mode": "focused_counterfactual_protocol_failure",
                "findings": ["Focused risk review could not account for every flagged assertion"],
                "protocol_errors": protocol_retries,
                "risk_batch_count": len(batches),
            }
        protocol_retries.extend(f"batch_{batch_index}: {error}" for error in errors)
        model_verdicts.append(str(accepted["verdict"]))
        all_findings.extend(accepted["findings"])
        all_assessments.extend(accepted["assessments"])

    open_text_limitations = [
        row for row in all_assessments
        if row["kind"] == "message_nonempty_only"
        and row["predicted_valid_pass"]
        and not row["predicted_invalid_fail"]
    ]
    counterexamples = [
        row for row in all_assessments
        if not row["constraint_required_by_p"] and (
            not row["predicted_valid_pass"] or not row["predicted_invalid_fail"]
        ) and row not in open_text_limitations
    ]
    unsupported_exactness = [
        row for row in all_assessments
        if row["constraint_required_by_p"] and not row["predicted_invalid_fail"]
        and row not in open_text_limitations
    ]
    for row in counterexamples:
        all_findings.append(f"{row['file']} [{row['kind']}]: {row['reason']}")
    for row in unsupported_exactness:
        all_findings.append(
            f"{row['file']} [{row['kind']}]: the verifier does not reject a counterexample to its claimed P constraint"
        )
    # A focused judge may mark an open-text residual limitation FAIL because
    # its counterfactual is accepted by a nonempty-only predicate. That is not
    # a hard defect absent a P-defined semantic oracle; retain the audit trail.
    blocking_model_fail = "FAIL" in model_verdicts and not (
        open_text_limitations and len(open_text_limitations) == len(all_assessments)
    )
    result = {
        "verdict": "FAIL" if blocking_model_fail or counterexamples or unsupported_exactness else "PASS",
        "review_mode": "focused_counterfactual",
        "findings": all_findings,
        "assessments": all_assessments,
        "risk_batch_count": len(batches),
    }
    if open_text_limitations:
        result["residual_limitations"] = [
            {"file": row["file"], "kind": row["kind"], "reason": row["reason"]}
            for row in open_text_limitations
        ]
    if protocol_retries:
        result["protocol_retries"] = protocol_retries
    return result
