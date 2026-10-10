"""Structured feedback and bounded revision allocation for Stage 2 repair."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from ..paths import TaskPaths


def _load(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def next_revision(paths: TaskPaths) -> Path:
    numbers = []
    for path in paths.revisions_root.glob("rev_[0-9][0-9][0-9]"):
        match = re.fullmatch(r"rev_(\d{3})", path.name)
        if match:
            numbers.append(int(match.group(1)))
    revision = paths.revisions_root / f"rev_{max(numbers, default=0) + 1:03d}"
    revision.mkdir(parents=True, exist_ok=False)
    return revision


def seed_revision(source: Path, destination: Path) -> None:
    """Copy the last complete verifier artifact into a fresh repair revision."""
    for name in ("conversion_trace.json", "functional_specification.md", "self_review.md", "manifest.json", "tests"):
        src = source / name
        dst = destination / name
        if src.is_dir():
            shutil.copytree(
                src, dst, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
        elif src.is_file():
            shutil.copy2(src, dst)


def _compact_artifact_contract(value: Any) -> Any:
    """Keep artifact feedback actionable without repeating every field/row."""
    if not isinstance(value, dict):
        return value
    compact = dict(value)
    contract = compact.get("contract")
    if not isinstance(contract, dict) or not isinstance(contract.get("errors"), list):
        return compact
    contract = dict(contract)
    errors = [str(item) for item in contract["errors"]]
    scaffold = [item for item in errors if "unresolved scaffold marker" in item]
    others = [item for item in errors if "unresolved scaffold marker" not in item]
    if scaffold:
        locations = []
        for item in scaffold:
            location = item.split(" contains an unresolved scaffold marker", 1)[0]
            if location not in locations:
                locations.append(location)
        others.append(
            f"{len(scaffold)} unresolved scaffold findings remain; replace every draft, "
            f"pending, placeholder, and skeleton value. Sample locations: {locations[:16]}"
        )
        contract["error_summary"] = {
            "total": len(errors),
            "unresolved_scaffold": len(scaffold),
            "sample_locations": locations[:16],
        }
    contract["errors"] = others
    compact["contract"] = contract
    return compact


def _compact_replay_feedback(value: Any, key: str = "") -> Any:
    """Bound replay evidence sent to the repair model while keeping failures.

    Full logs remain in intermediate/validation. Repair feedback needs the
    return code, failing output tail, and stderr; repeated passed-test JSON is
    noise that delays or crowds out the edit itself.
    """
    if isinstance(value, dict):
        return {name: _compact_replay_feedback(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [_compact_replay_feedback(item, key) for item in value]
    if not isinstance(value, str):
        return value
    if key == "output.json":
        return f"[omitted parsed test listing: {len(value)} characters; use output and stderr below]"
    if key == "output":
        # The failing selector may precede thousands of later P2P lines. A
        # plain tail can discard the only actionable assertion and send the
        # repair agent back to guessing from an exit code.
        sections = re.split(r"(?=^===== SELECTOR:)", value, flags=re.MULTILINE)
        failures = [section for section in sections if re.search(
            r"(?m)^FAILED\s|^ERROR\s|AssertionError|Traceback|MODULE FAILURE|\bFAILURES\b",
            section,
        )]
        if failures:
            excerpts = [section[-5000:] for section in failures[:3]]
            return "[failing selector excerpts]\n" + "\n".join(excerpts)[:14000]
    if key == "runner_stdout.log":
        return f"[omitted duplicate runner stdout: {len(value)} characters; use output above]"
    limit = 3000 if key in {"output", "runner_stderr.log"} else 5000
    if len(value) <= limit:
        return value
    return f"[truncated {len(value) - limit} leading characters]\n" + value[-limit:]


def _selector_name_diagnostics(paths: TaskPaths, revision: Path) -> list[dict[str, Any]]:
    """Diagnose whether original P2P selectors execute without rewriting them."""
    config = _load(revision / "tests" / "config.json") or {}
    expected = config.get("pass_to_pass", []) if isinstance(config, dict) else []
    if isinstance(expected, str):
        try:
            expected = json.loads(expected)
        except json.JSONDecodeError:
            expected = []
    if not isinstance(expected, list):
        return []
    diagnostics: list[dict[str, Any]] = []
    for side in ("base", "gold"):
        output = None
        for name in ("output.json", "parsed_results.json", "results.json"):
            candidate = _load(paths.hard_replay_root / "docker" / side / name)
            if isinstance(candidate, dict) and isinstance(candidate.get("tests"), list):
                output = candidate
                break
        if not output:
            continue
        observed = {
            str(item.get("name", "")).strip(): str(item.get("status", "")).strip()
            for item in output["tests"] if isinstance(item, dict)
        }
        for selector in expected:
            selector = str(selector).strip()
            if not selector or selector in observed or " | " not in selector:
                continue
            file_path, *parts = selector.split(" | ")
            leaf = parts[-1]
            matches = [
                {"name": name, "status": status}
                for name, status in observed.items()
                if name.startswith(file_path + " | ") and name.rsplit(" | ", 1)[-1] == leaf
            ]
            if matches:
                diagnostics.append({
                    "side": side, "canonical_selector": selector,
                    "observed_same_file_and_leaf": matches[:3],
                })
            if len(diagnostics) >= 8:
                return diagnostics
    return diagnostics


def _repair_objectives(failed_gate: str, evidence: dict[str, Any]) -> list[str]:
    objectives: list[str] = []
    semantic = evidence.get("semantic_review")
    if isinstance(semantic, dict):
        deterministic = semantic.get("deterministic_binding_gate")
        symbols = deterministic.get("gold_only_symbols", []) if isinstance(deterministic, dict) else []
        if symbols:
            objectives.append(
                "Remove unsupported Gold-only member/signature dependencies, but retain a "
                "behavioral check for any P-named public type only when historical F2P covers its behavior. Review: "
                + ", ".join(map(str, symbols))
            )
            objectives.append(
                "Rewrite behavior through a public boundary. When P does not name the "
                "new symbol and both Base and Gold satisfy the behavior, set "
                "base_behavior_status=already_satisfies and task_disposition=non_discriminative; "
                "do not defend an unspecified method by citing Requirements, Interface, "
                "Gold, or historical tests. A P-named class is in scope only when historical F2P covers behavior involving it; "
                "do not add coverage from P alone."
            )
    if failed_gate == "semantic_review" and isinstance(semantic, dict):
        semantic_findings = []
        for key in ("findings", "binding_risks", "hidden_contracts", "under_conversion", "mapping_gaps"):
            values = semantic.get(key) or []
            if isinstance(values, list):
                semantic_findings.extend(str(value) for value in values if str(value).strip())
        if semantic_findings:
            objectives.append(
                "Repair the semantic defects identified by the Judge without weakening the "
                "historical product behavior. Remove hidden method, call-shape, ordering, DOM, "
                "or representation contracts that the effective Problem Statement does not "
                "authorize; assert the equivalent public/observable product outcome instead. "
                "Primary findings: " + " | ".join(semantic_findings[:4])
            )
        specification_gaps = semantic.get("specification_gaps") or []
        if isinstance(specification_gaps, list) and specification_gaps:
            objectives.append(
                "Inspect the effective Problem Statement, including any controller-generated "
                "specification addendum, before acting on the Judge's specification_gaps. "
                "If the behavior is already stated there, keep its rewrite/merge mapping and "
                "strengthen the emitted test to observe the missing behavior; do not reclassify "
                "it as specification_gap. Only genuinely unstated product behavior should become "
                "missing_product_behavior/specification_gap with a minimal behavior-level proposal "
                "and planned public observation surface. Do not drop observable behavior."
            )
    if failed_gate == "behavior_role_audit":
        role_audit = evidence.get("behavior_role_audit")
        errors = role_audit.get("errors", []) if isinstance(role_audit, dict) else []
        objectives.append(
            "Reconcile every row's base_behavior_status with the per-selector Base replay. "
            "A selector that PASSES on Base is a converted regression, not a functional delta; "
            "use base_regression_behavior when P does not state that existing behavior. A true "
            "functional delta must have an independently executable selector that FAILS on Base. "
            "Split selectors shared across the two roles. Do not weaken assertions or introduce "
            "an unnamed Gold-only API to manufacture Base failure. Preserve a P-named new public type only when historical F2P covers its behavior. Findings: "
            + " | ".join(str(item) for item in errors[:8])
        )
    if failed_gate in {"hard_replay", "stability"}:
        objectives.append(
            "Fix the concrete runner/runtime failure shown in diagnostic_artifacts before "
            "changing semantic scope; keep all previously accepted F2P mappings intact."
        )
        hard = evidence.get("hard_replay")
        replay = hard.get("hard_replay", hard) if isinstance(hard, dict) else {}
        runs = replay.get("runs", {}) if isinstance(replay, dict) else {}
        setup_failures = []
        if isinstance(runs, dict):
            for side, run in runs.items():
                if not isinstance(run, dict):
                    continue
                diagnosis = run.get("execution_diagnosis")
                if isinstance(diagnosis, dict) and diagnosis.get("classification") == "setup_failure_before_leaf_tests":
                    setup_failures.append({
                        "side": side,
                        "failed_setup_hooks": diagnosis.get("failed_setup_hooks", []),
                    })
        if setup_failures:
            objectives.append(
                "The replay diagnostics show suite setup hooks failed before any leaf tests ran: "
                + json.dumps(setup_failures, ensure_ascii=False)
                + ". This is not evidence that Base violates or Gold satisfies a product behavior. "
                "Repair setup data only where it belongs to the emitted verifier; do not edit, "
                "remove, rename, or weaken original P2P tests. If an original-suite hook remains "
                "blocked, report it as an execution blocker and keep the task unaccepted. Require "
                "actual leaf-test results and the full Base FAIL / Gold PASS contract before acceptance."
            )
        aliases = evidence.get("selector_name_diagnostics") or []
        if aliases:
            objectives.append(
                "The original P2P selectors must remain byte-for-byte identical and in their "
                "original order. Do not rename, map, exclude, or replace them based on collected "
                "test names; only change historical F2P verifier tests. Observed native selector "
                "names are diagnostics only: never fabricate a PASS for a canonical selector "
                "from a same-file/same-leaf match; report the exact observed names and statuses. "
                "Report the Base/Gold runner failure as evidence. Findings: "
                + " | ".join(str(item) for item in aliases[:4])
            )
    if failed_gate == "artifact_contract":
        artifact = evidence.get("artifact_contract")
        contract = artifact.get("contract") if isinstance(artifact, dict) else None
        errors = contract.get("errors", []) if isinstance(contract, dict) else []
        error_text = "\n".join(str(item) for item in errors)

        if "unresolved scaffold" in error_text:
            objectives.append(
                "Replace every unresolved scaffold value across all eight formal artifacts; "
                "do not leave draft, pending, placeholder, skeleton, or TODO content merely "
                "to satisfy file or row counts."
            )
        if "specification_proposal must state the chosen observable behavior declaratively" in error_text:
            objectives.append(
                "Rewrite each rejected specification_proposal as one concise declarative "
                "product requirement that states the historical observable condition and "
                "outcome. Remove meta-language such as specify/clarify/whether/e.g. and do "
                "not list alternative outcomes; the text is copied verbatim into final P."
            )
        if "meta-language into specification addendum" in error_text or "meta-language rather than a chosen observable behavior" in error_text:
            objectives.append(
                "A solver-facing specification addendum may state only a concrete observable "
                "product behavior. Remove historical-test, verifier, Gold, and internal-probe "
                "commentary from the proposal. If the cited part is only an implementation "
                "or robustness probe, exclude that obligation with evidence while preserving "
                "any separate product behavior; otherwise propose the smallest actual user "
                "condition and outcome. Do not edit the controller-owned addendum directly."
            )
        if "claims a behavior addendum/clarification" in error_text:
            objectives.append(
                "Do not delete the provenance warning while keeping an unsupported hidden "
                "contract. For each cited behavior, either show that the retained Problem "
                "Statement states it, classify an important observable omission as "
                "missing_product_behavior/specification_gap with a minimal behavior-level "
                "proposal, or exclude only a proven pure implementation detail. The controller "
                "will create the real addendum on the next revision."
            )
        if "test_patch.patch" in error_text or "historical test patch" in error_text:
            objectives.append(
                "Remove test_patch.patch from the emitted bundle and remove every verifier-level apply, source, copy, reconstruction, or runtime dependency on it. The controller stages original test source in disposable replay containers; preserve all original P2P selectors unchanged and report execution failures as harness gaps."
            )
        if any(marker in error_text for marker in (
            "task_disposition", "p2p_accounting", "missing fields",
            "behavioral_obligations", "obligation_accounting", "preservation_evidence",
        )):
            objectives.append(
                "Migrate the revision to the current conversion schema: declare task_disposition "
                "and its evidence-based reason, provide preserve_original_verbatim p2p_accounting with excluded=[], and "
                "decompose every historical F2P into behavioral_obligations with one complete "
                "obligation_accounting entry per obligation plus preservation_evidence."
            )
        if not objectives:
            objectives.append(
                "Repair each listed artifact-contract error and reconcile the trace, specification, "
                "self-review, manifest, and verifier bundle without changing accepted behavior scope."
            )
    return objectives


def build_feedback(paths: TaskPaths, revision: Path, failed_gate: str, report: dict[str, Any]) -> dict[str, Any]:
    """Collect actionable evidence from this pipeline invocation only.

    Task-level validation files are mutable compatibility outputs. Reading them
    here can mix a previous revision's semantic verdict with the current
    revision's hard replay. The controller report is the revision-scoped source
    of truth because it is assembled in gate order during one invocation.
    """
    evidence: dict[str, Any] = {}
    for name in (
        "artifact_contract", "semantic_review", "hard_replay", "behavior_role_audit", "stability",
        "positive_qa", "negative_qa",
    ):
        value = report.get(name)
        if value is None:
            continue
        if name == "semantic_review" and isinstance(value, dict):
            value = {key: value.get(key) for key in (
                "verdict", "findings", "unsupported_requirements", "binding_risks",
                "mapping_gaps", "under_conversion", "hidden_contracts",
                "unjustified_drops", "specification_gaps", "rationale",
                "deterministic_binding_gate", "base_repository_probe_summary",
                "focused_error_audit", "focused_counterfactual_audit",
            )}
        if name == "artifact_contract":
            value = _compact_artifact_contract(value)
        elif name in {"hard_replay", "behavior_role_audit", "stability", "positive_qa", "negative_qa"}:
            value = _compact_replay_feedback(value)
        evidence[name] = value
    if failed_gate in {"hard_replay", "stability"}:
        diagnostics = _selector_name_diagnostics(paths, revision)
        if diagnostics:
            evidence["selector_name_diagnostics"] = diagnostics
    return {
        "schema_version": "1.1",
        "failed_gate": failed_gate,
        "revision": str(revision.relative_to(paths.run_root)),
        "instruction": (
            "For specification_enrichment, read intermediate/specification_addendum.md as an audited behavior-level supplement and emit public/observable tests for every important behavior. "
            "For other gates, repair only confirmed verifier or artifact defects. Preserve historical F2P behavioral obligations. Preserve the original P2P selector list exactly and do not exclude or remap entries; never apply the historical test patch from the emitted verifier or introduce an implementation API from Gold."
            if failed_gate == "specification_enrichment" else
            "Repair only confirmed verifier or artifact defects. Preserve Problem Statement semantics and every historical F2P behavioral obligation. Preserve the original P2P selector list exactly, without exclusions or remapping; never make the emitted verifier apply the historical test patch. "
            "When a drop audit says observable behavior remains but Base already satisfies it, rewrite or merge the row through a product boundary that exists and runs in both Base and Gold, keep base_behavior_status=already_satisfies, and use task_disposition=non_discriminative if no retained behavior changes in Gold. "
            "A Base-only boundary that Gold removes is not a stable functional surface. Do not convert this situation into a Gold-only symbol requirement or changed_or_missing claim. "
            "If hard replay reports only missing selectors, first make the verifier retain native runner stdout/stderr under /logs/verifier and print failures; do not guess at the defect. "
            "When one historical F2P mixes product behavior with helper representation or product-invalid inputs, use obligation_accounting: preserve every product_behavior obligation in emitted tests and exclude only separately evidenced implementation_detail obligations. Keep the row as rewrite or merge; do not drop it wholesale. "
            "Use this revision's gate evidence as the actionable repair source. Earlier gates have already passed on this revision before the current gate ran; do not carry forward rejected findings from older revisions as new requirements. Preserve the validated behavior already present in the seeded artifacts while repairing the current defect."
        ),
        "repair_objectives": _repair_objectives(failed_gate, evidence),
        "gate_evidence": evidence,
        "pipeline_status": report.get("status"),
    }


def write_feedback(paths: TaskPaths, revision: Path, failed_gate: str, report: dict[str, Any], next_revision_path: Path) -> Path:
    payload = build_feedback(paths, revision, failed_gate, report)
    global_path = paths.validation_root / "repair_feedback.json"
    global_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    global_path.write_text(text, encoding="utf-8")
    (next_revision_path / "repair_feedback.json").write_text(text, encoding="utf-8")
    return global_path
