#!/usr/bin/env python3
"""Run deterministic artifact and optional Base/Gold gates for a verifier revision.

The script never invents a conversion.  It checks the revision contract first;
``--execute`` then runs the candidate Harbor verifier in the task image using
the same Docker fallback used by the Stage 1 preflight.  Official Stage 3
runs should use pinned Harbor v0.22.0 instead.
"""
from __future__ import annotations
import argparse, ast, json, re, sys
from pathlib import Path

from ..runtime.stage1 import image_name, run_docker_preflight, write_json
from swepro_trans.paths import PROJECT_ROOT, resolve_task  # noqa: E402
from ..conversion_schema import (
    REQUIRED_F2P_FIELDS, classification_errors, converted_selector_groups, canonical_retained_p2p, append_f2p_regressions, replay_expectation,
    trace_disposition_errors, specification_provenance_errors,
    specification_addendum_errors,
    UNRESOLVED_MARKER, UNRESOLVED_EXACT_VALUES,
)

REQUIRED_TEST_FILES = ("test.sh", "run_script.sh", "parser.py", "config.json")
REQUIRED_REVISION_FILES = ("conversion_trace.json", "functional_specification.md", "self_review.md", "manifest.json")

def _normalized_citation_text(value: str) -> str:
    """Normalize whitespace only; punctuation and wording remain evidence-bearing."""
    return re.sub(r"\s+", " ", str(value)).strip()


def problem_statement_citation_errors(trace: dict, problem_text: str, addendum_text: str = "") -> list[str]:
    """Require exact source excerpts for rows classified as normative behavior."""
    errors: list[str] = []
    sources = [_normalized_citation_text(problem_text)]
    if addendum_text.strip():
        sources.append(_normalized_citation_text(addendum_text))
    for row in trace.get("f2p_accounting", []):
        if not isinstance(row, dict) or row.get("behavior_classification") not in {
            "p_supported_behavior", "base_regression_behavior"
        }:
            continue
        selector = str(row.get("source_f2p", "<unknown>"))
        citations = row.get("problem_statement_quotes")
        if not isinstance(citations, list) or not citations:
            errors.append(f"{selector}: missing exact P/addendum quote in problem_statement_quotes")
            continue
        for citation in citations:
            quote = _normalized_citation_text(citation)
            if not quote or not any(quote in source for source in sources):
                errors.append(
                    f"{selector}: problem_statement_quotes contains text not present verbatim in P or approved addendum"
                )
    return errors


def parse_list(value):
    if isinstance(value, list):
        return [str(x) for x in value]
    for fn in (json.loads, ast.literal_eval):
        try:
            result = fn(value)
            return [str(x) for x in result] if isinstance(result, (list, tuple)) else []
        except Exception:
            pass
    return []

