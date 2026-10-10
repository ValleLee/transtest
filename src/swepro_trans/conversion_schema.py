"""Shared schema and decision rules for F2P conversion rows."""
from __future__ import annotations

import re
from typing import Any

BEHAVIOR_CLASSIFICATIONS = frozenset({
    "p_supported_behavior",
    "base_regression_behavior",
    "missing_product_behavior",
    "implementation_detail",
})

CLASSIFICATION_DECISIONS = {
    "p_supported_behavior": frozenset({"rewrite", "merge"}),
    "base_regression_behavior": frozenset({"rewrite", "merge"}),
    "missing_product_behavior": frozenset({"specification_gap"}),
    "implementation_detail": frozenset({"drop"}),
}

REQUIRED_F2P_FIELDS = frozenset({
    "source_f2p",
    "behavior_intent",
    "functional_surface",
    "evidence",
    "historical_behavior",
    "behavioral_obligations",
    "obligation_accounting",
    "preservation_evidence",
    "problem_statement_support",
    "problem_statement_quotes",
    "behavior_classification",
    "binding_detected",
    "base_repo_observable",
    "base_behavior_status",
    "gold_only_binding",
    "observable_surface",
    "decision",
    "emitted_tests",
    "rationale",
    "specification_gap",
    "specification_proposal",
    "planned_observable_surface",
    "drop_justification",
    "drop_evidence",
})

TASK_DISPOSITIONS = frozenset({"convertible", "non_discriminative"})
P2P_POLICY = "preserve_original_verbatim"
OBLIGATION_SCOPES = frozenset({"product_behavior", "implementation_detail"})
OBLIGATION_DISPOSITIONS = {
    "product_behavior": frozenset({"preserved", "pending_specification"}),
    "implementation_detail": frozenset({"excluded"}),
}
REQUIRED_OBLIGATION_FIELDS = frozenset({
    "id", "obligation", "scope", "disposition", "emitted_tests",
    "evidence", "rationale",
})

UNRESOLVED_EXACT_VALUES = frozenset({"pending", "placeholder", "draft", "skeleton", "tbd", "todo"})
UNRESOLVED_MARKER = re.compile(
    r"\b(?:placeholder|pending refinement|draft skeleton|skeleton row|awaiting evidence|to be refined)\b",
    re.IGNORECASE,
)
BOOLEAN_LITERAL_FIELDS = frozenset({"base_repo_observable", "gold_only_binding"})


def coerce_boolean_literal(value: Any) -> Any:
    """Coerce only unambiguous JSON-like boolean literals.

    Agent output sometimes quotes booleans. Accepting a fixed literal set is a
    presentation normalization; descriptive or uncertain text remains unchanged
    and is rejected by the schema gate.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return value


def canonical_retained_p2p(
    original_p2p: list[str], accounting: dict[str, Any] | None,
) -> tuple[list[str], list[str]]:
    """Keep every original P2P selector unchanged and in its original order."""
    errors: list[str] = []
    accounting = accounting if isinstance(accounting, dict) else {}
    excluded = accounting.get("excluded", [])
    if excluded not in (None, []):
        errors.append("original P2P selectors cannot be excluded or rewritten")
    retained = accounting.get("retained")
    if retained is not None and retained != original_p2p:
        errors.append("p2p_accounting.retained must equal the original P2P selector list exactly")
    for field in ("converted_to_regression", "converted_regressions"):
        if accounting.get(field):
            errors.append(f"{field} cannot alter original P2P; convert only historical F2P")
    return list(original_p2p), errors


def append_f2p_regressions(original_p2p: list[str], regressions: list[str]) -> list[str]:
    """Append F2P-derived regressions without changing the original P2P list."""
    result = list(original_p2p)
    for selector in regressions:
        if selector not in result:
            result.append(selector)
    return result


def converted_selector_groups(trace: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return delta and Base-regression selectors from preserved obligations.

    One historical F2P can contain both kinds of behavior. Its row status is
    only a default for older traces; an obligation's own Base status determines
    the role of its emitted selectors when present.
    """
    deltas: list[str] = []
    regressions: list[str] = []
    for row in trace.get("f2p_accounting", []):
        if not isinstance(row, dict) or row.get("decision") not in {"rewrite", "merge"}:
            continue
        obligations = row.get("obligation_accounting")
        if isinstance(obligations, list) and obligations:
            sources = [
                item for item in obligations
                if isinstance(item, dict)
                and item.get("scope") == "product_behavior"
                and item.get("disposition") == "preserved"
            ]
        else:
            sources = [row]
        for item in sources:
            status = item.get("base_behavior_status", row.get("base_behavior_status"))
            target = (
                regressions
                if status == "already_satisfies"
                or (status is None and row.get("behavior_classification") == "base_regression_behavior")
                else deltas
            )
            raw = item.get("emitted_tests", [])
            for selector in raw if isinstance(raw, list) else [raw]:
                value = str(selector).strip()
                if value and value not in target:
                    target.append(value)
    # P2P is construction input and must remain verbatim. Only converted F2P
    # rows can contribute functional deltas or Base regressions.
    return deltas, regressions


