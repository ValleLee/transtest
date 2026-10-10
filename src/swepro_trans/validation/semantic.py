#!/usr/bin/env python3
"""Run the read-only semantic Judge before an expensive hard replay.

The Judge receives Problem Statement semantics, the candidate trace/tests, and a
small Base-repository symbol probe. Requirements/interface remain construction
evidence. Only product behaviors represented in the historical F2P scope are
converted; a P-named type alone does not authorize additional test coverage.
"""
from __future__ import annotations
import argparse, ast, hashlib, json, re, shlex, subprocess, tomllib
from pathlib import Path
import yaml

import sys
from swepro_trans.agents.judge import judge, write_judgement
from swepro_trans.agents.runner import _image, _load_env
from swepro_trans.paths import PROJECT_ROOT, canonical_path, resolve_task
from ..conversion_schema import classification_errors, trace_disposition_errors
from .binding_signals import binding_signals as _binding_signals, is_verifier_source, revision_evidence_fingerprint
from .counterfactual import review_counterfactuals



def _normalize_judge_lists(value: object, *fields: str) -> dict:
    """Accept text where Judge was asked for a list, reject other bad shapes."""
    if not isinstance(value, dict):
        raise ValueError("semantic Judge response must be an object")
    for field in fields:
        items = value.get(field)
        if items is None:
            value[field] = []
        elif isinstance(items, str):
            value[field] = [items] if items.strip() else []
        elif not isinstance(items, list):
            raise ValueError(f"semantic Judge {field} must be an array or text")
    return value


def scope_review_findings(value: dict, f2p_rows: list[dict]) -> dict:
    """Do not let P-only omissions become F2P conversion failures.

    Mapping-gap, under-conversion, and specification-gap findings must identify
    a canonical source F2P selector. Unanchored findings are retained as audit
    notes, but cannot block conversion by demanding coverage absent from
    historical F2P.
    """
    selectors = {
        str(row.get("source_f2p", "")).strip()
        for row in f2p_rows if isinstance(row, dict) and row.get("source_f2p")
    }
    out_of_scope: list[dict[str, str]] = []
    scoped_fields = ("mapping_gaps", "under_conversion", "specification_gaps")
    for field in scoped_fields:
        kept = []
        for item in value.get(field, []):
            finding = str(item)
            if any(selector and selector in finding for selector in selectors):
                kept.append(item)
            else:
                out_of_scope.append({"category": field, "finding": finding})
        value[field] = kept
    if not out_of_scope:
        return value

    value.setdefault("out_of_scope_review_findings", []).extend(out_of_scope)
    blocking_fields = (
        "unsupported_requirements", "binding_risks", *scoped_fields,
        "hidden_contracts", "unjustified_drops",
    )
    if (value.get("verdict") == "FAIL"
            and not any(value.get(field) for field in blocking_fields)
            and len(value.get("findings", [])) <= len(out_of_scope)):
        value["verdict"] = "PASS"
        value["findings"] = []
        value["rationale"] = (
            str(value.get("rationale", "")).rstrip()
            + " The only mapping/under-conversion/specification-gap findings lacked a citation to any "
              "historical F2P selector and were retained as out-of-scope review notes."
        ).strip()
    return value

def _read(path: Path, limit: int = 12000) -> str:
    return path.read_text(encoding="utf-8", errors="replace")[:limit] if path.is_file() else ""


def _auditable_revision_tests(
    tests: dict[str, dict[str, object]], *, head_limit: int = 5000
) -> dict[str, dict[str, object]]:
    """Keep every source needed to reconstruct the verifier for Judge review.

    Functional tests are often embedded in run_script.sh and generated under
    /tmp at runtime. Supplying only test.sh and language source files hides
    those bodies from the semantic gate. config.json is also needed to map the
    accounting selectors to the executable command.
    """
    included_suffixes = (
        ".sh", ".py", ".ts", ".tsx", ".js", ".jsx", ".cjs", ".mjs",
        ".cts", ".mts", ".go", ".rs", ".java", ".rb", ".php",
    )
    result: dict[str, dict[str, object]] = {}
    for name, data in tests.items():
        # Every file must appear in the inventory. Otherwise the Judge may
        # mistake an omitted build helper or nested fixture for a missing file.
        entry: dict[str, object] = {
            "sha256": data.get("sha256"),
            "bytes": data.get("bytes"),
        }
        if name.endswith(included_suffixes) or name.endswith("config.json"):
            # Selector manifests must not lose their tail, which may contain
            # converted regression selectors.
            limit = max(head_limit, 20000) if name.endswith("config.json") else head_limit
            entry["head"] = str(data.get("head", ""))[:limit]
        result[name] = entry
    return result


def _compact_semantic_f2p_rows(trace: dict[str, Any], clip) -> list[dict[str, Any]]:
    """Preserve every field the semantic Judge needs to assess row/obligation accounting."""
    row_keys = (
        "source_f2p", "behavior_intent", "historical_behavior", "behavioral_obligations",
        "preservation_evidence", "functional_surface", "behavior_classification",
        "decision", "emitted_tests", "problem_statement_support", "problem_statement_quotes",
        "base_repo_observable", "base_behavior_status", "gold_only_binding",
        "observable_surface", "specification_gap", "specification_proposal",
        "planned_observable_surface", "drop_justification", "drop_evidence",
    )
    obligation_keys = (
        "id", "obligation", "scope", "disposition", "base_behavior_status",
        "emitted_tests", "evidence", "rationale",
    )
    compact_rows = []
    for row in trace.get("f2p_accounting", []):
        if not isinstance(row, dict):
            compact_rows.append(row)
            continue
        compact = {key: clip(row.get(key), 350) for key in row_keys}
        compact["obligation_accounting"] = [
            {key: clip(item.get(key), 350) for key in obligation_keys}
            for item in row.get("obligation_accounting", []) if isinstance(item, dict)
        ]
        compact_rows.append(compact)
    return compact_rows


def _without_comment_only_lines(text: str) -> str:
    """Remove prose comments before executable symbol provenance checks.

    A verifier may name the historical Gold-only helper in an explanatory
    comment while executing only a stable Base/Gold product boundary. Treating
    that prose as a runtime dependency produces a false binding rejection. This
    intentionally keeps strings and executable lines, including dynamic
    getattr/import spellings, so hiding a dependency in data is still caught.
    """
    output: list[str] = []
    in_block = False
    python_doc_quote: str | None = None
    for raw in text.splitlines():
        stripped = raw.lstrip()
        if python_doc_quote is not None:
            if python_doc_quote in stripped:
                remainder = stripped.split(python_doc_quote, 1)[1].strip()
                python_doc_quote = None
                if remainder:
                    output.append(remainder)
            continue
        if stripped.startswith((chr(34) * 3, chr(39) * 3)):
            quote = stripped[:3]
            remainder = stripped[3:]
            if quote not in remainder:
                python_doc_quote = quote
            else:
                trailing = remainder.split(quote, 1)[1].strip()
                if trailing:
                    output.append(trailing)
            continue
        if in_block:
            if "*/" in stripped:
                in_block = False
                remainder = stripped.split("*/", 1)[1].strip()
                if remainder:
                    output.append(remainder)
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped[2:]:
                in_block = True
            else:
                remainder = stripped.split("*/", 1)[1].strip()
                if remainder:
                    output.append(remainder)
            continue
        if stripped.startswith(("#", "//", "<!--", "*")):
            continue
        output.append(raw)
    return "\n".join(output)