def _selector_is_emitted(selector: str, tests_root: Path) -> bool:
    """Check that an accounting selector names code present in this revision.

    This is deliberately syntax-light so it works across Python, Go,
    JavaScript and other task languages. The file component must exist in the
    emitted bundle and the terminal test name must occur in that file. Runtime
    collection remains the authority in hard replay.
    """
    selector = str(selector).strip()
    if not selector:
        return False
    # SWE-bench/pytest selectors use ``file.py::test_name`` while several
    # JavaScript runners encode a hierarchical test title as
    # ``file.js | suite title test title``. The latter is not one literal
    # substring in source: suite and case names are declared separately.
    pipe_selector = " | " in selector
    if pipe_selector:
        pipe_parts = selector.split(" | ")
        file_part, pipe_titles = pipe_parts[0], pipe_parts[1:]
        parts = [file_part]
    else:
        parts = selector.split("::")
        file_part = parts[0]
        pipe_titles = []
    source_path = Path(file_part)
    path_parts = [part for part in source_path.parts if part not in {"/", "\\"}]
    candidates = []
    if not source_path.is_absolute():
        candidates.append(tests_root / source_path)
    candidates.append(tests_root / source_path.name)
    # Selectors may retain the repository's ``test/`` prefix or an absolute
    # container ``/tests/`` prefix, while the converted bundle stores files
    # relative to its tests root. Try the suffix after either known anchor.
    for anchor in ("tests", "test"):
        for index, part in enumerate(path_parts):
            if part == anchor and index + 1 < len(path_parts):
                candidates.append(tests_root.joinpath(*path_parts[index + 1:]))
    candidate = next((path for path in candidates if path.is_file()), None)
    if candidate is not None:
        artifact_text = candidate.read_text(encoding="utf-8", errors="replace")
    else:
        # Some language runners materialize tests from an embedded heredoc in
        # test.sh.  Such source is part of the emitted bundle, so inspect the
        # executable bundle files instead of assuming a standalone test file.
        # A selector listed in config.json is only a claim, not emitted test
        # code. Exclude the config from this fallback scan so native historical
        # F2P selectors cannot masquerade as converted tests merely because
        # their names are present in the selector list. Embedded tests in the
        # executable harness remain discoverable through test.sh/run_script.sh.
        artifact_text = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in tests_root.rglob("*")
            if path.is_file() and path.name != "config.json"
        )
        if Path(file_part).name not in artifact_text:
            return False
    if pipe_selector:
        # Test runners compose nested suite/case titles with spaces. Compare
        # normalized title tokens as an ordered subsequence so punctuation,
        # quoting, and the boundary between describe()/it() do not make a
        # real emitted test look absent. The physical test file is still
        # required above, and runtime collection remains the authority.
        def title_tokens_appear_in_order(title: str) -> bool:
            wanted = re.findall(r"[a-z0-9]+", title.lower())
            available = iter(re.findall(r"[a-z0-9]+", artifact_text.lower()))
            return bool(wanted) and all(
                any(token == found for found in available) for token in wanted
            )

        return bool(pipe_titles) and all(
            title_tokens_appear_in_order(title) for title in pipe_titles
        )
    if len(parts) == 1:
        return True
    terminal = parts[-1].split("[", 1)[0].strip()
    if not terminal:
        return True
    return terminal in artifact_text


def _selector_source_hints(selector: str, tests_root: Path, limit: int = 6) -> list[str]:
    """Suggest bundled test sources when an accounting selector points nowhere.

    Hints improve repair feedback only; they never make an absent selector valid.
    """
    file_part = str(selector).strip().split(" | ", 1)[0].split("::", 1)[0]
    wanted = Path(file_part).name.lower()
    if not wanted or not tests_root.is_dir():
        return []
    source_suffixes = {
        ".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
        ".go", ".rs", ".java", ".kt", ".rb", ".php", ".sh",
    }
    files = [
        path for path in tests_root.rglob("*")
        if path.is_file() and (path.suffix.lower() in source_suffixes or path.name in {"test.sh", "run_script.sh"})
    ]
    wanted_stem = Path(wanted).stem.lower()
    files.sort(key=lambda path: (
        0 if path.name.lower() == wanted else
        1 if path.stem.lower() == wanted_stem else
        2 if wanted_stem in path.stem.lower() or path.stem.lower() in wanted_stem else
        3,
        len(path.parts),
        str(path),
    ))
    return [path.relative_to(tests_root).as_posix() for path in files[:limit]]


def _selector_role_errors(trace: dict) -> list[str]:
    """Report selectors incorrectly assigned both Base replay roles."""
    delta, regressions = converted_selector_groups(trace)
    overlap = sorted(set(delta) & set(regressions))
    if not overlap:
        return []
    return [
        "converted selector cannot serve both functional-delta and Base-regression roles: "
        + ", ".join(overlap[:10])
    ]