TRACE_SEMANTIC_FIELDS = frozenset({
    "behavior_intent", "historical_behavior", "preservation_evidence",
    "functional_surface", "evidence", "problem_statement_support",
    "binding_detected", "base_repo_observable", "gold_only_binding",
    "observable_surface", "rationale", "specification_gap",
    "specification_proposal", "planned_observable_surface",
    "drop_justification", "drop_evidence",
})


def _unresolved_text(value: Any) -> bool:
    text = str(value).strip()
    normalized = re.sub(r"[_-]+", " ", text)
    return normalized.casefold() in UNRESOLVED_EXACT_VALUES or bool(UNRESOLVED_MARKER.search(normalized))


def unresolved_trace_errors(trace: dict[str, Any] | None) -> list[str]:
    """Reject scaffolding that looks structurally complete but is not evidence-backed."""
    if not isinstance(trace, dict):
        return []
    errors: list[str] = []
    if _unresolved_text(trace.get("task_disposition_reason", "")):
        errors.append("task_disposition_reason contains an unresolved scaffold marker")
    for row in f2p_rows(trace):
        source = str(row.get("source_f2p", "<unknown>"))
        for field in TRACE_SEMANTIC_FIELDS:
            value = row.get(field, "")
            if value and _unresolved_text(value):
                errors.append(f"{source}: {field} contains an unresolved scaffold marker")
        for selector in row.get("emitted_tests", []) if isinstance(row.get("emitted_tests"), list) else [row.get("emitted_tests", "")]:
            if selector and _unresolved_text(selector):
                errors.append(f"{source}: emitted_tests contains an unresolved scaffold marker")
        for index, item in enumerate(row.get("obligation_accounting", [])):
            if not isinstance(item, dict):
                continue
            for field in ("obligation", "evidence", "rationale"):
                value = item.get(field, "")
                if value and _unresolved_text(value):
                    errors.append(
                        f"{source}: obligation_accounting[{index}].{field} contains an unresolved scaffold marker"
                    )
            for selector in item.get("emitted_tests", []) if isinstance(item.get("emitted_tests"), list) else [item.get("emitted_tests", "")]:
                if selector and _unresolved_text(selector):
                    errors.append(
                        f"{source}: obligation_accounting[{index}].emitted_tests contains an unresolved scaffold marker"
                    )
    return errors


