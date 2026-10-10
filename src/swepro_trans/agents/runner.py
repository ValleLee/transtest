"""Run the model-driven Converter against one Harbor task revision.\n\nThe deterministic controller owns revision validation and packaging. This\nentrypoint owns only one mini-SWE-agent session and writes its trajectory and\nsubmitted artifact into the requested revision directory.\n"""
from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import tempfile
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from minisweagent.agents.default import DefaultAgent

from ..paths import PROJECT_ROOT, canonical_path, resolve_task
from ..conversion_schema import (
    BOOLEAN_LITERAL_FIELDS,
    P2P_POLICY,
    REQUIRED_F2P_FIELDS,
    classification_errors,
    coerce_boolean_literal,
    converted_selector_groups,
    canonical_retained_p2p,
    append_f2p_regressions,
    trace_disposition_errors,
)
from .mini_swe_session import (
    MiniSWEEnvironment,
    OpenAICompatibleMiniModel,
    SUBMIT_SENTINEL,
    _converter_finalization_issues,
    _formal_output_digest,
    _missing_converter_skeleton,
    _verifier_test_digest,
    _write_workspace_layout,
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_env(path: Path, config: dict[str, Any] | None = None) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f"credentials file not found: {path}; copy .env.example to .env")
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip().upper()] = value.strip().strip('"').strip("'")
    model_defaults = (config or {}).get("model", {}) if isinstance(config, dict) else {}
    def value(name: str, default: str = "") -> str:
        return values.get(name, values.get("DEFAULT_" + name, default))
    return {
        "backend": value("BACKEND", "openai_compatible"),
        "base_url": value("BASE_URL"),
        "api_key": value("API_KEY"),
        "model": value("MODEL"),
        "request_timeout_seconds": value("REQUEST_TIMEOUT_SECONDS", str(model_defaults.get("request_timeout_seconds", 300))),
        "max_tokens": value("MAX_TOKENS", str(model_defaults.get("max_tokens", 6144))),
    }


def _parse_selector_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(value)
            except Exception:
                continue
            if isinstance(parsed, (list, tuple)):
                return [str(item) for item in parsed]
    return []


def _seed_converter_inventory(revision: Path, selectors: list[str]) -> bool:
    """Seed only the mechanical source-selector inventory for an empty revision.

    The Converter still has to determine every behavior, decision and emitted
    test. Pending values deliberately fail the semantic/finalization gates.
    """
    trace_path = revision / "conversion_trace.json"
    if trace_path.exists():
        return False
    rows = []
    for selector in selectors:
        row: dict[str, Any] = {key: "pending" for key in REQUIRED_F2P_FIELDS}
        row.update({
            "source_f2p": selector,
            "behavioral_obligations": [],
            "obligation_accounting": [],
            "emitted_tests": [],
        })
        rows.append(row)
    trace = {
        "schema_version": "1.1",
        "specification_source": "source/problem_statement.md",
        "f2p_accounting": rows,
        "task_disposition": "pending",
        "task_disposition_reason": "pending",
        "p2p_accounting": {"policy": P2P_POLICY, "excluded": []},
        "revision_id": revision.name,
    }
    trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def _seed_harbor_test_scaffold(task_root: Path, revision: Path) -> list[str]:
    """Copy reusable Harbor runner inputs as editable Converter drafts.

    The historical test patch and test.sh are deliberately excluded: the
    latter may reset source files or apply the historical patch. The Converter
    must still author the functional tests and final entrypoint.
    """
    original_tests = resolve_task(task_root).original / "tests"
    seeded: list[str] = []
    for name in ("run_script.sh", "parser.py", "config.json"):
        source = original_tests / name
        target = revision / "tests" / name
        if not source.is_file() or target.exists():
            continue
        data = source.read_bytes()
        if name != "config.json" and b"test_patch.patch" in data:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        seeded.append(f"tests/{name}")
    return seeded


def _is_seed_only_revision(revision: Path) -> bool:
    """A mechanical selector inventory is not a partial Converter solution."""
    trace_path = revision / "conversion_trace.json"
    try:
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    rows = trace.get("f2p_accounting", []) if isinstance(trace, dict) else []
    return (
        isinstance(rows, list)
        and bool(rows)
        and trace.get("task_disposition") == "pending"
        and all(isinstance(row, dict) and row.get("behavior_intent") == "pending" for row in rows)
        and not (revision / "tests" / "test.sh").exists()
    )


def _requires_partial_completion(revision: Path, existing_count: int, required_count: int) -> bool:
    """A seeded repair revision is partial even if its inherited trace is pending."""
    return (
        0 < existing_count < required_count
        and (not _is_seed_only_revision(revision) or (revision / "repair_feedback.json").is_file())
    )


