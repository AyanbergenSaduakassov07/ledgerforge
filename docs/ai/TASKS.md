# Task backlog

Status: todo / doing / review / done. Every task: `make lint test` green + its acceptance tests;
reviewer runs `make verify` before merge.

## Claude (generation, verification)

### CL-01 id_salt metamorphic renaming — done (agent/cl-01)
Files: `sim/episode.py` (`project`), `tests/test_generator.py`. Deps: none.
In: config `id_salt`. Out: every public id (doc, invoice, payment, row, entity) consistently renamed;
truth renamed identically. Acceptance: for 10 seeds, oracle reward identical with/without salt;
auditor issues map 1:1 through the rename; no salted id equals an unsalted one.
DoD: `NotImplementedError` removed; CONTRACTS §9 updated. Review: Opus code-reviewer.

### CL-02 Release 10 train + 10 dev episodes — done (agent/cl-01; public files + splits.json, truth regenerated into private/ by `ledgerforge release`)
Files: `episodes/train/`, `episodes/dev/`, `private/` (truth for train/dev committed under
`episodes/*/truth/` by explicit decision), `cli.py generate`. Deps: CL-01.
Acceptance: mix of clean, each single fault, both interactions, ≥2 currencies; all pass gate;
regeneration from listed seeds is byte-identical (test). Review: self + Codex spot check.

### CL-03 Size-range coverage — done (agent/cl-01; cap n_invoices ≤ 100, gate enforces ranges)
Files: `tests/test_generator.py`. Acceptance: expert + n_invoices=150 + 12 errors passes gate and stays
< 5 s generation; ledger ≤ 2000 rows, docs ≤ 200.

## Codex (environment, evaluator, baselines, benchmark)

### CX-01 Take ownership + harden env/evaluator — todo
Files: `env/env.py`, `evaluation/service.py`, `tests/test_env.py`. Deps: contracts frozen (done).
Work: evaluator crash/timeout handling (dead pipe → clean error, no hang); test the 60 s limit with an
injected clock; `get_document` arg validation messages; close() idempotent.
Acceptance: new tests for each; existing tests unchanged and green. Review: Claude.

### CX-02 Baseline policies — todo
Files: `agents/random_explorer.py`, `agents/reconciler.py`, `agents/flag_all.py`,
`tests/test_baselines.py`. Deps: CX-01.
I/O: `AgentPolicy` protocol (`contracts/schemas.py`): `reset(obs)`, `act(obs) -> EnvAction`, public data only.
Reconciler uses only tool calls (no truth, no `sim/` imports). Acceptance: each policy finishes
within 100 steps on 5 seeds; deterministic given seed; import-guard test that none imports
`sim`/`verification`/`evaluation`. Review: Claude.

### CX-03 Adversarial suite (spec §11.4 rest) — todo
Files: `tests/test_adversarial.py`. Deps: CX-02.
Acceptance: flag-all mean reward < 0 over 10 faulted + 5 clean seeds; shuffled-finding-order
submissions give identical reward (property test over 20 permutations); submissions with
persuasive explanations but wrong amount get FP. Review: Claude.

### CX-04 Benchmark runner — todo
Files: `benchmark/run.py`, `cli.py bench`, `outputs/benchmarks/`. Deps: CX-02, CL-02.
Out: per policy × split JSON + trajectories.jsonl (spec §12 fields) + markdown table of precision,
recall, F1, reward, steps, runtime. Acceptance: rerun gives identical numbers (except runtime);
local closed-eval mirror 20 episodes (≥5 clean, ≥5 interacting) + 20 paired id/order transforms.
Review: Claude checks numbers come from raw outputs.

### CX-05 Failure analysis — todo
Files: `outputs/reports/failure_analysis.md`, `benchmark/analyze.py`. Deps: CX-04.
Categorise reconciler FP/FN by fault type and cause. Measured only.