def obligation_accounting_errors(row: dict[str, Any]) -> list[str]:
    """Validate per-assertion decomposition within one historical F2P row.

    A historical test may mix product behavior with helper representation or
    out-of-domain plumbing. Product obligations must map to emitted tests; only
    explicitly evidenced implementation aspects may be excluded.
    """
    source = str(row.get("source_f2p", "<unknown>"))
    declared = row.get("behavioral_obligations")
    items = row.get("obligation_accounting")
    errors: list[str] = []
    if not isinstance(declared, list) or not declared or not all(str(item).strip() for item in declared):
        return [f"{source}: behavioral_obligations must be a non-empty string list"]
    if not isinstance(items, list) or not items:
        return [f"{source}: obligation_accounting must be a non-empty list"]
    if len(items) != len(declared):
        errors.append(
            f"{source}: obligation_accounting must have one entry per behavioral_obligations item "
            f"({len(items)} != {len(declared)})"
        )
    ids: list[str] = []
    preserved_selectors: list[str] = []
    product_dispositions: list[str] = []
    implementation_count = 0
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{source}: obligation_accounting[{index}] must be an object")
            continue
        missing = sorted(REQUIRED_OBLIGATION_FIELDS - set(item))
        if missing:
            errors.append(f"{source}: obligation_accounting[{index}] missing fields: {', '.join(missing)}")
            continue
        oid = str(item.get("id", "")).strip()
        if not oid:
            errors.append(f"{source}: obligation_accounting[{index}].id is empty")
        ids.append(oid)
        if not str(item.get("obligation", "")).strip():
            errors.append(f"{source}: obligation_accounting[{index}].obligation is empty")
        if not str(item.get("evidence", "")).strip():
            errors.append(f"{source}: obligation_accounting[{index}].evidence is empty")
        if not str(item.get("rationale", "")).strip():
            errors.append(f"{source}: obligation_accounting[{index}].rationale is empty")
        scope = item.get("scope")
        disposition = item.get("disposition")
        if scope not in OBLIGATION_SCOPES:
            errors.append(f"{source}: obligation_accounting[{index}].scope must be one of {sorted(OBLIGATION_SCOPES)}")
            continue
        if disposition not in OBLIGATION_DISPOSITIONS[scope]:
            errors.append(
                f"{source}: obligation_accounting[{index}] scope {scope!r} requires disposition "
                f"one of {sorted(OBLIGATION_DISPOSITIONS[scope])}"
            )
        emitted = item.get("emitted_tests")
        if not isinstance(emitted, list):
            errors.append(f"{source}: obligation_accounting[{index}].emitted_tests must be a list")
            emitted = []
        emitted = [str(value).strip() for value in emitted if str(value).strip()]
        if scope == "product_behavior":
            if "base_behavior_status" not in item:
                errors.append(
                    f"{source}: obligation_accounting[{index}].base_behavior_status must be explicit; "
                    "a row-level status cannot classify an individual product obligation"
                )
            elif item.get("base_behavior_status") not in {"already_satisfies", "changed_or_missing", "unavailable"}:
                errors.append(
                    f"{source}: obligation_accounting[{index}].base_behavior_status must be "
                    "already_satisfies, changed_or_missing, or unavailable"
                )
            item_status = item.get("base_behavior_status")
            if row.get("behavior_classification") == "base_regression_behavior" and item_status != "already_satisfies":
                errors.append(f"{source}: Base regression obligation {oid or index} must already satisfy Base")
            product_dispositions.append(str(disposition))
            if disposition == "preserved":
                if not emitted:
                    errors.append(f"{source}: preserved product obligation {oid or index} has no emitted_tests")
                preserved_selectors.extend(emitted)
            elif emitted:
                errors.append(f"{source}: pending product obligation {oid or index} must not emit tests")
        else:
            implementation_count += 1
            if emitted:
                errors.append(f"{source}: excluded implementation obligation {oid or index} must not emit tests")
    duplicates = sorted({value for value in ids if value and ids.count(value) > 1})
    if duplicates:
        errors.append(f"{source}: duplicate obligation ids: {', '.join(duplicates)}")
    classification = row.get("behavior_classification")
    row_emitted_raw = row.get("emitted_tests", [])
    row_emitted = [str(value).strip() for value in (row_emitted_raw if isinstance(row_emitted_raw, list) else [row_emitted_raw]) if str(value).strip()]
    if classification in {"p_supported_behavior", "base_regression_behavior"}:
        if not product_dispositions or any(value != "preserved" for value in product_dispositions):
            errors.append(f"{source}: {classification} requires every product obligation to be preserved")
        if set(preserved_selectors) != set(row_emitted):
            errors.append(f"{source}: row emitted_tests must equal the union of preserved obligation emitted_tests")
    elif classification == "missing_product_behavior":
        if not product_dispositions or any(value != "pending_specification" for value in product_dispositions):
            errors.append(f"{source}: missing_product_behavior requires pending_specification product obligations")
        if row_emitted:
            errors.append(f"{source}: missing_product_behavior must not emit tests")
    elif classification == "implementation_detail":
        if product_dispositions or implementation_count != len(items):
            errors.append(f"{source}: implementation_detail row may contain only excluded implementation obligations")
    return errors