def _reconcile_derived_test_config(task_root: Path, revision: Path, trace: dict[str, Any]) -> dict[str, Any]:
    """Derive selector lists from their authoritative semantic/source records."""
    paths = resolve_task(task_root)
    config_path = revision / "tests" / "config.json"
    if not config_path.is_file():
        raise RuntimeError("submitted revision is missing tests/config.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise RuntimeError("tests/config.json must contain an object")

    delta_selectors, regression_selectors = converted_selector_groups(trace)
    overlap = sorted(set(delta_selectors) & set(regression_selectors))
    if overlap:
        raise RuntimeError(
            "converted selectors cannot serve both functional-delta and Base-regression roles: "
            + ", ".join(overlap[:10])
        )

    original_config_path = paths.original / "tests" / "config.json"
    original_config = json.loads(original_config_path.read_text(encoding="utf-8"))
    original_p2p = _parse_selector_list(
        original_config.get("pass_to_pass", original_config.get("pass_to_pass_tests", []))
    )
    p2p_accounting = trace.get("p2p_accounting", {})
    retained_native_p2p, mapping_errors = canonical_retained_p2p(original_p2p, p2p_accounting)
    if mapping_errors:
        raise RuntimeError("; ".join(mapping_errors))
    retained_p2p = append_f2p_regressions(retained_native_p2p, regression_selectors)

    before_f2p = _parse_selector_list(config.get("fail_to_pass", []))
    before_p2p = _parse_selector_list(config.get("pass_to_pass", config.get("pass_to_pass_tests", [])))
    config["fail_to_pass"] = delta_selectors
    config["pass_to_pass"] = retained_p2p
    config.pop("pass_to_pass_tests", None)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "fail_to_pass_changed": before_f2p != delta_selectors,
        "pass_to_pass_changed": before_p2p != retained_p2p,
        "fail_to_pass_count": len(delta_selectors),
        "pass_to_pass_count": len(retained_p2p),
        "converted_regression_count": len(regression_selectors),
    }


def _image(task_root: Path) -> str:
    paths = resolve_task(task_root)
    config = tomllib.loads((paths.original / "task.toml").read_text(encoding="utf-8"))
    image = config.get("environment", {}).get("docker_image")
    if not image:
        raise ValueError("original/task.toml has no environment.docker_image")
    return str(image)