def _base_search_terms(term: str) -> list[str]:
    """Return equivalent source spellings for a verifier identifier.

    TypeScript projects using Node ESM commonly import a ``.ts`` source module
    with a runtime ``.js`` suffix.  A literal repository search for that suffix
    therefore reports an existing Base symbol as absent.  Probe the extension
    free identifier and the corresponding TypeScript source suffixes as well.
    """
    terms = [term]
    source_equivalents = {
        ".js": (".ts", ".tsx"),
        ".mjs": (".mts",),
        ".cjs": (".cts",),
        ".jsx": (".tsx",),
    }
    for runtime_suffix, source_suffixes in source_equivalents.items():
        if term.endswith(runtime_suffix):
            stem = term[:-len(runtime_suffix)]
            terms.extend([stem, *(stem + suffix for suffix in source_suffixes)])
            break
    return list(dict.fromkeys(terms))


def _module_source_paths(term: str) -> list[str]:
    """Possible Base source paths for a dotted Python module import.

    Content search alone misses an import that exists only as a filename.
    A module path does not authorize unspecified members under that module.
    """
    stem = term.replace(".", "/")
    return [
        f"{prefix}{stem}{suffix}"
        for prefix in ("", "src/", "lib/")
        for suffix in (".py", "/__init__.py")
    ]


def _p_names_class(name: str, problem_text: str) -> bool:
    """Recognize an expressly named public type, ignoring incidental matches."""
    return bool(re.search(
        rf"(?:`{re.escape(name)}`|\b{re.escape(name)}\s+(?:class|struct|type)\b|\b(?:class|struct|type)\s+{re.escape(name)}\b)",
        problem_text,
    ))


def _p_authorizes_symbol(term: str, problem_text: str, gold_classes: set[str]) -> bool:
    """Accept a P-named class without accepting unspecified members or paths."""
    if term in problem_text:
        return True
    name = term.rsplit(".", 1)[-1]
    return name in gold_classes and "." in term and _p_names_class(name, problem_text)


def _base_probe(image: str, revision: Path, gold_patch: Path) -> dict:
    test_root = revision / "tests"
    evidence_files = [test_root / name for name in ("test.sh", "run_script.sh", "test_patch.patch", "config.json")]
    evidence_files.extend(sorted(test_root.glob("*.py")))
    text = _without_comment_only_lines(
        "\n".join(_read(p, 20000) for p in evidence_files if p.is_file())
    )
    identifiers = []
    ignored_roots = {
        "os", "json", "ast", "sys", "pytest", "typing", "pathlib",
        "subprocess", "dataclasses", "re", "config", "test", "tests",
        "results", "result", "output", "parsed", "families", "parts",
        "value", "values", "name", "items", "entry",
    }
    for value in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*){1,3}\b", text):
        root = value.split(".", 1)[0]
        if root in ignored_roots or value in {"tests.unit.config", "pytest.mark.parametrize"}:
            continue
        if value not in identifiers:
            identifiers.append(value)
    # Dynamic attribute checks are still symbol requirements.  A converter can
    # hide a Gold-only dependency behind getattr/hasattr or a string literal,
    # so normalize those forms into the same qualified-symbol probe.  This is
    # generic across repositories and does not name any task-specific symbol.
    for qualifier, symbol in re.findall(
        r"\b(?:getattr|hasattr)\(\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*,\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]",
        text,
    ):
        value = f"{qualifier}.{symbol}"
        if qualifier.split('.', 1)[0] not in ignored_roots and value not in identifiers:
            identifiers.append(value)
    for module, symbol in re.findall(
        r"\bfrom\s+([A-Za-z_][A-Za-z0-9_.]*)\s+import\s+([A-Za-z_][A-Za-z0-9_]*)",
        text,
    ):
        value = f"{module}.{symbol}"
        if module.split('.', 1)[0] not in ignored_roots and value not in identifiers:
            identifiers.append(value)
    identifiers = identifiers[:120]
    added = [line[1:].strip() for line in _read(gold_patch, 50000).splitlines()
             if line.startswith("+") and not line.startswith("+++")]
    # Gold declarations are usually unqualified (``class Widget``), while a
    # verifier imports them through a qualified name (``module.Widget.call``).
    # Keep declaration names so the provenance check cannot miss that common
    # hidden-contract shape.
    gold_defined = _gold_defined_symbols(added)
    added_source = _without_comment_only_lines("\n".join(added))
    gold_classes = sorted(set(re.findall(
        r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)\b",
        added_source,
    )))
    gold_types = sorted(set(gold_classes) | set(re.findall(
        r"\btype\s+([A-Za-z_][A-Za-z0-9_]*)\b",
        added_source,
    )))
    # Harbor images contain different repositories. Probe the complete git
    # worktree instead of assuming qutebrowser source/test directories;
    # otherwise a symbol that is public in another task would be classified
    # as Base-invisible.
    command_parts = []
    for term in identifiers:
        searches = "; ".join(
            "git grep -n -F -- " + shlex.quote(search_term) + " 2>/dev/null || true"
            for search_term in _base_search_terms(term)
        )
        path_searches = "; ".join(
            "[ -f " + shlex.quote(path) + " ] && printf '%s:1:module source exists\\n' "
            + shlex.quote(path) + " || true"
            for path in _module_source_paths(term)
        )
        command_parts.append(
            "printf '__TERM__%s\\n' " + shlex.quote(term)
            + "; { " + searches + "; " + path_searches + "; } | head -5"
        )
    command = "cd /app 2>/dev/null || cd /testbed 2>/dev/null || exit 91; " + "; ".join(command_parts)
    try:
        result = subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "/bin/bash", image, "-lc", command], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180, check=False)
        output, status = result.stdout[-30000:], ("ok" if result.returncode == 0 else "probe_error")
    except Exception as exc:
        output, status = repr(exc), "probe_error"
    base_present = {}
    for term in identifiers:
        marker = "__TERM__" + term
        section = output.split(marker, 1)[1].split("__TERM__", 1)[0] if marker in output else ""
        base_present[term] = bool(re.search(r"(?:^|\n)[^\n]+:[0-9]+:", section))
    # A use of a qualified expression in Gold does not mean Gold introduced
    # that API. Only declarations added by Gold can establish provenance for
    # this cheap precheck; other cases are left to the semantic Judge.
    gold_only = []
    gold_only_evidence = {}
    for term in identifiers:
        if base_present.get(term):
            continue
        matched = _gold_declaration_matches(term, gold_defined)
        if matched:
            gold_only.append(term)
            gold_only_evidence[term] = sorted(set(matched))
    return {
        "status": status,
        "identifiers": identifiers,
        "base_present": base_present,
        "gold_only_candidates": gold_only,
        "gold_only_evidence": gold_only_evidence,
        "gold_defined_symbols": gold_defined,
        "gold_defined_classes": gold_classes,
        "gold_defined_types": gold_types,
        "base_repo_search": output,
        "gold_added_lines_sample": added[:80],
    }


