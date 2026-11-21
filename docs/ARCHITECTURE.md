# Architecture

## Modules and dependency direction

```
contracts/  (money, schemas, submission)        ← imported by everyone, imports nothing internal
   ↑
sim/  world → faults → episode → export         trusted side: builds world, injects, gates
verification/auditor.py                         public data + contracts only (never sim/)
   ↑
evaluation/  matcher, service (OS process)      holds truth; imports sim, verification, matcher
   ↑ JSON lines over a pipe
env/  env.py, calculator.py                     agent side: public data only, imports contracts only
agents/oracle.py, benchmark/trajectory.py, cli.py
```

Rule: `env/` must not import `sim/`, `verification/` or `evaluation/` (checked by
`test_agent_process_never_receives_truth`). `verification/` must not import `sim/` (ADR-009).

## Episode pipeline

1. `build_world(seed, config, attempt)`: vendors, FX table (business days, period ±21 d), invoices with
   line items, payments (full, instalment, split, advance), distractors, background journals
   (payroll, depreciation, bank fees) until ≥200 ledger rows. Every journal balances.
2. `faults.inject(world)`: interactions first, then the four types; each mutation records
   before/after, a counterfactual, and returns a truth spec.
3. `project(world)` → `PublicEpisode` (sorted ledger, shuffled docs, manifest, policy).
4. Acceptance gate (`episode._gate`): auditor violations = 0, auditor issues == truth, evidence
   resolves and is derivable. Retry with the next attempt (≤20) or raise `GenerationFailed`.
5. `evaluation/service.py` keeps truth; the env receives `public` only.

## Accounting model

Chart: `1010 Bank`, `2100 Accounts Payable`, `2190 Supplier Advances`, expense accounts per industry,
`7600 FX Difference`, payroll/depreciation/fee accounts. Ledger in base currency (ADR-002). Journal
grouping and AP relief formula: CONTRACTS §2.

## Truth and evidence

Truth issue = `{issue_id, type, affected_ids, expected_amount_minor, currency, allowed_evidence_sets}`
(CONTRACTS §3). Evidence ids are public ids only (doc ids, row ids, fx ids). Provenance (seed,
attempt, mutations, counterfactual) goes to `provenance.json`, never to the agent.

## Requirements traceability

| Requirement (spec / PDF) | Implementation | Test | Status |
|---|---|---|---|
| 1 company, 1 period, 200–2000 rows, 20–200 docs, 0–12 errors | `sim/world.py`, `ScenarioConfig.validate` | `test_generator`, `test_contracts::test_invalid_configs_rejected` | done; size gate + `test_largest_episode_fits_official_ranges_and_budget` |
| 4 error types independently configurable | `sim/faults.py` | `test_truth_equals_independent_audit` | done |
| 2 interacting-error scenarios | `duplicate_with_allocation`, `reporting_period(foreign, wrong_rate)` | same | done |
| Clean companies, distractors | `world._distractors` | clean config in generator tests | done |
| Public files manifest/ledger/invoices/payments/fx | `sim/export.py`, `schemas/` | `test_contracts`, round-trip test | done |
| Private truth separated | `write_private`, evaluator process | `test_agent_process_never_receives_truth` | done |
| reset/step API, 5 tools, ≤50 page, 100 steps, 60 s | `env/env.py` | `test_env` | done (time limit not tested by clock) |
| Matching rules + tolerance | `evaluation/matcher.py` | `test_matcher` | done |
| Official reward formula | `matcher.reward_from` | `test_matcher`, `test_slice` | done |
| Malformed → −1, no double submit | `contracts/submission.py`, env | `test_contracts`, `test_env` | done |
| Closed eval withholds reward | `Evaluator("eval")`, env | `test_env` | done |
| Deterministic seeds | phase RNGs | `test_generation_is_identical_across_processes` | done |
| Trajectories + replay | `benchmark/trajectory.py` | `test_trajectory_replays_identically` | done |
| ID / order metamorphic pairs | `sim/salt.py`, `project()` | `test_metamorphic` | done |
| 10 train + 10 dev episodes | — | — | **planned** (CL-02) |
| 4 baselines + benchmark + failure analysis | oracle only | — | **planned** (CX-02..05) |
| Adversarial suite §11.4 | partly | see EVALUATION.md | **partial** (CX-03) |
| Offline container | `Dockerfile` | — | written, not built |