def specification_proposal_is_meta(text: str) -> bool:
    """Whether a proposal asks for a decision instead of stating a contract."""
    return bool(re.search(
        r"^(?:please\s+)?(?:specify|clarify|define|decide|determine|describe|verify|test|check|audit|confirm)\b|"
        r"\bwhether\b|\be\.g\.\s|\bfor example\b|"
        r"\b(?:historical\s+(?:test|hypothesis|f2p)|f2p|verifier|gold-only|p-named)\b|"
        r"\b(?:hypothesis|property-based)\s+(?:test|property)\b|"
        r"\btest(?:s|ing)?\s+(?:assertion|suite|case|coverage|property)\b|"
        r"\binternal\s+(?:detail|robustness|probe|implementation)\b|"
        r"\bno\s+independent\s+product\s+outcome\b",
        str(text or "").strip(),
        re.IGNORECASE,
    ))


def specification_addendum_errors(text: str) -> list[str]:
    """Validate the controller-owned behavior supplement as solver-ready text."""
    value = str(text or "").strip()
    if not value:
        return []
    marker = "## Additional observable behavior"
    sections = value.split(marker)
    if len(sections) < 2:
        return ["specification_addendum.md has no Additional observable behavior section"]
    errors: list[str] = []
    for index, section in enumerate(sections[1:], 1):
        body = section.strip()
        if not body:
            errors.append(f"specification_addendum.md section {index} is empty")
        elif specification_proposal_is_meta(body):
            errors.append(
                f"specification_addendum.md section {index} is meta-language rather than "
                "a chosen observable behavior"
            )
    return errors