def _script_permission_errors(tests_root: Path) -> list[str]:
    """Reject a non-executable standard runner before invoking Docker.

    ``test.sh`` is launched explicitly through ``bash`` by our replay harness,
    but ``run_script.sh`` is the native runner entrypoint and converters often
    invoke it directly from ``test.sh``. A missing executable bit otherwise
    makes both Base and Gold fail for an artifact packaging defect.
    """
    runner = tests_root / "run_script.sh"
    if runner.is_file() and not (runner.stat().st_mode & 0o111):
        return ["tests/run_script.sh must be executable (chmod +x)"]
    return []


def artifact_contract(root: Path, rev: Path) -> dict:
    paths = resolve_task(root)
    original = paths.original
    errors=[]
    if not original.is_dir(): errors.append('missing original task')
    if not paths.source.joinpath('problem_statement.md').is_file(): errors.append('missing problem_statement evidence')
    if paths.specification_addendum_path.is_file():
        errors.extend(specification_addendum_errors(
            paths.specification_addendum_path.read_text(encoding='utf-8', errors='replace')
        ))
    tests=rev/'tests'
    for name in REQUIRED_TEST_FILES:
        if not (tests/name).is_file(): errors.append(f'missing revision tests/{name}')
    errors.extend(_script_permission_errors(tests))
    for name in REQUIRED_REVISION_FILES:
        if not (rev/name).is_file(): errors.append(f'missing revision {name}')
    self_review=rev/'self_review.md'
    if self_review.is_file():
        self_review_text = self_review.read_text(encoding='utf-8', errors='replace')
        if not self_review_text.rstrip().endswith('SELF_REVIEW: PASS'):
            errors.append('self_review.md must end with SELF_REVIEW: PASS')
        if UNRESOLVED_MARKER.search(self_review_text):
            errors.append('self_review.md contains an unresolved scaffold marker')
    functional_specification = rev/'functional_specification.md'
    if functional_specification.is_file() and UNRESOLVED_MARKER.search(functional_specification.read_text(encoding='utf-8', errors='replace')):
        errors.append('functional_specification.md contains an unresolved scaffold marker')
    manifest=rev/'manifest.json'
    if manifest.is_file():
        try:
            manifest_data=json.loads(manifest.read_text())
            if not isinstance(manifest_data, dict):
                errors.append('manifest.json must contain an object')
            else:
                for field in ('revision', 'status'):
                    value = str(manifest_data.get(field, '')).strip()
                    if value.casefold() in UNRESOLVED_EXACT_VALUES or UNRESOLVED_MARKER.search(value):
                        errors.append(f'manifest.json {field} contains an unresolved scaffold marker')
        except Exception as exc: errors.append(f'invalid manifest.json: {exc}')
    cfg=original/'tests/config.json'; trace=rev/'conversion_trace.json'
    source=[]
    original_p2p=[]
    if cfg.is_file():
        try: source=parse_list(json.loads(cfg.read_text()).get('fail_to_pass', []))
        except Exception: errors.append('invalid original tests/config.json')
    if not trace.is_file():
        errors.append('missing conversion_trace.json')
    else:
        try:
            payload=json.loads(trace.read_text())
            rows = payload.get("f2p_accounting", [])
            errors.extend(trace_disposition_errors(payload))
            addendum_text = (
                paths.specification_addendum_path.read_text(encoding="utf-8", errors="replace")
                if paths.specification_addendum_path.is_file() else ""
            )
            errors.extend(specification_provenance_errors(payload, addendum_text))
            problem_text = paths.source.joinpath("problem_statement.md").read_text(encoding="utf-8", errors="replace")
            errors.extend(problem_statement_citation_errors(payload, problem_text, addendum_text))
            original_config = json.loads(cfg.read_text()) if cfg.is_file() else {}
            original_p2p = parse_list(original_config.get('pass_to_pass', original_config.get('pass_to_pass_tests', [])))
            candidate_config_path = tests / 'config.json'
            candidate_config = json.loads(candidate_config_path.read_text()) if candidate_config_path.is_file() else {}
            candidate_f2p = parse_list(candidate_config.get('fail_to_pass', []))
            candidate_p2p = parse_list(candidate_config.get('pass_to_pass', candidate_config.get('pass_to_pass_tests', [])))
            delta_selectors, regression_selectors = converted_selector_groups(payload)
            errors.extend(_selector_role_errors(payload))
            if set(candidate_f2p) != set(delta_selectors):
                missing_from_trace = sorted(set(candidate_f2p) - set(delta_selectors))
                missing_from_config = sorted(set(delta_selectors) - set(candidate_f2p))
                errors.append(
                    'functional delta selector provenance mismatch: '
                    f'config_only={missing_from_trace[:10]}, trace_only={missing_from_config[:10]}'
                )
            p2p_accounting = payload.get('p2p_accounting', {})
            excluded_items = p2p_accounting.get('excluded', []) if isinstance(p2p_accounting, dict) else []
            excluded = [str(item.get('selector')) for item in excluded_items if isinstance(item, dict)]
            if len(excluded) != len(set(excluded)):
                errors.append('duplicate selectors in p2p_accounting.excluded')
            unknown_excluded = sorted(set(excluded) - set(original_p2p))
            if unknown_excluded:
                errors.append('unknown excluded P2P selectors: ' + ', '.join(unknown_excluded[:10]))
            retained_native_p2p, mapping_errors = canonical_retained_p2p(original_p2p, p2p_accounting)
            errors.extend(mapping_errors)
            expected_p2p = append_f2p_regressions(retained_native_p2p, regression_selectors)
            if candidate_p2p != expected_p2p:
                errors.append(
                    'candidate P2P must equal the original P2P list verbatim followed only by converted F2P regressions'
                )
            if (tests / 'test_patch.patch').exists():
                errors.append('historical test_patch.patch must not be bundled into a functional verifier')
            tests_text = '\n'.join(
                path.read_text(encoding='utf-8', errors='replace')
                for path in tests.rglob('*') if path.is_file() and path.name != 'config.json'
            )
            if 'test_patch.patch' in tests_text or 'historical_tests/test_patch' in tests_text:
                errors.append('functional verifier must not apply or depend on the historical test patch')
            accounted_list=[str(x.get("source_f2p")) for x in rows if isinstance(x, dict)]
            accounted=set(accounted_list)
            missing=[x for x in source if x not in accounted]
            if missing: errors.append(f'unaccounted F2P seeds: {len(missing)}')
            duplicates = sorted({item for item in accounted_list if accounted_list.count(item) > 1})
            if duplicates: errors.append(f'duplicate F2P accounting rows: {len(duplicates)}')
            extra = sorted(accounted - set(source))
            if extra: errors.append(f'unknown F2P accounting seeds: {len(extra)}')
            allowed_decisions = {"rewrite", "merge", "drop", "specification_gap"}
            required_row = set(REQUIRED_F2P_FIELDS)
            for row in rows:
                if not isinstance(row, dict):
                    errors.append('F2P accounting row must be an object')
                    continue
                missing_fields = sorted(required_row - set(row))
                if missing_fields:
                    errors.append(f"F2P row {row.get('source_f2p', '<unknown>')} missing fields: {', '.join(missing_fields)}")
                decision = row.get("decision")
                if decision not in allowed_decisions:
                    errors.append(f"unsupported F2P decision: {decision!r}")
                for classification_error in classification_errors(row):
                    errors.append(classification_error)
                if decision in {"rewrite", "merge"} and not row.get("emitted_tests"):
                    errors.append(f"{decision} F2P row has no emitted_tests: {row.get('source_f2p', '<unknown>')}")
                elif decision in {"rewrite", "merge"}:
                    emitted = row.get("emitted_tests")
                    emitted_list = emitted if isinstance(emitted, list) else [emitted]
                    missing_emitted = [
                        str(selector) for selector in emitted_list
                        if not _selector_is_emitted(str(selector), tests)
                    ]
                    if missing_emitted:
                        details = []
                        for selector in missing_emitted[:10]:
                            hints = _selector_source_hints(selector, tests)
                            detail = selector
                            if hints:
                                detail += " (available bundled sources: " + ", ".join(hints) + ")"
                            details.append(detail)
                        errors.append(
                            f"{decision} F2P row references absent emitted tests: "
                            + "; ".join(details)
                        )
                elif decision == "drop":
                    for field in ("drop_justification", "drop_evidence"):
                        if not str(row.get(field, "")).strip():
                            errors.append(f"drop row {row.get('source_f2p', '<unknown>')} missing {field}")
                elif decision == "specification_gap":
                    for field in ("specification_gap", "specification_proposal", "planned_observable_surface"):
                        if not str(row.get(field, "")).strip():
                            errors.append(f"specification_gap row {row.get('source_f2p', '<unknown>')} missing {field}")
            # Mini-SWE works inside a container and may echo its mounted
            # evidence path. Normalize that equivalent spelling at the
            # controller boundary; the canonical host contract remains stable.
            if payload.get('specification_source') == 'evidence/problem_statement.md':
                payload['specification_source'] = 'source/problem_statement.md'
                trace.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            if payload.get('specification_source') != 'source/problem_statement.md':
                errors.append('trace specification source is not problem_statement.md')
        except Exception as exc: errors.append(f'invalid conversion_trace.json: {exc}')
    result={'status':'PASS' if not errors else 'FAIL','errors':errors,'task_root':str(root),'revision':str(rev),'revision_relative':str(rev.relative_to(root)) if rev.is_relative_to(root) else str(rev),'trace':str(trace.relative_to(root)) if trace.is_relative_to(root) else str(trace),'required_test_files':list(REQUIRED_TEST_FILES), 'required_revision_files':list(REQUIRED_REVISION_FILES)}
    write_json(paths.artifact_contract_path, result)
    return result