def _historical_selector_terms(selectors: list[str]) -> list[str]:
    """Return searchable source names for native test selectors.

    Suite selectors often contain subtest suffixes (for example Go's
    ``TestLoad/case_name``); the containing test source is named by the root
    selector. Keep the complete selector too when it may be a literal test
    title or a path-based node id.
    """
    terms: list[str] = []
    for raw in selectors:
        selector = str(raw).strip()
        if not selector:
            continue
        candidates = [selector]
        if "::" in selector:
            candidates.extend(part for part in selector.split("::") if part)
        if "/" in selector:
            candidates.append(selector.split("/", 1)[0])
        for term in candidates:
            if term and term not in terms:
                terms.append(term)
    return terms


def _parse_historical_test_sources(output: str) -> list[dict[str, str]]:
    """Parse bounded source snippets emitted by the Base-image source probe."""
    marker = re.compile(
        r"__HIST_SOURCE_BEGIN__(?P<path>[^\n]+)\n(?P<source>.*?)\n__HIST_SOURCE_END__",
        re.DOTALL,
    )
    return [
        {"path": match.group("path").strip(), "source": match.group("source")}
        for match in marker.finditer(output)
    ]


def _historical_test_patch_paths(patch: str) -> list[str]:
    """Extract test-file paths changed by the historical F2P patch."""
    paths: list[str] = []
    for match in re.finditer(r"^diff --git a/(.+?) b/(.+?)$", patch, re.MULTILINE):
        path = match.group(1)
        if path == "/dev/null":
            path = match.group(2)
        if re.search(r"(^|/)(?:test|tests|spec|specs)(?:/|$)|(?:_test|\.test|\.spec)", path, re.I):
            if path not in paths:
                paths.append(path)
    return paths


def _parse_selector_list(value: object) -> list[str]:
    """Parse selector arrays from native JSON lists or Stage 1 stringified lists.

    Some imported task manifests serialize ``fail_to_pass`` as the textual
    representation of a JSON/Python list. Treating those values as malformed
    made the semantic Judge receive ``no_selectors`` and omit historical test
    source evidence for otherwise valid tasks.
    """
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    if not isinstance(value, str):
        return []
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(value)
        except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, (list, tuple)):
            return [str(item) for item in parsed]
    return []


def _historical_test_source_probe(image: str, selectors: list[str], test_patch: str = "") -> dict:
    """Read source-level historical tests from the task's immutable Base image.

    The selector manifest and test patch do not contain unchanged table-driven
    cases. Supplying matched source files lets the semantic Judge verify the
    converter's case inventory instead of trusting self-reported trace prose.
    """
    terms = _historical_selector_terms(selectors)
    patch_paths = _historical_test_patch_paths(test_patch)
    if not terms and not patch_paths:
        return {"status": "no_selectors", "selectors": [], "patch_paths": [], "sources": []}
    searches = " ; ".join(
        "git grep -l -I -F -e " + shlex.quote(term) + " 2>/dev/null || true"
        for term in terms
    ) or "true"
    patch_file_search = "for __f in " + " ".join(shlex.quote(path) for path in patch_paths) + "; do git cat-file -e \"HEAD:$__f\" 2>/dev/null && printf '%s\n' \"$__f\"; done"
    command = (
        "cd /app 2>/dev/null || cd /testbed 2>/dev/null || exit 91; "
        "__files=$( { " + searches + "; " + patch_file_search + "; } | sort -u); __count=0; "
        "while IFS= read -r __f; do "
        "case \"$__f\" in *test*|*Test*|*spec*|*Spec*) ;; *) continue;; esac; "
        "printf '__HIST_SOURCE_BEGIN__%s\n' \"$__f\"; "
        "git show \"HEAD:$__f\" 2>/dev/null | head -c 14000; printf '\n__HIST_SOURCE_END__\n'; "
        "__count=$((__count + 1)); [ \"$__count\" -ge 4 ] && break; "
        "done <<< \"$__files\"; exit 0"
    )
    try:
        result = subprocess.run(
            ["docker", "run", "--rm", "--network", "none", "--entrypoint", "/bin/bash", image, "-lc", command],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=120, check=False,
        )
        output = result.stdout[-60000:]
        sources = _parse_historical_test_sources(output)
        if result.returncode != 0:
            status = "probe_error"
        else:
            status = "ok" if sources else "no_matches"
    except Exception as exc:
        output, sources, status = repr(exc), [], "probe_error"
    return {
        "status": status,
        "selectors": selectors,
        "search_terms": terms,
        "patch_paths": patch_paths,
        "sources": sources,
        "source_file_count": len(sources),
        "diagnostic": output[-2000:] if status != "ok" else "",
    }

def _gold_declaration_matches(term: str, gold_defined: list[str]) -> list[str]:
    """Return Gold declarations present in a qualified verifier expression."""
    components = set(term.split("."))
    return [name for name in gold_defined if name in components]


def _gold_defined_symbols(added_lines: list[str]) -> list[str]:
    """Extract declared symbols from added source, including Go types/methods.

    Go methods use ``func (receiver Type) Method(...)`` rather than
    ``def``/``class`` declarations. Omitting their names lets a verifier call
    an API introduced only by Gold without the deterministic Base-provenance
    check noticing that it is one-sided. Named Go types (including structs,
    interfaces, and aliases) also need provenance checks: a generic type name
    may exist elsewhere in the repository while being absent from the package
    imported by the verifier.
    """
    added_source = _without_comment_only_lines("\n".join(added_lines))
    names = set(re.findall(
        r"\b(?:class|def|async\s+def)\s+([A-Za-z_][A-Za-z0-9_]*)",
        added_source,
    ))
    names.update(re.findall(
        r"\bfunc\s*(?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        added_source,
    ))
    names.update(re.findall(
        r"\btype\s+([A-Za-z_][A-Za-z0-9_]*)\b",
        added_source,
    ))
    return sorted(names)