def classification_errors(row: dict[str, Any]) -> list[str]:
    """Return deterministic errors for the four-way F2P classification."""
    source = str(row.get("source_f2p", "<unknown>"))
    classification = row.get("behavior_classification")
    decision = row.get("decision")
    errors: list[str] = obligation_accounting_errors(row)
    if not str(row.get("rationale", "")).strip():
        errors.append(f"{source}: rationale is empty")
    if classification not in BEHAVIOR_CLASSIFICATIONS:
        errors.append(
            f"{source}: behavior_classification must be one of "
            f"{sorted(BEHAVIOR_CLASSIFICATIONS)}, got {classification!r}"
        )
        return errors
    allowed = CLASSIFICATION_DECISIONS[classification]
    if decision not in allowed:
        errors.append(
            f"{source}: classification {classification!r} requires decision "
            f"one of {sorted(allowed)}, got {decision!r}"
        )
    for field in ("base_repo_observable", "gold_only_binding"):
        if field in row and not isinstance(row.get(field), bool):
            errors.append(f"{source}: {field} must be a boolean")
    base_status = str(row.get("base_behavior_status", "")).strip()
    if base_status not in {"already_satisfies", "changed_or_missing", "unavailable"}:
        errors.append(f"{source}: base_behavior_status must be already_satisfies, changed_or_missing, or unavailable")
    if classification == "p_supported_behavior":
        quotes = row.get("problem_statement_quotes")
        if not isinstance(quotes, list) or not quotes or any(not isinstance(q, str) or not q.strip() for q in quotes):
            errors.append(f"{source}: p_supported_behavior requires non-empty problem_statement_quotes")
        if not str(row.get("observable_surface", "")).strip():
            errors.append(f"{source}: p_supported_behavior requires observable_surface")
        # A P-required new public surface can be absent from Base by design.
        # Semantic review must verify P support and Base/Gold replay must prove
        # the claimed delta. An already-satisfied regression still needs a
        # Base observation surface.
        if base_status == "already_satisfies" and row.get("base_repo_observable") is not True:
            errors.append(
                f"{source}: already_satisfies requires an existing Base "
                "observation surface (base_repo_observable=true)"
            )
        if not str(row.get("preservation_evidence", "")).strip():
            errors.append(f"{source}: p_supported_behavior requires preservation_evidence")
    if classification == "base_regression_behavior":
        quotes = row.get("problem_statement_quotes")
        if not isinstance(quotes, list) or not quotes or any(not isinstance(q, str) or not q.strip() for q in quotes):
            errors.append(f"{source}: base_regression_behavior requires non-empty problem_statement_quotes")
        if base_status != "already_satisfies":
            errors.append(
                f"{source}: base_regression_behavior requires "
                "base_behavior_status=already_satisfies"
            )
        if row.get("base_repo_observable") is not True:
            errors.append(
                f"{source}: base_regression_behavior requires an existing Base "
                "public/product observation surface (base_repo_observable=true)"
            )
        if not str(row.get("observable_surface", "")).strip():
            errors.append(f"{source}: base_regression_behavior requires observable_surface")
        if not str(row.get("preservation_evidence", "")).strip():
            errors.append(f"{source}: base_regression_behavior requires preservation_evidence")
    if classification == "missing_product_behavior":
        if not str(row.get("specification_gap", "")).strip():
            errors.append(f"{source}: missing_product_behavior requires specification_gap")
        proposal = str(row.get("specification_proposal", "")).strip()
        if not proposal:
            errors.append(f"{source}: missing_product_behavior requires specification_proposal")
        else:
            if specification_proposal_is_meta(proposal):
                errors.append(
                    f"{source}: specification_proposal must state the chosen observable "
                    "behavior declaratively; it must not ask to specify/decide whether or "
                    "list alternative behaviors"
                )
        if not str(row.get("planned_observable_surface", "")).strip():
            errors.append(f"{source}: missing_product_behavior requires planned_observable_surface")
        if row.get("emitted_tests"):
            errors.append(f"{source}: specification_gap must not emit final tests before the addendum revision")
    if classification == "implementation_detail":
        if not str(row.get("drop_justification", "")).strip():
            errors.append(f"{source}: implementation_detail requires drop_justification")
        if not str(row.get("drop_evidence", "")).strip():
            errors.append(f"{source}: implementation_detail requires drop_evidence")
        if row.get("emitted_tests"):
            errors.append(f"{source}: implementation_detail/drop must not emit a functional test")
    return errors


def trace_disposition_errors(trace: dict[str, Any] | None) -> list[str]:
    """Validate task-level convertibility and P2P policy declarations."""
    if not isinstance(trace, dict):
        return ["conversion_trace must be a JSON object"]
    errors: list[str] = unresolved_trace_errors(trace)
    disposition = trace.get("task_disposition")
    if disposition not in TASK_DISPOSITIONS:
        errors.append(f"task_disposition must be one of {sorted(TASK_DISPOSITIONS)}")
    reason = str(trace.get("task_disposition_reason", "")).strip()
    if not reason:
        errors.append("task_disposition_reason is required")
    p2p = trace.get("p2p_accounting")
    if not isinstance(p2p, dict):
        errors.append("p2p_accounting must be an object")
    else:
        if p2p.get("policy") != P2P_POLICY:
            errors.append(f"p2p_accounting.policy must be {P2P_POLICY!r}")
        excluded = p2p.get("excluded", [])
        if not isinstance(excluded, list):
            errors.append("p2p_accounting.excluded must be a list")
        elif excluded:
            errors.append("original P2P selectors must be retained verbatim; exclusions are forbidden")
        for field in ("converted_to_regression", "converted_regressions"):
            if p2p.get(field):
                errors.append(f"{field} cannot alter original P2P; convert only historical F2P")
    rows = f2p_rows(trace)
    functional = [row for row in rows if row.get("decision") in {"rewrite", "merge"}]
    changed = [
        row for row in functional
        if row.get("behavior_classification") == "p_supported_behavior"
        and row.get("base_behavior_status") == "changed_or_missing"
    ]
    if disposition == "convertible" and not changed:
        errors.append(
            "convertible task requires at least one retained functional behavior that is changed_or_missing in Base"
        )
    if disposition == "non_discriminative" and changed:
        errors.append(
            "non_discriminative task cannot contain retained changed_or_missing functional behavior"
        )
    return errors


