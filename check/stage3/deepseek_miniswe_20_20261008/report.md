# Stage 3 run report — deepseek_miniswe_20_20261008

Generated: 2026-10-07T19:57:38+00:00

## Two instruction cohorts

| Measure | Original instruction | Converted instruction |
|---|---:|---:|
| Planned | 20 | 20 |
| Nonempty patches | 20 | 20 |
| Two valid verifier results | 20 | 20 |
| Original verifier PASS | 19 | 3 |
| Functional verifier PASS | 17 | 13 |
| No patch | 0 | 0 |
| Replay errors | 0 | 0 |
| Input tokens | 59609625 | 108441069 |
| Cache tokens | 58695040 | 107098624 |
| Output tokens | 536184 | 651276 |
| Native vs regrade comparable | 20 | 20 |
| Native vs regrade disagreements | 0 | 0 |

## Paired verifier verdicts

### original

| Original verifier | Functional PASS | Functional FAIL |
|---|---:|---:|
| PASS | 16 | 3 |
| FAIL | 1 | 0 |

### converted

| Original verifier | Functional PASS | Functional FAIL |
|---|---:|---:|
| PASS | 3 | 0 |
| FAIL | 10 | 7 |

## Paired instruction comparison

Only tasks with valid results for both instruction cohorts enter each comparison.

| Verifier and task subset | Paired tasks | Original instruction PASS | Converted instruction PASS | Difference |
|---|---:|---:|---:|---:|
| original_verifier | 20 | 19 | 3 | -80.0% |
| functional_verifier | 20 | 17 | 13 | -20.0% |
| deletion_only_original_verifier | 17 | 16 | 2 | -82.4% |
| deletion_only_functional_verifier | 17 | 15 | 12 | -17.6% |
| clarification_original_verifier | 3 | 3 | 1 | -66.7% |
| clarification_functional_verifier | 3 | 2 | 1 | -33.3% |

## Semantic review

- Disagreements: 14
- Reviewed: 14; unreviewed: 0; uncertain: 0
- Confirmed rescues: 10
- Confirmed false rejections: 1

Harbor reports zero USD for this custom model; actual API charges are unavailable.
See `aggregate.json`, `semantic_review_queue.json`, per-task `analysis.json`, trajectories, patches, and replay logs.
