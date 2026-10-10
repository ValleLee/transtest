# Stage 2 runtime contract

## Local process

The controller runs on the host in Python 3.12. Create a local `.venv` as
described in the root README; the project pins `mini-swe-agent==2.4.6`. Model credentials are
read from `.env` with mode `600`; the file is never copied into a task
workspace, trajectory, prompt, or Docker mount.

Check the installation without contacting the model endpoint:

```bash
PYTHONPATH=src .venv/bin/python scripts/runtime_check.py
```

## Model-driven Converter

`src/swepro_trans/agents/mini_swe_session.py` owns the mini-SWE-agent loop:
model request, bash tool-call parsing, Docker environment, bounded command
execution, submission sentinel, and trajectory output.

`src/swepro_trans/agents/runner.py` adapts a Harbor task to that loop. It reads
`environment.docker_image` from the official `task.toml`, leaves the image's
`/app` repository authoritative, mounts `problem_statement.md` and construction
evidence read-only, and mounts only the requested revision as writable output.
The Converter container uses `--network none`, matching the Harbor agent
network policy; verifier replay separately follows the task's declared
`[verifier].network_mode`.

The Converter receives:

- `public/problem_statement.md`: the only normative specification;
- `restricted/`: requirements, interface, historical test selectors/patches,
  Gold patch and task metadata as construction evidence;
- `/app`: the repository from the published Harbor image;
- `/solution`: the revision output boundary.

It must emit `tests/test.sh`, `tests/run_script.sh`, `tests/parser.py`,
`tests/config.json`, and `conversion_trace.json`, then execute
`COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`.

## Deterministic boundary

The model session never accepts a revision directly. The required sequence is:

```text
mini-SWE Converter
  -> validate_verifier_revision.py [cheap artifact/F2P contract]
  -> semantic Judge [P support + Base-repository observability]
  -> validate_verifier_revision.py --execute [Base/Gold replay]
  -> Positive QA / Negative QA evidence
  -> accept_verifier_revision.py
  -> swepro_trans package
```

A missing artifact, missing F2P mapping, missing replay, or missing QA summary
fails closed. `final/instruction.md` is written by the package script from the
original `problem_statement.md`; the model does not author it.