def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--task-root',type=Path,required=True)
    ap.add_argument('--revision',type=Path,required=True)
    ap.add_argument('--execute',action='store_true',help='after artifact checks, run Base/Gold candidate verifier in Docker')
    args=ap.parse_args(argv); paths=resolve_task(args.task_root); root=paths.run_root; original=paths.original; rev=args.revision.resolve()
    contract=artifact_contract(root,rev)
    result={'status':contract['status'],'contract':contract}
    if args.execute and contract['status']=='PASS':
        row_path=paths.source / 'dataset_row.json'
        try:
            row=json.loads(row_path.read_text())
            image=image_name(original,row)
            trace_payload = json.loads((rev / "conversion_trace.json").read_text(encoding="utf-8"))
            expectation = replay_expectation(trace_payload)
            original_config = json.loads((original / "tests/config.json").read_text(encoding="utf-8"))
            original_p2p = parse_list(original_config.get("pass_to_pass", original_config.get("pass_to_pass_tests", [])))
            replay=run_docker_preflight(root,image,tests_dir=rev/'tests',log_root=paths.hard_replay_root / 'docker',original_root=original,evidence_root=paths.validation_root,write_compat_results=False,expectation=expectation,stage_original_test_patch=bool(original_p2p))
            replay['revision']=str(rev.relative_to(root)) if rev.is_relative_to(root) else str(rev)
            write_json(paths.hard_replay_path,replay)
            result['hard_replay']=replay
            result['status']='PASS' if replay.get('status')=='pass' else 'FAIL'
        except Exception as exc:
            result['status']='FAIL'; result['hard_replay']={'status':'error','error':repr(exc),'revision':str(rev.relative_to(root)) if rev.is_relative_to(root) else str(rev)}
            write_json(paths.hard_replay_path,result['hard_replay'])
    elif args.execute:
        result['hard_replay']={'status':'not_run','revision':str(rev.relative_to(root)) if rev.is_relative_to(root) else str(rev),'reason':'artifact contract failed'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__': raise SystemExit(main())
