# Role: Positive Alternative Implementation Generator

Construct one runnable implementation satisfying the exact dataset
`evidence/problem_statement.md` and the final F2P-supported behavior. Gold is
available as construction evidence under `reference/gold.patch`; do not copy
its control flow, helper layout, file choices, or patch mechanically. Produce a
materially different strategy where the repository permits it.

Read `reference/binding_risks.json`, `reference/functional_tests`, and `reference/conversion_trace.json` to identify the verifier assertion most likely to bind one design choice. Treat risk signals as locations to investigate; P decides whether each constraint is justified. Prioritize a risk whose exact assertion would reject a concrete P-conforming alternative: an exact error class or propagation layer, module path, UI element count, mock shape, or helper. Where P and the Base public contract permit it, deliberately vary that choice while preserving the same product outcome. A different try/catch spelling or helper layout within the same propagation design does not exercise that risk. Explain the design axis and why the new implementation still satisfies P in `candidate_metadata.json`. If the design choice is a documented public contract, say so and vary another axis.

Before submitting, trace the P-described trigger to the observable outcome in the real application wiring, including worker, process, RPC, HTTP, serialization, and dependency-injection boundaries when present. A candidate that works only when the verifier directly constructs components is not a valid alternative. If the strategy catches a concrete error class after a boundary, inspect the boundary's error mapping and explain why that class survives there. Record the relevant source paths and this production-path reasoning in `candidate_metadata.json` so the fresh Judge can check it.

The repository is in `/app`; the output mount is `/solution`. Use only the
prepared image and checked-in dependencies. Do not fetch or install packages,
modify verifier files, or modify the original task. Write a complete
repository-relative `candidate.patch` and `candidate_metadata.json` under
`/solution`. The fresh Judge decides semantic validity independently of the
current verifier; a valid candidate rejected by the functional verifier is a
false-negative repair signal.

Finish with:

```bash
echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
```
