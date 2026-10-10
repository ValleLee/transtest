#!/usr/bin/env python3
"""Close a verifier revision only after every deterministic and QA gate passes."""
from __future__ import annotations
import argparse, ast, json
from pathlib import Path
from swepro_trans.paths import resolve_task
from ..conversion_schema import classification_errors, trace_disposition_errors
from .binding_signals import revision_evidence_fingerprint


def load(path: Path):
    if not path.is_file(): return None
    try: return json.loads(path.read_text())
    except Exception: return None

def semantic_evidence_matches(review: dict | None, revision: Path) -> bool:
    """Reject a stale semantic verdict after verifier or signal rules change."""
    return isinstance(review, dict) and review.get("verifier_evidence_fingerprint") == revision_evidence_fingerprint(revision / "tests")


def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument('--task-root',type=Path,required=True); ap.add_argument('--revision',type=Path,required=True)
    args=ap.parse_args(argv); paths=resolve_task(args.task_root); root=paths.run_root; rev=args.revision.resolve()
    expected_revision = str(rev.relative_to(root)) if rev.is_relative_to(root) else str(rev)
    checks={
      'artifact_contract': load(paths.artifact_contract_path),
      'hard_replay': load(paths.hard_replay_path),
      'behavior_role_audit': load(paths.behavior_role_audit_path),
      'stability': load(paths.stability_path),
      'semantic_review': load(paths.semantic_review_path),
      'positive_qa': load(paths.qa_branch('positive') / 'summary.json'),
      'negative_qa': load(paths.qa_branch('negative') / 'summary.json'),
    }
    errors=[]
    # functional_specification.md is an intermediate proposal record. It is
    # never merged into the solver instruction automatically. A proposal is
    # allowed to be empty when the base Problem Statement already covers all
    # retained behavior; any actual gap remains an explicit blocker below.
    proposal = rev / 'functional_specification.md'
    if not proposal.is_file():
        errors.append('functional_specification.md proposal record is missing')
    # The selected revision owns the authoritative F2P mapping. The attempt-level
    # trace is only an initialization/progress record and may remain empty.
    revision_trace_path = rev / 'conversion_trace.json'
    trace = load(revision_trace_path) or {}
    errors.extend(trace_disposition_errors(trace))
    if trace.get("task_disposition") != "convertible":
        errors.append("only task_disposition=convertible may be accepted and packaged")
    rows = trace.get("f2p_accounting", [])
    original_config = load(paths.original / "tests/config.json") or {}
    raw_f2p = original_config.get("fail_to_pass", [])
    if isinstance(raw_f2p, str):
        try:
            raw_f2p = json.loads(raw_f2p)
        except json.JSONDecodeError:
            try:
                raw_f2p = ast.literal_eval(raw_f2p)
            except (ValueError, SyntaxError):
                raw_f2p = []
    source_f2p = {str(value) for value in raw_f2p} if isinstance(raw_f2p, (list, tuple)) else set()
    accounted_f2p = {str(row.get("source_f2p")) for row in rows if isinstance(row, dict)}
    missing_f2p = sorted(source_f2p - accounted_f2p)
    extra_f2p = sorted(accounted_f2p - source_f2p)
    if missing_f2p:
        errors.append("F2P coverage is incomplete: " + ", ".join(missing_f2p[:20]))
    if extra_f2p:
        errors.append("F2P accounting contains unknown selectors: " + ", ".join(extra_f2p[:20]))
    gaps = []
    invalid = []
    for row in rows:
        if not isinstance(row, dict):
            invalid.append("<unknown>")
            continue
        source = str(row.get("source_f2p", "<unknown>"))
        decision = row.get("decision")
        invalid.extend(classification_errors(row))
        if decision == "specification_gap":
            gaps.append(source)
        if decision not in {"rewrite", "merge", "drop"}:
            invalid.append(source)
        elif decision in {"rewrite", "merge"} and not row.get("emitted_tests"):
            invalid.append(source)
        elif decision == "drop" and not (str(row.get("drop_justification", "")).strip() and str(row.get("drop_evidence", "")).strip()):
            invalid.append(source)
    if gaps:
        errors.append("unresolved specification_gap: " + ", ".join(gaps[:20]))
    if invalid:
        errors.append("F2P conversion is incomplete: " + ", ".join(invalid[:20]))
    if checks['artifact_contract'] is None or checks['artifact_contract'].get('status')!='PASS' or checks['artifact_contract'].get('revision_relative')!=expected_revision:
        errors.append('artifact contract is not PASS for this revision')
    if checks['hard_replay'] is None or checks['hard_replay'].get('status')!='pass' or checks['hard_replay'].get('revision')!=expected_revision:
        errors.append('hard replay is not pass for this revision')
    if checks['behavior_role_audit'] is None or checks['behavior_role_audit'].get('status')!='PASS' or checks['behavior_role_audit'].get('revision')!=expected_revision:
        errors.append('behavior role audit is not PASS for this revision')
    if checks['stability'] is None or checks['stability'].get('status')!='pass' or checks['stability'].get('revision')!=expected_revision:
        errors.append('stability is not pass for this revision')
    elif not checks['stability'].get('f2p_scope_preserved') or not checks['stability'].get('p2p_scope_preserved'):
        errors.append('stability scope accounting is not preserved for this revision')
    if checks['semantic_review'] is None or checks['semantic_review'].get('verdict')!='PASS' or checks['semantic_review'].get('revision')!=expected_revision:
        errors.append('semantic_review is not PASS for this revision')
    elif not semantic_evidence_matches(checks['semantic_review'], rev):
        errors.append('semantic_review evidence is stale for current verifier files or binding-signal rules')
    for name in ('positive_qa','negative_qa'):
        if checks[name] is None or checks[name].get('status')!='pass' or checks[name].get('revision')!=expected_revision:
            errors.append(f'{name} is not pass for this revision')
    if isinstance(checks['positive_qa'], dict) and checks['positive_qa'].get('mode') == 'base_is_positive_reference':
        errors.append('Base may not substitute for an independently generated Positive QA implementation')
    result={'status':'accepted' if not errors else 'rejected','revision':str(rev.relative_to(root)) if rev.is_relative_to(root) else str(rev),'checks':{k:((v.get('verdict') if k=='semantic_review' else v.get('status')) if v else 'missing') for k,v in checks.items()},'errors':errors}
    out=paths.acceptance_path; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    # Reconcile a controller report left by an earlier gate run. This keeps
    # the human audit view consistent when acceptance is resumed manually or
    # after a nonzero pipeline exit.
    pipeline_path = paths.pipeline_report_path
    if pipeline_path.is_file():
        pipeline = load(pipeline_path) or {}
        pipeline['acceptance'] = result
        # A resumed run may have executed gates outside the original
        # controller process. Rehydrate the report from their authoritative
        # artifacts so the audit view never omits a completed QA gate.
        reconciled = {
            'artifact_contract': paths.artifact_contract_path,
            'semantic_review': paths.semantic_review_path,
            'hard_replay': paths.hard_replay_path,
            'behavior_role_audit': paths.behavior_role_audit_path,
            'stability': paths.stability_path,
            'positive_qa': paths.qa_branch('positive') / 'summary.json',
            'negative_qa': paths.qa_branch('negative') / 'summary.json',
        }
        for key, artifact in reconciled.items():
            value = load(artifact)
            if value is not None:
                pipeline[key] = value
        if result['status'] == 'accepted' and pipeline.get('status', '').startswith('rejected_'):
            pipeline['status'] = 'accepted_pending_package'
        pipeline_path.write_text(json.dumps(pipeline, ensure_ascii=False, indent=2) + '\n')
    if result['status']=='accepted':
        trace = load(revision_trace_path) or {}; trace['status']='accepted'; trace['accepted_revision']=result['revision']; revision_trace_path.write_text(json.dumps(trace,ensure_ascii=False,indent=2)+'\n')
        # Keep the canonical attempt-level index in sync for reviewers and
        # resumed tooling, while retaining the revision copy as the source of truth.
        paths.conversion_trace_path.parent.mkdir(parents=True, exist_ok=True)
        paths.conversion_trace_path.write_text(json.dumps(trace,ensure_ascii=False,indent=2)+'\n')
        state_path=paths.state_path; state=load(state_path) or {}; state['status']='accepted'; state['accepted_revision']=result['revision']; state['final_task']=str(paths.final_root.relative_to(root)); state['terminal_reason']='All automatic artifact, semantic, replay, stability, and QA gates passed.'; state.pop('manual_review_reason', None); state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result['status']=='accepted' else 1
if __name__=='__main__': raise SystemExit(main())
