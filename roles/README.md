# Verifier conversion roles

The Converter, Positive Generator, Negative Generator and fresh Judges use the
V2 prompts in `prompts/`. The exact dataset `problem_statement` is the only
normative instruction. `requirements`, `interface`, F2P/P2P, Gold, repository
and environment are construction evidence. Hard validation, replay, packaging
and accounting remain deterministic.

The role contract is in `roles.yaml`. The prompt files describe semantics;
container mounts and paths are supplied by the controller for each run.