def _prepare_sandbox(task_root: Path, sandbox: Path, revision: Path) -> list[tuple[Path, str, str]]:
    """Prepare the minimal Harbor-to-Harbor Converter boundary."""
    paths = resolve_task(task_root)
    source, original = paths.source, paths.original
    for required in (source / "problem_statement.md", original / "tests", original / "solution"):
        if not required.exists():
            raise FileNotFoundError(f"missing Converter evidence: {required}")

    evidence = sandbox / "evidence"
    reference = sandbox / "reference"
    run = sandbox / "run"
    scratch = sandbox / "scratch"
    for directory in (evidence, reference, run, scratch):
        directory.mkdir(parents=True, exist_ok=True)
    # The image repository is at /app (or /testbed), while the logical
    # workspace is a host-mounted directory. Pre-create links in that host
    # directory so an unprivileged container user does not need to write into
    # the image's root-owned /workspace directory.
    for name, target in (("app", "/app"), ("testbed", "/testbed")):
        link = sandbox / name
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(target)
    revision.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source / "problem_statement.md", evidence / "problem_statement.md")
    for name in ("requirements.md", "interface.md", "dataset_row.json", "instruction_policy.json"):
        item = source / name
        if item.is_file():
            shutil.copy2(item, evidence / name)
    # A controller-generated addendum is behavior-level task context, not a
    # hidden API contract. It is copied only after the prior revision recorded
    # a specification gap and the controller explicitly promoted the proposal.
    addendum = paths.specification_addendum_path
    if addendum.is_file():
        shutil.copy2(addendum, evidence / "specification_addendum.md")
    shutil.copytree(original / "tests", evidence / "historical_tests", dirs_exist_ok=True)
    shutil.copy2(original / "task.toml", evidence / "task.toml")
    for name in ("gold_patch.diff", "solve.sh"):
        item = original / "solution" / name
        if item.is_file():
            shutil.copy2(item, evidence / name)

    taxonomy = PROJECT_ROOT / "docs" / "references" / "deepswe_verifier_taxonomy.md"
    if taxonomy.is_file():
        shutil.copy2(taxonomy, reference / taxonomy.name)
    run.joinpath("metadata.json").write_text(
        json.dumps({"docker_image": _image(task_root), "instance_id": paths.instance_id}, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_workspace_layout(sandbox, "converter")
    return [
        (sandbox, "/workspace", "rw"),
        (evidence, "/workspace/evidence", "ro"),
        (reference, "/workspace/reference", "ro"),
        (run, "/workspace/run", "ro"),
        (scratch, "/workspace/scratch", "rw"),
        (revision, "/solution", "rw"),
        (sandbox / "WORKSPACE_LAYOUT.md", "/workspace/WORKSPACE_LAYOUT.md", "ro"),
    ]


def _normalize_revision_outputs(task_root: Path, revision: Path) -> dict[str, Any]:
    """Normalize the model's trace into the controller schema and register it.\n\n    Models sometimes emit the required F2P rows as a bare JSON array.  The\n    controller keeps one stable object schema so validation and later QA do\n    not depend on that presentation detail.\n    """
    trace_path = revision / "conversion_trace.json"
    if not trace_path.is_file():
        raise RuntimeError("submitted revision is missing conversion_trace.json")
    raw = json.loads(trace_path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        rows = raw
    elif isinstance(raw, dict):
        rows = raw.get("f2p_accounting") or raw.get("f2p_mappings") or raw.get("rows") or []
    else:
        raise RuntimeError("conversion_trace.json must be an object or F2P row array")
    required = set(REQUIRED_F2P_FIELDS)
    allowed_decisions = {"rewrite", "merge", "drop", "specification_gap"}
    if any(not isinstance(row, dict) or not required.issubset(row) for row in rows):
        raise RuntimeError(
            "conversion_trace.json rows must include source_f2p, behavior_intent, "
            "functional_surface, evidence, decision, emitted_tests, and rationale"
        )
    for row in rows:
        # Mini-SWE agents occasionally serialize an otherwise unambiguous
        # boolean as a quoted JSON literal. Normalize only strictly boolean
        # schema fields. Descriptive or uncertain text stays unchanged and is
        # rejected by the validation gate below.
        for field in BOOLEAN_LITERAL_FIELDS:
            if field in row:
                row[field] = coerce_boolean_literal(row[field])
        if row["decision"] not in allowed_decisions:
            raise RuntimeError(f"unsupported F2P decision: {row['decision']!r}")
        classification_problems = classification_errors(row)
        if classification_problems:
            raise RuntimeError("; ".join(classification_problems))
        if row["decision"] in {"rewrite", "merge"} and not row["emitted_tests"]:
            raise RuntimeError(f"{row['decision']} F2P row has no emitted_tests: {row['source_f2p']}")
        if row["decision"] == "drop":
            missing_drop = [key for key in ("drop_justification", "drop_evidence") if not str(row.get(key, "")).strip()]
            if missing_drop:
                raise RuntimeError(f"drop row {row['source_f2p']} is missing: {', '.join(missing_drop)}")
        if row["decision"] == "specification_gap":
            missing_gap = [
                key for key in ("specification_gap", "specification_proposal", "planned_observable_surface")
                if not str(row.get(key, "")).strip()
            ]
            if missing_gap:
                raise RuntimeError(
                    f"specification_gap row {row['source_f2p']} is missing: {', '.join(missing_gap)}"
                )
    normalized = {
        "schema_version": "1.1",
        "specification_source": "source/problem_statement.md",
        "f2p_accounting": rows,
        "task_disposition": (raw.get("task_disposition") if isinstance(raw, dict) else None),
        "task_disposition_reason": (raw.get("task_disposition_reason") if isinstance(raw, dict) else ""),
        # P2P is controller-owned evidence: preserve the original selector list
        # verbatim and ignore any converter attempt to rename or exclude it.
        "p2p_accounting": {"policy": P2P_POLICY, "excluded": []},
        "revision_id": revision.name,
        "normalized_at_utc": _now(),
    }
    disposition_problems = trace_disposition_errors(normalized)
    if disposition_problems:
        raise RuntimeError("; ".join(disposition_problems))
    config_reconciliation = _reconcile_derived_test_config(task_root, revision, normalized)
    trace_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    controller_path = resolve_task(task_root).conversion_trace_path
    controller = json.loads(controller_path.read_text(encoding="utf-8")) if controller_path.is_file() else {}
    controller["f2p_accounting"] = rows
    revisions = [item for item in controller.get("revisions", []) if item.get("revision") != revision.name]
    revisions.append({"revision": revision.name, "status": "submitted", "f2p_count": len(rows), "submitted_at_utc": _now()})
    controller["revisions"] = revisions
    controller["specification_source"] = "source/problem_statement.md"
    controller_path.write_text(json.dumps(controller, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"f2p_count": len(rows), "trace": str(trace_path), "config_reconciliation": config_reconciliation}


def run_session(task_root: Path, revision: Path, credentials: dict[str, str], config: dict[str, Any]) -> dict[str, Any]:
    paths = resolve_task(task_root)
    task_root = paths.run_root
    session_root = paths.converter_root / "agent_sessions"
    session_root.mkdir(parents=True, exist_ok=True)
    sandbox = Path(tempfile.mkdtemp(prefix="converter_", dir=session_root))
    trajectory = paths.trajectory_root / f"{revision.name}_{sandbox.name}.json"
    trajectory.parent.mkdir(parents=True, exist_ok=True)
    environment: MiniSWEEnvironment | None = None
    try:
        mounts = _prepare_sandbox(task_root, sandbox, revision)
        model = OpenAICompatibleMiniModel(
            base_url=credentials["base_url"], api_key=credentials["api_key"],
            model=credentials["model"],
            timeout=int(credentials["request_timeout_seconds"]),
            max_tokens=int(credentials["max_tokens"]),
        )
        original_config = json.loads((paths.original / "tests" / "config.json").read_text(encoding="utf-8"))
        source_f2p = _parse_selector_list(original_config.get("fail_to_pass", []))
        required_f2p_count = len(source_f2p)
        _seed_converter_inventory(revision, source_f2p)
        _seed_harbor_test_scaffold(task_root, revision)
        environment = MiniSWEEnvironment(
            sandbox, _image(task_root), mounts,
            timeout=int(config["agent"].get("tool_timeout_seconds", 180)),
            role="converter",
            # The artifact-first contract is intentionally an early, fixed
            # controller reminder. A percentage of a large turn budget arrives
            # too late after the model has spent the session on exploration.
            progress_reminder_step=max(1, int(config["agent"].get("artifact_first_reminder_step", 8))),
            artifact_checkpoint_step=max(1, int(config["agent"].get("artifact_skeleton_deadline_step", 12))),
            artifact_finalization_step=max(1, int(config["agent"].get("artifact_finalization_deadline_step", 40))),
            formal_output_root=revision,
            required_f2p_count=required_f2p_count,
        )
        prompt_path = Path(config.get("prompts", {}).get("converter", "prompts/converter.md"))
        if not prompt_path.is_absolute(): prompt_path = PROJECT_ROOT / prompt_path
        prompt = prompt_path.read_text(encoding="utf-8")
        system = prompt + "\n\nEvery response must contain one bash tool call. When complete, execute " + SUBMIT_SENTINEL + " as a standalone command."
        task = (
            "Build or repair the functional verifier revision. Read evidence/problem_statement.md as the base specification. If evidence/specification_addendum.md exists, it is an audited behavior-level supplement generated from prior F2P proposals and is part of the effective instruction; do not name implementation APIs in it. "
            "Use evidence/ for construction evidence and reference/deepswe_verifier_taxonomy.md only as design guidance. "
            "The mini-swe shell starts in /workspace and accepts relative paths: inspect the repository with cd app or cd testbed, read evidence/ and reference/ from the workspace root, and write only under solution/. Do not use host paths, absolute /workspace paths, or parent traversal. "
            "The final Harbor verifier bundle is mounted read-only at /tests. Never write logs, parser output, caches, or generated tests under /tests; use /tmp or the writable log mount. If native test discovery requires a generated test inside the repository, use a collision-free path or back up any existing file and restore it in an EXIT trap. The verifier must leave the repository working tree exactly as it found it. The controller stages the original test patch only in disposable Base/Gold replay containers so unchanged original P2P test sources are executable. Never bundle, apply, or depend on that patch from the emitted verifier. Copy the original pass_to_pass selector list exactly, in the same order, into the final verifier. Never rename, remap, omit, exclude, or add items to the original P2P list. Convert only historical F2P tests; converted F2P regressions may be appended after the untouched original P2P list. Declare p2p_accounting policy preserve_original_verbatim with excluded=[] and do not add retained or converted selector mappings. "
            "For result dictionaries or other mappings, do not assert whole-object equality against a fixture unless the effective Problem Statement explicitly requires a closed exact result. Assert each required observable field and its value; allow additional valid fields when P leaves the result open, and submit this risk to focused counterfactual review. "
            "For negative or invalid-input obligations, assert the required public rejection or no-value outcome. Merely asserting that the raw invalid input is absent can pass if the product silently substitutes another incorrect value; test that counterfactual during self-review while retaining the historical F2P scope. "
            "When P promises a warning or notification for each failure, test the required causal warnings without imposing an exact total or one-call ceiling unless P rules out extra useful warnings. A conforming implementation may emit the required per-event warnings plus a summary. Do not assert internal command-helper spy calls when public results and warnings already prove the historical behavior. Counterfactually review this case before submission. "
            "Write only the revision artifact under /solution: tests/test.sh, tests/run_script.sh, tests/parser.py, tests/config.json, "
            "conversion_trace.json, functional_specification.md (a non-normative specification proposal record), self_review.md, and manifest.json. Account for every historical fail_to_pass selector. "
            "The controller has preseeded solution/conversion_trace.json with every historical F2P selector and deliberately unresolved values. Read that inventory; replace every pending value with evidence-backed decisions, create the remaining verifier files, and start writing formal output early. Do not spend the whole session on broad repository listings or scratch experiments. Before any model step limit, leave the latest complete artifact in solution/ so deterministic gates can inspect it. "
            "Do not create output inside the repository and do not rewrite instruction.md. "
            "do not use host paths, and do not install dependencies. Treat requirements/interface as discovery evidence only: "
            "a Base-existing surface is valid when public and behaviorally supported; a new public type explicitly named by P is relevant only when historical F2P covers behavior involving it; "
            "Classify every F2P explicitly as exactly one of p_supported_behavior, base_regression_behavior, missing_product_behavior, or implementation_detail. p_supported_behavior means P already states the behavior and requires rewrite or merge to a public/observable surface. base_regression_behavior means P does not add that requirement but the historical F2P protects public behavior already present in Base; rewrite or merge it through that Base boundary with base_behavior_status=already_satisfies and do not expand P. missing_product_behavior means the behavior is a real product contract absent from P and changed or missing in Base, so it requires specification_gap plus a behavior-level proposal; do not emit a final verifier for that row until the next revision receives the addendum. implementation_detail means the assertion has no independent product behavior and requires a justified drop. A row that contains any meaningful product behavior is not implementation_detail merely because it also touches an internal helper. A Gold-introduced helper is implementation_detail only when removing the helper mechanism leaves no independent behavioral assertion. A representation change does not erase behavior: when an internal empty collection corresponds to a stable public None, empty result, or absent field, rewrite or merge the row to assert that public no-value outcome and exclude only the container/type representation. Similar coverage in another F2P or retained P2P is not sufficient reason to drop: use merge and map the row to a shared public-boundary test, or emit a focused public-boundary edge-case test. "
            "When an important product behavior is absent from Problem Statement, record a specification_gap and behavior-level proposal; the controller will create an audited instruction addendum and ask for a fresh revision, so do not invent a hidden API. Do not add class names, methods, module paths, signatures, type-existence checks, exact implementation formats, or Gold details to the proposal. Every F2P must finish as rewrite, merge, drop, or specification_gap; the classification and decision must obey the four-way mapping. "
            "Every F2P row must include behavior_intent, historical_behavior, behavioral_obligations, obligation_accounting, preservation_evidence, functional_surface, evidence, problem_statement_support, behavior_classification, binding_detected, base_repo_observable, base_behavior_status, gold_only_binding, observable_surface, decision, emitted_tests, rationale, specification_gap, specification_proposal, planned_observable_surface, drop_justification, and drop_evidence. Give each behavioral obligation one obligation_accounting entry. Preserve product_behavior obligations in emitted tests; isolate an internal representation, helper-only guarantee, or explicitly product-invalid input as implementation_detail/excluded with concrete evidence. A mixed row remains rewrite or merge and may exclude only its implementation aspects. Map every product obligation to emitted tests without semantic substitution; the union of preserved obligation selectors must equal row emitted_tests, and changed_or_missing rewrite/merge selectors must exactly equal config fail_to_pass, while already_satisfies/base_regression_behavior selectors must be appended to config pass_to_pass after the retained original P2P selectors. Set task_disposition=convertible only when at least one P-supported retained observable behavior is changed_or_missing in Base; otherwise use non_discriminative and do not manufacture a Gold-only requirement. The controller verifies every already_satisfies/changed_or_missing claim from per-selector Base replay. Keep their emitted selectors separate so one failing delta cannot mask a passing converted regression. "
            "For non_discriminative revisions, every emitted observation surface must exist and preserve the same product behavior in both unmodified Base and Gold. A Base helper removed or replaced by Gold is one-sided and invalid even if its name is public; an unnamed Gold-only replacement is equally invalid. A P-named type is a possible functional delta only when historical F2P covers behavior involving it; do not add coverage from P alone. Prefer a shared higher-level product boundary only for behavior P does not tie to the new type. If no common surface preserves a helper-specific representation or extra input domain, account that aspect separately as implementation_detail/excluded instead of selecting a one-sided helper. "
            "A new public class or type named in P needs a behavioral test only when a historical F2P obligation covers behavior involving it; do not add a test from P alone. Do not require an exact method, module path, constructor signature, or format found only in Requirements, Interface, Gold, or historical tests. If P leaves access unspecified, tolerate plausible public access patterns. "
            "A helper existing in Base is not automatically a public observation boundary. For UI behavior, assert rendered accessible output, control state, navigation, persisted state, or an externally visible service effect. Do not replace a visible result with a spy on an internal modal/dialog factory, router helper, store dispatcher, component method, or exact internal callback shape when the product result can be observed. "
            "Then run the explicit completion sentinel."
        )
        task = (
            "FIRST MILESTONE: Read evidence/problem_statement.md, "
            "evidence/historical_tests/config.json, and "
            "evidence/historical_tests/test_patch.patch; inspect the actual Base "
            "source test function for every F2P selector, including all table rows, "
            "nested subtests, parameterized cases, and distinct outcomes. The patch "
            "is a delta to the original source, not a complete test inventory. Record "
            "a case-by-case inventory in self_review.md before submission. Inspect "
            "only the Base product entrypoints needed for these selectors. The Gold patch is "
            "evidence/gold_patch.diff, and R/I are evidence/requirements.md and "
            "evidence/interface.md. Do not guess evidence paths or repeat broad "
            "repository listings. Write an initial executable verifier in "
            "solution/tests/ and start filling the preseeded "
            "solution/conversion_trace.json before further exploratory reads; "
            "then revise both against the remaining evidence. The initial test "
            "may be imperfect: the independent semantic and Docker gates will "
            "return specific repair feedback. Source F2P selectors: "
            + json.dumps(source_f2p, ensure_ascii=False)
            + ".\n\n" + task
        )
        if config["agent"].get("focused_converter_task", False):
            task = (
                "Convert this Harbor verifier. P is evidence/problem_statement.md. "
                "The historical F2P selector inventory is preseeded in "
                "solution/conversion_trace.json: "
                + json.dumps(source_f2p, ensure_ascii=False)
                + ". Read evidence/historical_tests/config.json and relevant hunks "
                "of evidence/historical_tests/test_patch.patch, then open the actual "
                "Base source function for each F2P selector. Enumerate every table row, "
                "subtest, parameterized case, and distinct outcome in self_review.md; "
                "the patch alone is not the full historical test. After focused Base "
                "entrypoint inspection, write solution/tests/test.sh and the first "
                "public-behavior test before any broad repository exploration. "
                "The original Harbor runner/parser/config in solution/tests/ are "
                "editable drafts; remove historical patch dependencies. Then "
                "complete all F2P mapping rows and required revision artifacts, "
                "self-review, and submit."
            )
        resume_required = (
            revision / "conversion_trace.json",
            revision / "functional_specification.md",
            revision / "self_review.md",
            revision / "manifest.json",
            revision / "tests" / "test.sh",
            revision / "tests" / "run_script.sh",
            revision / "tests" / "parser.py",
            revision / "tests" / "config.json",
        )
        existing_count = sum(path.is_file() and path.stat().st_size > 0 for path in resume_required)
        session_step_limit = int(config["agent"].get("max_turns", 160))
        if _requires_partial_completion(revision, existing_count, len(resume_required)):
            missing = [str(path.relative_to(revision)) for path in resume_required if not path.is_file() or path.stat().st_size == 0]
            task = (
                "Resume the existing partial revision mounted at /solution. "
                "Preserve sound completed artifacts and do not repeat broad repository exploration. "
                f"Complete these missing artifacts: {missing}. "
                "Reconcile all eight required artifacts against the source F2P list and current converter rules, "
                "run focused syntax/static checks, and execute " + SUBMIT_SENTINEL + " as a standalone command."
            )
            session_step_limit = int(config["agent"].get("artifact_completion_turns", 50))
            # A repair seeded from an incomplete first revision otherwise
            # inherits a pending trace and looks like a fresh seed. Require
            # actual progress on missing files; editing the preseeded trace
            # alone must not release this checkpoint for the whole session.
            environment.partial_missing_baseline = set(_missing_converter_skeleton(revision))
            environment.partial_progress_action = 0
            environment.partial_write_interval = max(
                1, int(config["agent"].get("repair_write_deadline_step", 8))
            )
        feedback_candidates = [
            revision / "repair_feedback.json",
            paths.validation_root / "repair_feedback.json",
            paths.semantic_review_path,
        ]
        active_feedback_path = next(
            (feedback_path for feedback_path in feedback_candidates if feedback_path.is_file()),
            None,
        )
        has_repair_feedback = active_feedback_path is not None
        scaffold_issues = _converter_finalization_issues(revision)
        if (
            not has_repair_feedback
            and existing_count == len(resume_required)
            and scaffold_issues
        ):
            environment.artifact_finalization_step = min(
                environment.artifact_finalization_step or 20,
                max(1, int(config["agent"].get("artifact_resume_finalization_step", 20))),
            )
            session_step_limit = int(config["agent"].get("artifact_completion_turns", 50))
            system += (
                "\n\nACTIVE SCAFFOLD COMPLETION MODE: /solution contains all eight files but "
                "still has unresolved TODO/placeholder content. Replace it in place. Do not "
                "repeat broad repository or git exploration. Begin editing no later than the "
                "configured finalization checkpoint."
            )
            task = (
                "Resume the existing Converter skeleton mounted at /solution. Resolve these "
                "scaffold findings: " + "; ".join(scaffold_issues) + ". Use the existing complete "
                "F2P inventory, replace placeholder verifier code with executable functional "
                "tests, reconcile all eight artifacts, run focused static checks, and execute "
                + SUBMIT_SENTINEL + " as a standalone command."
            )
        verifier_repair_required = False
        if has_repair_feedback and active_feedback_path is not None:
            try:
                feedback_data = json.loads(active_feedback_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                feedback_data = {}
            semantic_evidence = feedback_data.get("gate_evidence", {}).get("semantic_review", {}) if isinstance(feedback_data, dict) else {}
            verifier_repair_required = (
                feedback_data.get("failed_gate") == "semantic_review"
                and isinstance(semantic_evidence, dict)
                and any(semantic_evidence.get(key) for key in ("binding_risks", "hidden_contracts", "under_conversion"))
            )
        if has_repair_feedback and existing_count == len(resume_required):
            environment.repair_write_checkpoint_step = max(
                1, int(config["agent"].get("repair_write_deadline_step", 8))
            )
            environment.formal_output_baseline = _formal_output_digest(revision)
            if verifier_repair_required:
                environment.verifier_write_checkpoint_step = max(
                    1, int(config["agent"].get("repair_write_deadline_step", 8))
                )
                environment.verifier_output_baseline = _verifier_test_digest(revision / "tests")
            session_step_limit = int(config["agent"].get("repair_step_cap", session_step_limit))
            system += (
                "\n\nACTIVE COPY-FORWARD REPAIR MODE: /solution already contains a complete prior revision. "
                "You must edit it in place. Do not run git, inspect dataset_row.json, recount selectors, copy the repository, "
                "create a scratch repository, or run dependency/test commands. Use the existing conversion_trace and config "
                "as the inventory. Read only repair feedback, the existing verifier, and narrowly relevant Base source. "
                "Begin writing the repair no later than your eighth tool call. Deterministic Docker gates will test it after submission."
            )
            task = (
                "Repair the complete verifier already mounted at /solution using the structured feedback below. "
                "Treat /solution/conversion_trace.json and /solution/tests/config.json as the authoritative source-test inventory; "
                "do not reparse or recount dataset_row.json. Within the first 8 tool calls, read repair_feedback.json, "
                "the existing trace, and the relevant existing verifier test, then begin editing /solution. "
                "Do not copy the repository, create a second workspace, install dependencies, or run the full test suite; "
                "the controller runs Docker validation after submission. Inspect only focused Base files needed to replace a "
                "confirmed binding. If Base already satisfies a historical behavior, retain it as already_satisfies when P does not add that requirement. Test a P-named new type only when historical F2P covers behavior involving it; do not add a test from P alone. Preserve unrelated correct artifacts and copy the original P2P selector list verbatim with no remapping or exclusions. Reconcile all eight "
                "artifacts, run syntax/static checks only, and execute " + SUBMIT_SENTINEL + " as a standalone command."
            )
        if active_feedback_path is not None:
            task += (
                "\n\nREPAIR FEEDBACK (address every confirmed finding; do not preserve unsupported requirements):\n"
                + active_feedback_path.read_text(encoding="utf-8")
            )
        environment.start()
        # Reasoning gateways occasionally return several non-tool messages in
        # a row, which mini-swe-agent reports as RepeatedFormatError. Retry a
        # fresh agent session once with an explicit protocol reminder; this is
        # a transport/protocol recovery and does not alter verifier semantics.
        format_retries = max(0, int(config["agent"].get("format_retries", 1)))
        result = None
        for attempt in range(format_retries + 1):
            retry_task = task
            if attempt:
                retry_task += ("\n\nPROTOCOL RECOVERY: the previous session ended with "
                               "RepeatedFormatError. Issue exactly one bash tool call in every response, "
                               "and finish by executing the completion sentinel as a standalone command.")
            output_path = trajectory if attempt == 0 else trajectory.with_name(f"{trajectory.stem}_format_retry{attempt}{trajectory.suffix}")
            result = DefaultAgent(
                model, environment, system_template=system, instance_template="{{task}}",
                step_limit=session_step_limit, cost_limit=0.0,
                max_consecutive_format_errors=int(config["agent"].get("max_consecutive_format_errors", 6)),
                output_path=output_path,
            ).run(task=retry_task)
            if result.get("exit_status") == "Submitted" or result.get("exit_status") != "RepeatedFormatError":
                break
        assert result is not None
        required_artifacts = (
            revision / "conversion_trace.json",
            revision / "functional_specification.md",
            revision / "self_review.md",
            revision / "manifest.json",
            revision / "tests" / "test.sh",
            revision / "tests" / "run_script.sh",
            revision / "tests" / "parser.py",
            revision / "tests" / "config.json",
        )
        artifacts_complete = all(path.is_file() and path.stat().st_size > 0 for path in required_artifacts)
        # A large repository can consume a bounded session while producing a
        # useful partial revision. Resume once in a fresh, short-context agent
        # whose only job is to complete and reconcile /solution. This avoids
        # discarding completed analysis or silently accepting a partial bundle.
        if result.get("exit_status") == "LimitsExceeded" and not artifacts_complete and any(
            path.is_file() and path.stat().st_size > 0 for path in required_artifacts
        ):
            missing = [str(path.relative_to(revision)) for path in required_artifacts if not path.is_file() or path.stat().st_size == 0]
            completion_task = (
                "Resume the existing partial revision already mounted at /solution. "
                "Do not repeat broad repository exploration and do not replace sound completed files. "
                f"Complete these missing artifacts: {missing}. "
                "Then reconcile manifest, self-review, trace, config selectors, and emitted test names; "
                "run only focused syntax/static checks needed for a coherent handoff; finally execute "
                + SUBMIT_SENTINEL + " as a standalone command."
            )
            completion_output = trajectory.with_name(f"{trajectory.stem}_artifact_completion{trajectory.suffix}")
            result = DefaultAgent(
                model, environment, system_template=system, instance_template="{{task}}",
                step_limit=int(config["agent"].get("artifact_completion_turns", 50)), cost_limit=0.0,
                max_consecutive_format_errors=int(config["agent"].get("max_consecutive_format_errors", 6)),
                output_path=completion_output,
            ).run(task=completion_task)
            artifacts_complete = all(path.is_file() and path.stat().st_size > 0 for path in required_artifacts)
        submitted = result.get("exit_status") == "Submitted"
        verifier_unchanged = (
            verifier_repair_required
            and environment.verifier_output_baseline is not None
            and _verifier_test_digest(revision / "tests") == environment.verifier_output_baseline
        )
        # A bounded mini-swe session may write a complete Harbor artifact and
        # hit its turn limit immediately before the sentinel. Validate and
        # continue with deterministic gates instead of discarding that complete
        # submission. Incomplete artifacts remain a hard failure.
        if submitted or artifacts_complete:
            trace_report = _normalize_revision_outputs(task_root, revision)
        else:
            trace_report = None
        report = {
            "status": (
                "repair_no_verifier_change" if verifier_unchanged
                else "submitted" if submitted
                else "submitted_artifacts_after_limit" if artifacts_complete
                else "not_submitted"
            ),
            "instance_id": task_root.name, "revision": revision.name,
            "trajectory": str(trajectory.relative_to(task_root)), "agent": "mini-swe-agent==2.4.6",
            "docker_image": _image(task_root), "submitted_at_utc": _now(),
            "exit_status": result.get("exit_status"),
            "trace_report": trace_report,
        }
        (revision / "agent_session.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if verifier_unchanged:
            raise RuntimeError("semantic binding repair ended without changing the verifier tests")
        if not submitted and not artifacts_complete:
            raise RuntimeError(f"mini-SWE agent did not submit complete artifacts: {result.get('exit_status')!r}")
        return report
    finally:
        if environment is not None:
            environment.close()
        shutil.rmtree(sandbox, ignore_errors=True)
        if session_root.is_dir() and not any(session_root.iterdir()):
            session_root.rmdir()


def _record_agent_state(paths, revision: Path, status: str, **fields: Any) -> None:
    try:
        state = json.loads(paths.state_path.read_text(encoding="utf-8")) if paths.state_path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    state.update({
        "status": status,
        "revision": str(revision.relative_to(paths.run_root)),
        "updated_at_utc": _now(),
        **fields,
    })
    paths.state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = paths.state_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(paths.state_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument("--revision", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs/experiment.yaml")
    parser.add_argument("--dry-run", action="store_true", help="validate mounts and credentials without calling the model")
    args = parser.parse_args(argv)
    args.task_root = canonical_path(args.task_root)
    args.revision = canonical_path(args.revision)
    args.env_file = canonical_path(args.env_file)
    args.config = canonical_path(args.config)
    paths = resolve_task(args.task_root)
    root = paths.run_root
    revision = args.revision.resolve()
    revisions_root = paths.revisions_root.resolve()
    if not revision.is_relative_to(revisions_root):
        raise SystemExit(
            "--revision must be inside the task-root's intermediate/converter/revisions directory"
        )
    config = yaml.safe_load(args.config.resolve().read_text(encoding="utf-8"))
    credentials = _load_env(args.env_file.resolve(), config)
    if not credentials["base_url"] or not credentials["model"] or not credentials["api_key"]:
        raise SystemExit(".env must define DEFAULT_BASE_URL, DEFAULT_MODEL, and DEFAULT_API_KEY")
    if args.dry_run:
        sandbox = Path(tempfile.mkdtemp(prefix="converter_check_", dir=paths.converter_root))
        try:
            mounts = _prepare_sandbox(root, sandbox, revision)
            print(json.dumps({"status": "ready", "docker_image": _image(root), "mount_count": len(mounts)}, indent=2))
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)
        return 0
    _record_agent_state(paths, revision, "converter_running", converter_error="")
    try:
        report = run_session(root, revision, credentials, config)
    except KeyboardInterrupt as exc:
        _record_agent_state(paths, revision, "converter_interrupted", converter_error=repr(exc))
        print(json.dumps({
            "status": "converter_interrupted",
            "revision": str(revision.relative_to(root)),
            "error": repr(exc),
        }, ensure_ascii=False, indent=2))
        return 130
    except Exception as exc:
        _record_agent_state(paths, revision, "converter_failed", converter_error=repr(exc))
        print(json.dumps({
            "status": "converter_failed",
            "revision": str(revision.relative_to(root)),
            "error": repr(exc),
        }, ensure_ascii=False, indent=2))
        return 8
    _record_agent_state(paths, revision, "converter_submitted", converter_error="", converter_status=report.get("status"))
    print(json.dumps(report, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