def _should_run_focused_counterfactual(result: dict, *, deterministic_only: bool) -> bool:
    """Collect independent binding findings even when the broad Judge found other defects."""
    return (
        not deterministic_only
        and result.get("verdict") in {"PASS", "FAIL"}
        and result.get("failure_classification") != "judge_transport"
    )


def _merge_focused_counterfactual_audit(result: dict, focused_audit: dict) -> dict:
    """Keep Judge protocol failures out of the Converter defect-repair loop."""
    result["focused_counterfactual_audit"] = focused_audit
    if focused_audit.get("verdict") == "PASS":
        return result

    result["verdict"] = "FAIL"
    result.setdefault("findings", []).extend(
        str(item) for item in focused_audit.get("findings", [])
    )
    if focused_audit.get("review_mode") == "focused_counterfactual_protocol_failure":
        result["review_mode"] = "protocol_failure"
        result["failure_classification"] = "judge_transport"
        return result

    result.setdefault("binding_risks", []).append(
        "Focused counterfactual audit found an implementation-bound verifier assertion"
    )
    return result


def _deterministic_fallback(evidence: dict, protocol_errors: list[str], *, allow_pass: bool = False) -> dict:
    """Reject a revision when the semantic Judge protocol is unavailable.

    Structural checks can reject an unsafe revision, but they cannot prove that
    historical behavior was preserved. A provider timeout or malformed answer
    therefore cannot be promoted to semantic PASS.
    """
    trace = evidence.get("conversion_trace") or {}
    rows = trace.get("f2p_accounting") or []
    failures: list[str] = list(trace_disposition_errors(trace))
    if not rows:
        failures.append("conversion_trace has no F2P accounting rows")
    for row in rows:
        if not isinstance(row, dict):
            failures.append("F2P accounting row is not an object")
            continue
        source = row.get("source_f2p", "<unknown>")
        required = (
            "behavior_intent", "historical_behavior", "behavioral_obligations",
            "obligation_accounting", "preservation_evidence", "functional_surface", "evidence", "problem_statement_support", "problem_statement_quotes",
            "behavior_classification", "binding_detected", "base_repo_observable",
            "base_behavior_status", "gold_only_binding", "observable_surface", "decision", "rationale",
        )
        missing = [name for name in required if name not in row]
        boolean_fields = {"base_repo_observable", "gold_only_binding"}
        invalid_booleans = [
            name for name in boolean_fields if name in row and not isinstance(row.get(name), bool)
        ]
        empty_required = [
            name for name in required if name not in boolean_fields and name in row
            and (row[name] is None or row[name] == "" or row[name] == [] or row[name] == {})
        ]
        if missing:
            failures.append(f"{source}: missing fields {', '.join(missing)}")
        if invalid_booleans:
            failures.append(f"{source}: fields must be boolean: {', '.join(sorted(invalid_booleans))}")
        if empty_required:
            failures.append(f"{source}: empty required values {', '.join(empty_required)}")
        failures.extend(classification_errors(row))
        if row.get("decision") in {"rewrite", "merge"} and not row.get("emitted_tests"):
            failures.append(f"{source}: no emitted tests")
    probe = evidence.get("base_repository_probe") or {}
    if probe.get("status") != "ok":
        failures.append(f"Base repository probe status is {probe.get('status')!r}")
    problem = str(evidence.get("problem_statement", ""))
    gold_types = set(probe.get("gold_defined_classes", [])) | set(probe.get("gold_defined_types", []))
    unauthorized_gold = [
        str(term) for term in probe.get("gold_only_candidates", [])
        if not _p_authorizes_symbol(str(term), problem, gold_types)
    ]
    if unauthorized_gold:
        failures.append("Gold-only symbols remain: " + ", ".join(unauthorized_gold))
    if failures:
        return {
            "verdict": "FAIL",
            "review_mode": "deterministic_rejection",
            "judge_verdict": "FAIL",
            "failure_classification": "artifact_or_binding",
            "findings": failures,
            "unsupported_requirements": [],
            "binding_risks": unauthorized_gold,
            "mapping_gaps": failures,
            "rationale": "The semantic provider did not return usable JSON and deterministic checks found a defect.",
            "judge_protocol_errors": protocol_errors,
        }
    if allow_pass:
        return {
            "verdict": "PASS",
            "review_mode": "deterministic_semantic_audit",
            "judge_verdict": "PASS",
            "failure_classification": "none",
            "findings": [],
            "unsupported_requirements": [],
            "binding_risks": [],
            "mapping_gaps": [],
            "under_conversion": [],
            "hidden_contracts": [],
            "unjustified_drops": [],
            "rationale": "Strict local audit passed: complete classification, emitted-test mapping, Base probe, and no unauthorized Gold-only binding. No LLM semantic verdict was available.",
            "judge_protocol_errors": protocol_errors,
        }
    return {
        "verdict": "FAIL",
        "review_mode": "protocol_failure",
        "judge_verdict": "UNAVAILABLE",
        "failure_classification": "judge_transport",
        "findings": ["Semantic Judge did not return a closed JSON verdict after retries."],
        "unsupported_requirements": [],
        "binding_risks": [],
        "mapping_gaps": [],
        "under_conversion": [],
        "hidden_contracts": [],
        "unjustified_drops": [],
        "rationale": "A semantic PASS cannot be inferred from structural checks when the Judge protocol fails.",
        "judge_protocol_errors": protocol_errors,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-root", type=Path, required=True)
    ap.add_argument("--revision", type=Path, required=True)
    ap.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    ap.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs/experiment.yaml")
    ap.add_argument("--output", type=Path)
    ap.add_argument("--deterministic-only", action="store_true", help="run the strict local semantic audit without calling an LLM endpoint")
    args = ap.parse_args(argv)
    args.task_root = canonical_path(args.task_root)
    args.revision = canonical_path(args.revision)
    args.env_file = canonical_path(args.env_file)
    args.config = canonical_path(args.config)
    paths = resolve_task(args.task_root)
    root, revision = paths.run_root, args.revision
    revisions_root = paths.revisions_root.resolve()
    if not revision.is_relative_to(revisions_root):
        raise SystemExit("--revision must be inside task-root intermediate/converter/revisions")
    credentials = _load_env(args.env_file.resolve())
    config = yaml.safe_load(args.config.resolve().read_text(encoding="utf-8"))
    trace_path = revision / "conversion_trace.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8")) if trace_path.is_file() else {}
    tests = {}
    tests_root = revision / "tests"
    for path in sorted(tests_root.rglob("*")):
        if is_verifier_source(path, tests_root):
            tests[str(path.relative_to(revision))] = {
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "head": _read(path, 20000),
            }
    row_path = paths.source / "dataset_row.json"
    task_image = _image(root)
    # A non-discriminative revision may have a controller-owned pre-semantic
    # Base/Gold replay. Use it only when it belongs to this exact revision;
    # otherwise omit it so stale task-level evidence cannot pollute review.
    hard_replay = None
    if paths.hard_replay_path.is_file():
        try:
            candidate_hard = json.loads(paths.hard_replay_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            candidate_hard = None
        expected_revision = str(revision.relative_to(root)) if revision.is_relative_to(root) else str(revision)
        if isinstance(candidate_hard, dict) and candidate_hard.get("revision") == expected_revision:
            hard_replay = candidate_hard
    behavior_role_audit = None
    if paths.behavior_role_audit_path.is_file():
        try:
            candidate_roles = json.loads(paths.behavior_role_audit_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            candidate_roles = None
        expected_revision = str(revision.relative_to(root)) if revision.is_relative_to(root) else str(revision)
        if isinstance(candidate_roles, dict) and candidate_roles.get("revision") == expected_revision:
            behavior_role_audit = candidate_roles
    full_probe = _base_probe(task_image, revision, paths.original / "solution/gold_patch.diff")
    historical_test_config = json.loads((paths.original / "tests" / "config.json").read_text(encoding="utf-8"))
    historical_f2p = _parse_selector_list(
        historical_test_config.get("fail_to_pass", historical_test_config.get("fail_to_pass_tests", []))
    )
    historical_test_patch = _read(paths.original / "tests" / "test_patch.patch", 24000)
    historical_test_sources = _historical_test_source_probe(task_image, historical_f2p, historical_test_patch)
    evidence = {
        "problem_statement": _read(paths.source / "problem_statement.md", 16000),
        "specification_proposal": _read(revision / "functional_specification.md", 12000),
        "specification_addendum": _read(paths.specification_addendum_path, 16000),
        "requirements_evidence": _read(paths.source / "requirements.md", 12000),
        "interface_evidence": _read(paths.source / "interface.md", 12000),
        "conversion_trace": trace,
        "historical_test_patch": historical_test_patch,
        "historical_test_config": _read(paths.original / "tests" / "config.json", 12000),
        "historical_test_sources": historical_test_sources,
        "revision_tests": tests,
        "implementation_binding_signals": _binding_signals(tests),
        "base_repository_probe": full_probe,
        "hard_replay_summary": hard_replay,
        "behavior_role_audit": behavior_role_audit,
        "dataset_row": json.loads(row_path.read_text()) if row_path.is_file() else None,
    }
    # The complete probe output and test heads remain in the local evidence
    # bundle, but sending all of them to a reasoning model makes it spend the
    # completion budget narrating instead of emitting the required JSON. The
    # Judge only needs the normative text, accounting rows, test fingerprints,
    # and symbol provenance summary.
    judge_evidence = {
        "problem_statement": evidence["problem_statement"],
        "specification_proposal": evidence["specification_proposal"],
        "specification_addendum": evidence["specification_addendum"],
        "requirements_evidence": evidence["requirements_evidence"][:4000],
        "interface_evidence": evidence["interface_evidence"][:4000],
        "conversion_trace": trace,
        "historical_test_patch": evidence["historical_test_patch"],
        "historical_test_config": evidence["historical_test_config"],
        "historical_test_sources": evidence["historical_test_sources"],
        "implementation_binding_signals": evidence["implementation_binding_signals"],
        "revision_tests": {
            name: {key: value for key, value in data.items() if key != "head"}
            | {"head": str(data.get("head", ""))[:16000]}
            for name, data in tests.items()
        },
        "hard_replay_summary": evidence["hard_replay_summary"],
        "behavior_role_audit": evidence["behavior_role_audit"],
        "base_repository_probe": {
            "status": full_probe.get("status"),
            "identifiers": full_probe.get("identifiers", []),
            "base_present": full_probe.get("base_present", {}),
            "gold_only_candidates": full_probe.get("gold_only_candidates", []),
            "gold_added_lines_sample": full_probe.get("gold_added_lines_sample", [])[:20],
        },
        "dataset_row": evidence["dataset_row"],
    }
    def _clip_semantic(value: Any, limit: int = 700) -> Any:
        if isinstance(value, str):
            return value if len(value) <= limit else value[:limit] + "...[clipped]"
        if isinstance(value, list):
            return [_clip_semantic(item, limit) for item in value]
        if isinstance(value, dict):
            return {key: _clip_semantic(item, limit) for key, item in value.items()}
        return value

    compact_rows = _compact_semantic_f2p_rows(trace, _clip_semantic)
    minimal_judge_evidence = {
        "problem_statement": evidence["problem_statement"][:9000],
        "specification_proposal": evidence["specification_proposal"][:9000],
        "specification_addendum": evidence["specification_addendum"][:12000],
        "task_disposition": trace.get("task_disposition"),
        "task_disposition_reason": trace.get("task_disposition_reason"),
        "p2p_accounting": trace.get("p2p_accounting"),
        "f2p_accounting": compact_rows,
        "historical_test_patch": evidence["historical_test_patch"][:12000],
        "historical_test_config": evidence["historical_test_config"],
        "historical_test_sources": evidence["historical_test_sources"],
        "implementation_binding_signals": evidence["implementation_binding_signals"],
        "revision_tests": _auditable_revision_tests(tests, head_limit=12000),
        "revision_test_file_inventory": sorted(tests),
        "hard_replay_summary": evidence["hard_replay_summary"],
        "behavior_role_audit": evidence["behavior_role_audit"],
        "base_repository_probe": {
            "status": full_probe.get("status"),
            "base_present": full_probe.get("base_present", {}),
            "gold_only_candidates": full_probe.get("gold_only_candidates", []),
            "interpretation": "Literal qualified-text search only; false is not proof of runtime absence.",
        },
    }
    # Cheap deterministic binding failures do not need an endpoint round trip.
    # Reject them before the LLM Judge so a transient/slow endpoint cannot delay
    # an obvious repair (for example a Gold-only symbol hidden behind getattr).
    candidate_text = _without_comment_only_lines(
        "\n".join(str(data.get("head", "")) for data in tests.values())
    )
    problem_text = evidence["problem_statement"]
    def p_authorizes(term: str) -> bool:
        return _p_authorizes_symbol(
            term, problem_text, set(full_probe.get("gold_defined_classes", [])) | set(full_probe.get("gold_defined_types", []))
        )

    early_gold_only = [
        term for term in full_probe.get("gold_only_candidates", [])
        if term in candidate_text and not p_authorizes(term)
    ]
    if early_gold_only:
        result = {
            "verdict": "FAIL",
            "review_mode": "deterministic_binding_precheck",
            "findings": ["Candidate references Gold-only symbols absent from Base: " + ", ".join(early_gold_only)],
            "unsupported_requirements": [],
            "binding_risks": ["A symbol absent from Base needs explicit P support; a P-named class does not authorize its unspecified members or constructor."],
            "mapping_gaps": [],
            "under_conversion": [],
            "hidden_contracts": early_gold_only,
            "unjustified_drops": [],
            "rationale": "Deterministic binding precheck failed; repair the verifier before invoking the semantic endpoint.",
            "deterministic_binding_gate": {"status": "FAIL", "gold_only_symbols": early_gold_only},
        }
    else:
        result = None
    semantic_prompt = Path(config.get("prompts", {}).get("semantic_judge", "prompts/judges/semantic.md"))
    if not semantic_prompt.is_absolute(): semantic_prompt = PROJECT_ROOT / semantic_prompt
    system = semantic_prompt.read_text(encoding="utf-8") + (
        "\nThe revision_test_file_inventory is the complete supplied tests/ tree. "
        "A file listed there exists even if its content is clipped or omitted from "
        "revision_tests; never report it missing on that basis.\n"
    )
    protocol_errors: list[str] = []
    retry_limit = max(1, int(config.get("experiment", {}).get("semantic_protocol_retries", 3)))
    deterministic_only = bool(args.deterministic_only)
    retry_system = system + "\nReturn one compact JSON object immediately. Do not include reasoning, markdown, or prose outside JSON."
    compact_system = (
        "You are an automated semantic gate. Compare every historical test assertion with behavioral_obligations, obligation_accounting, and the emitted verifier. Require every product_behavior obligation to be preserved and allow an implementation_detail obligation to be excluded only with evidence that it is an internal representation, helper-only guarantee, or outside the accepted product input domain. A mixed row must remain rewrite or merge. When two rows retain the same product behavior, require one meaningful shared selector with merge accounting rather than duplicate identical test bodies. Reject semantic substitution between product behaviors: round-trip is not serialization, finite samples are not an arbitrary product-domain property, a swallowed exception, a returned error object, or bare empty result is not recovery; absence of an exception alone does not prove a P-required successful operation, so require its public success result or product-visible effect; likewise, for an invalid-input F2P, merely checking that the raw bad value is absent does not prove rejection because a different fabricated value could still be emitted; require the public no-value or error outcome actually supported by P and the historical assertion; a historical intermediate exception may map to a P-required visible recovery when the same failure is triggered and P or a documented Base public boundary does not fix its exact type and layer, exact mock arguments are not a user-visible effect, and related behavior is not equivalent behavior. Do not require the historical helper's container shape when an existing public boundary proves the same product state and the representation is not specified. When effective P expressly requires an enriched record field, derived field, aggregate list, or other transformed output state, a downstream boolean decision does not prove that state: a candidate can read raw fields directly and pass the decision while omitting the required output. Demand an independent stable public observation of each P-stated transformed result or an access-contract gap. A comparison negative control differing only in punctuation or parentheses may be a valid normalized equivalent; do not treat its lower score as required unless P fixes the distinction. Read the base Problem Statement, any controller-generated behavior addendum, original historical test patch/config, F2P accounting, emitted tests, and implementation-binding signals below. A proposal may add only behavior-level wording through the addendum; it may not name an implementation API. A P-named public class does not create a new test obligation by itself. Require a behavioral check of it only when the historical F2P mapping covers behavior involving that type. Never request coverage for P-only behavior outside historical F2P scope, even if the trace or reviewer labels it a converted obligation. Every mapping_gaps or under_conversion finding must name the original F2P selector, its assertion, and the emitted assertion that fails to preserve that same behavior. Do not infer a broader postcondition from P than the historical assertion exercises; for example, a cache-recovery F2P that checks cache reading and error notification does not require an added browsing/request non-blocking test unless a historical F2P assertion checks it. For an open-ended user-facing error message, require the deterministic verifier to check the causal new notification, any P-fixed level or channel, nonempty content, and required recovery; do not require a lexical test of unrestricted wording. Treat P-required warning counts as minimum per-event obligations; reject exact total/call-count ceilings unless P forbids additional useful warnings. Reject redundant internal helper-call spies when public results and warnings establish the behavior. Use paraphrase and nonsensical-message examples to document semantic risk, not to invent a fixed vocabulary contract. An unnamed Gold-only method, constructor signature, or private representation remains unauthorized; accept alternative public access patterns when P leaves them open. An existing Base exception class does not by itself justify requiring that exact class at a particular intermediate layer. Reject a verifier that would fail an alternative handling the same P-required failure at another layer unless P or a documented Base public contract fixes the type and boundary. For a default output contract that permits only customized entries, an assertion that one customized line is present and hidden lines are absent can still accept an unrelated noncustomized line; require the verifier to reject that concrete wrong output. For an include-all or include-hidden contract that requires certain entries to appear, a whole-output set equality can reject an additional legitimate programmatic entry; require a P quote before treating the seeded fixture as a closed universe. Likewise, a global count of UI controls is not justified merely by one required menu action. Reject a test adapter that chooses a different public parser or method per example by comparing each candidate output with that example's expected answer; require one consistent public entrypoint across the cases. A drop is valid only for a pure implementation detail with explicit evidence. A convertible task must contain at least one retained observable obligation that is changed or missing in Base. When the task is non_discriminative, do not fail merely for lacking a discriminator: audit every mapping and drop, PASS only if there is no under-conversion, and let the controller stop without publication. For non_discriminative, each emitted surface must exist and express the same behavior in both Base and Gold; a Base helper removed by Gold and an unnamed Gold-only replacement are one-sided implementation surfaces. A P-named new public type requires behavioral coverage only when historical F2P scope includes behavior involving it. "
        "Separate functional deltas from converted regressions. If an observable historical behavior is absent from P but already passes at a Base public/product boundary, require base_regression_behavior with base_behavior_status=already_satisfies and do not expand P. Only P-supported rows with independently replayable Base-failing selectors count as functional deltas. Reject one selector shared between Base-existing and changed/missing rows. This semantic review runs before hard replay for convertible tasks, so a null hard_replay_summary is expected and must not by itself cause FAIL; inspect the supplied verifier sources and let later deterministic gates establish execution outcomes. "
        "Apply strict specification entailment only while reviewing behaviors exercised by a historical F2P assertion. A sensible guard, safety measure, prerequisite, counterpart, interpretation, or UX consequence of a broader P feature is not itself P support. A normal-state feature does not prescribe hidden, inert, disabled, or absent behavior during loading or missing-resource states, and a collection action does not prescribe empty/singleton presentation. Route a behavior to specification_gap only when a cited historical F2P assertion exercises that same observable product behavior, the behavior is absent from P, and the missing specification blocks a fair conversion of that historical assertion. Behaviors stated by P but not exercised by any historical F2P are out of scope: do not report them as omissions, specification gaps, under-conversion, or new-test requests. "
        "If a row says behavior is absent from P, accept it only when the supplied behavior addendum states that behavior without prescribing an API. "
        "Return exactly one JSON object with verdict PASS or FAIL and arrays findings, unsupported_requirements, "
        "binding_risks, mapping_gaps, under_conversion, hidden_contracts, unjustified_drops, specification_gaps, plus rationale. "
        "Do not explain your reasoning outside JSON. Any emitted test that bypasses the historical behavior is FAIL."
    )
    for attempt in range(retry_limit) if result is None and not deterministic_only else []:
        try:
            # The compact bundle still contains every F2P obligation, the
            # historical assertions, generated verifier sources, replay result,
            # and symbol provenance. Sending the much larger construction dump
            # caused reasoning models to exhaust their completion before the
            # required JSON verdict and could clip middle F2P rows at the client
            # boundary.
            if attempt == 0:
                prompt, payload = retry_system, minimal_judge_evidence
            else:
                prompt, payload = compact_system, minimal_judge_evidence
            candidate_result = _normalize_judge_lists(
                judge(config=config, credentials=credentials, role="semantic", system=prompt, evidence=payload),
                "findings", "unsupported_requirements", "binding_risks", "mapping_gaps",
                "under_conversion", "hidden_contracts", "unjustified_drops", "specification_gaps",
            )
            if candidate_result.get("verdict") not in {"PASS", "FAIL"}:
                protocol_errors.append(
                    f"attempt_{attempt + 1}: Judge returned disallowed verdict "
                    f"{candidate_result.get('verdict')!r}"
                )
                continue
            result = candidate_result
            break
        except (ValueError, RuntimeError) as exc:
            protocol_errors.append(f"attempt_{attempt + 1}: {exc!r}")
    if result is None:
        result = _deterministic_fallback(
            evidence,
            protocol_errors or (["deterministic-only mode"] if deterministic_only else []),
            allow_pass=deterministic_only or bool(config.get("experiment", {}).get("semantic_deterministic_fallback", False)),
        )

    # A P-only omission is not a conversion defect unless the historical F2P
    # inventory actually asserts that behavior. Filter unsupported scope claims
    # before focused reviewer passes can turn them into a hard gate.
    result = scope_review_findings(result, compact_rows)

    # A broad semantic review can overlook drops when a nearby P2P test covers
    # similar behavior. Run a narrow second audit only for accepted revisions
    # that contain drops. Redundancy permits merge; it never proves that the
    # historical row has no independent observable behavior.
    drop_rows = [
        row for row in trace.get("f2p_accounting", [])
        if isinstance(row, dict) and row.get("decision") == "drop"
    ]
    if result.get("verdict") == "PASS" and drop_rows and not deterministic_only:
        drop_system = (
            "You are the conservative drop gate for historical F2P conversion. "
            "Audit every supplied drop row independently. Remove the private or Gold-only helper name mentally, then inspect behavior_intent, historical_behavior, and evidence. "
            "If any input/output value, normalization, ordering, serialization, error, side effect, or edge case remains observable through an existing Base product boundary, the drop is invalid and the row must be rewrite or merge. An internal empty collection versus public None, empty output, or absent field may be an equivalent no-value product outcome; preserve that outcome and exclude only the container/type representation. "
            "Similar coverage by another F2P or retained P2P is never sufficient justification for drop; it permits merge mapping to a shared emitted test. "
            "A drop is valid only when nothing remains except helper/type existence, private representation, mock call shape, fixture plumbing, or Gold bookkeeping. "
            "Return exactly one JSON object with verdict PASS or FAIL, findings, unjustified_drops, and rationale. unjustified_drops must list source_f2p values."
        )
        drop_evidence = {
            "problem_statement": evidence["problem_statement"][:7000],
            "drop_rows": [
                {key: row.get(key) for key in (
                    "source_f2p", "behavior_intent", "historical_behavior", "evidence",
                    "problem_statement_support", "functional_surface", "observable_surface",
                    "base_repo_observable", "drop_justification", "drop_evidence",
                )}
                for row in drop_rows
            ],
        }
        try:
            drop_audit = _normalize_judge_lists(
                judge(config=config, credentials=credentials, role="semantic",
                      system=drop_system, evidence=drop_evidence),
                "findings", "unjustified_drops",
            )
            drop_audit.pop("raw_response", None)
            result["drop_audit"] = drop_audit
            if drop_audit.get("verdict") != "PASS":
                sources = drop_audit.get("unjustified_drops") or [
                    row.get("source_f2p", "<unknown>") for row in drop_rows
                ]
                result["verdict"] = "FAIL"
                result.setdefault("findings", []).append(
                    "Dedicated drop audit rejected one or more implementation-detail drops"
                )
                result["unjustified_drops"] = list(dict.fromkeys(
                    list(result.get("unjustified_drops", [])) + [str(value) for value in sources]
                ))
                result["under_conversion"] = list(dict.fromkeys(
                    list(result.get("under_conversion", [])) + [str(value) for value in sources]
                ))
        except (ValueError, RuntimeError) as exc:
            result["verdict"] = "FAIL"
            result["review_mode"] = "protocol_failure"
            result["failure_classification"] = "judge_transport"
            result.setdefault("findings", []).append(
                "Dedicated drop audit did not return a closed JSON verdict"
            )
            result["drop_audit_protocol_error"] = repr(exc)
    # A broad review may mistake an existing error class for a contract that
    # an intermediate facade must throw it. Require a focused counterfactual
    # review only when executable verifier assertions contain exact error types.
    exact_error_signals = [
        signal for signal in evidence["implementation_binding_signals"]
        if signal["kind"] == "exact_exception_type"
    ]
    if result.get("verdict") == "PASS" and exact_error_signals and not deterministic_only:
        error_system = (
            "You are an adversarial semantic audit of exact exception-type assertions in a functional verifier. "
            "For each signal, distinguish the P-required external failure/recovery from a chosen intermediate propagation layer. "
            "A class existing in Base, appearing in Gold, or being asserted by the historical F2P does not prove that this exact class must be thrown at this exact boundary. "
            "Require either an explicit P requirement or documentation of the same Base public boundary and error contract, not documentation of a different method. "
            "Construct a concrete plausible alternative that handles the same P failure at a different layer or with a different application error. "
            "If that alternative would meet P and the verifier would reject it, return FAIL and explain how to test the downstream observable effect instead. "
            "Do not recommend adding Gold's error class or layer to P just to preserve a historical assertion. "
            "A PASS must cite the exact P passage or documented Base public boundary that fixes every exact type and layer; absence of this evidence is FAIL. "
            "Return exactly ONE compact JSON object, with verdict as the first key and then findings, binding_risks, counterfactual, and rationale. "
            "Use empty arrays for no findings; keep rationale under 120 words. Never output separate JSON objects per signal or prose outside JSON."
        )
        error_evidence = {
            "problem_statement": evidence["problem_statement"],
            "specification_addendum": evidence["specification_addendum"],
            "signals": exact_error_signals,
            "f2p_accounting": compact_rows,
            "revision_tests": {
                name: str(data.get("head", ""))[:12000]
                for name, data in tests.items()
                if any(signal["file"] == name for signal in exact_error_signals)
            },
            "base_probe_interpretation": "Literal source presence is not a public error contract; cite a documented boundary if one is supplied.",
        }
        try:
            error_audit = None
            focused_protocol_errors: list[str] = []
            for focused_attempt in range(2):
                try:
                    candidate_audit = _normalize_judge_lists(
                        judge(config=config, credentials=credentials, role="semantic",
                              system=(error_system if focused_attempt == 0 else error_system +
                                      "\nReturn one compact JSON object immediately. Start with {\"verdict\": \"PASS\" or \"FAIL\"}; do not emit separate per-signal objects."),
                              evidence=error_evidence),
                        "findings", "binding_risks",
                    )
                    if candidate_audit.get("verdict") not in {"PASS", "FAIL"}:
                        raise ValueError("focused error audit did not return PASS or FAIL")
                    error_audit = candidate_audit
                    break
                except (ValueError, RuntimeError) as exc:
                    focused_protocol_errors.append(f"attempt_{focused_attempt + 1}: {exc!r}")
            if error_audit is None:
                raise ValueError("; ".join(focused_protocol_errors))
            error_audit.pop("raw_response", None)
            if focused_protocol_errors:
                error_audit["protocol_retries"] = focused_protocol_errors
            result["focused_error_audit"] = error_audit
            if error_audit["verdict"] == "FAIL":
                result["verdict"] = "FAIL"
                result["primary_rationale"] = result.get("rationale", "")
                result["rationale"] = str(error_audit.get("rationale", "Focused exact-error contract audit failed"))
                result.setdefault("findings", []).append(
                    "Dedicated exact-error contract audit rejected an intermediate error-type assertion"
                )
                result.setdefault("binding_risks", []).extend(
                    str(item) for item in error_audit.get("binding_risks", [])
                )
        except (ValueError, RuntimeError) as exc:
            result["verdict"] = "FAIL"
            result["review_mode"] = "protocol_failure"
            result["failure_classification"] = "judge_transport"
            result.setdefault("findings", []).append(
                "Dedicated exact-error contract audit did not return a closed JSON verdict"
            )
            result["focused_error_audit_protocol_error"] = repr(exc)
    if _should_run_focused_counterfactual(result, deterministic_only=deterministic_only):
        focused_audit = review_counterfactuals(
            config=config, credentials=credentials,
            problem=evidence["problem_statement"],
            addendum=evidence["specification_addendum"],
            signals=evidence["implementation_binding_signals"],
            tests=tests, trace_rows=compact_rows, judge_fn=judge,
        )
        if focused_audit is not None:
            result = _merge_focused_counterfactual_audit(result, focused_audit)
    result.pop("raw_response", None)
    result["verifier_evidence_fingerprint"] = revision_evidence_fingerprint(revision / "tests")
    result["revision"] = str(revision.relative_to(root)) if revision.is_relative_to(root) else str(revision)
    probe = evidence["base_repository_probe"]
    problem = evidence["problem_statement"]
    revision_text = candidate_text
    specification_gaps = [
        {
            "source_f2p": row.get("source_f2p", "<unknown>"),
            "gap": row.get("specification_gap", ""),
            "proposal": row.get("specification_proposal", ""),
            "planned_observable_surface": row.get("planned_observable_surface", ""),
        }
        for row in trace.get("f2p_accounting", [])
        if isinstance(row, dict) and row.get("decision") == "specification_gap"
    ]
    if specification_gaps:
        result["verdict"] = "FAIL"
        result.setdefault("findings", []).append("Unresolved specification_gap requires explicit Problem Statement review")
        result["mapping_gaps"] = list(result.get("mapping_gaps", [])) + specification_gaps
        result["specification_gaps"] = specification_gaps
    disposition_errors = trace_disposition_errors(trace)
    if disposition_errors:
        result["verdict"] = "FAIL"
        result.setdefault("findings", []).extend(disposition_errors)
        result["mapping_gaps"] = list(result.get("mapping_gaps", [])) + disposition_errors
    trace_rows = evidence.get("conversion_trace", {}).get("f2p_accounting", [])
    missing_evidence = [row.get("source_f2p", "<unknown>") for row in trace_rows
                        if not isinstance(row, dict) or any(key not in row for key in (
                            "base_repo_observable", "gold_only_binding", "specification_gap",
                            "specification_proposal", "planned_observable_surface",
                            "drop_justification", "drop_evidence"))]
    if missing_evidence:
        result["verdict"] = "FAIL"
        result.setdefault("findings", []).append("Conversion trace lacks Base/Gold evidence fields for: " + ", ".join(missing_evidence[:20]))
    def p_explicitly_names(term: str) -> bool:
        # The precheck and final gate must apply the same authorization rule.
        return p_authorizes(term)
    gold_only = [term for term in probe.get("gold_only_candidates", [])
                 if term in revision_text and not p_explicitly_names(term)]
    # The probe must cover the emitted verifier itself. A symbol absent from
    # Base and absent from the retained Problem Statement is a hidden contract,
    # even when it appears in Requirements, Interface, or Gold.
    if gold_only:
        result["verdict"] = "FAIL"
        result.setdefault("findings", []).append("Deterministic Base/Gold gate: candidate references Gold-only symbols absent from Base: " + ", ".join(gold_only))
        result.setdefault("binding_risks", []).append("Gold-only API or implementation surface cannot be a correctness requirement when it is not named by the Problem Statement.")
        result["deterministic_binding_gate"] = {"status": "FAIL", "gold_only_symbols": gold_only}
    else:
        result["deterministic_binding_gate"] = {"status": "PASS", "gold_only_symbols": []}
    result["base_repository_probe_summary"] = {"status": probe.get("status"), "gold_only_candidates": probe.get("gold_only_candidates", [])}
    output = (args.output or paths.semantic_review_path).resolve()
    write_judgement(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