def f2p_rows(trace: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return normalized F2P rows from a revision trace."""
    if not isinstance(trace, dict):
        return []
    rows = trace.get("f2p_accounting", [])
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []




def specification_provenance_errors(trace: dict[str, Any] | None, addendum_text: str) -> list[str]:
    """Reject normative support claims that have no controller-owned source.

    Converter revisions may be resumed or seeded from older attempts. They
    cannot carry an "accepted addendum" assertion forward unless the current
    attempt actually contains the controller-generated addendum artifact that
    will later be inserted into final instruction.md.
    """
    if not isinstance(trace, dict) or str(addendum_text or "").strip():
        return []
    errors: list[str] = []
    positive_claims = (
        re.compile(r"\baccepted\s+(?:behavior(?:al)?\s+)?(?:addendum|supplement|clarification)\b", re.IGNORECASE),
        re.compile(r"\b(?:addendum|supplement|clarification)\s+(?:requires|states|supports|authorizes|specifies|clarifies|adds|makes)\b", re.IGNORECASE),
        re.compile(r"\b(?:under|per|according\s+to|from)\s+(?:the\s+)?(?:addendum|supplement|clarification)\b", re.IGNORECASE),
        re.compile(r"\bP\s*(?:\+|plus|and)\s*(?:the\s+)?(?:addendum|supplement|clarification)\b", re.IGNORECASE),
    )
    for row in f2p_rows(trace):
        source = str(row.get("source_f2p", "<unknown>"))
        fields = (
            str(row.get("problem_statement_support", "")),
            str(row.get("evidence", "")),
            str(row.get("rationale", "")),
            str(row.get("preservation_evidence", "")),
        )
        if any(pattern.search(value) for value in fields for pattern in positive_claims):
            errors.append(
                f"{source}: claims a behavior addendum/clarification, but the current "
                "attempt has no controller-generated specification_addendum.md; classify "
                "the missing product behavior as specification_gap or support it from P"
            )
    return errors


def has_functional_rows(trace: dict[str, Any] | None) -> bool:
    """Whether the revision retains at least one functional F2P test."""
    return any(row.get("decision") in {"rewrite", "merge"} for row in f2p_rows(trace))


def replay_expectation(trace: dict[str, Any] | None) -> str:
    """Select the Base/Gold expectation from the converted scope.

    A revision retaining functional F2P rows must distinguish the unpatched
    Base from Gold. If every historical F2P is proven implementation detail and
    dropped, the remaining verifier is regression-only and Base and Gold should
    both pass; requiring Base failure would force a hidden implementation
    contract back into the verifier.
    """
    rows = f2p_rows(trace)
    if not has_functional_rows(trace):
        return "base_pass_gold_pass"
    # A publishable functional task must contain at least one behavior that is
    # absent or different in Base. All-Base-satisfied revisions are routed to
    # non_discriminative review before replay and may not be packaged.
    return (
        "base_fail_gold_pass"
        if any(row.get("base_behavior_status") != "already_satisfies"
               for row in rows if row.get("decision") in {"rewrite", "merge"})
        else "base_pass_gold_pass"
    )
