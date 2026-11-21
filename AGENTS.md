# AGENTS.md — rules for every coding agent (Codex, Claude)

Read first: `docs/ai/HANDOFF.md` (your current task), then the sections of `docs/CONTRACTS.md` it names.
Precedence: `docs/official_case_ru.pdf` > `docs/MASTER_SPEC.md` > `docs/CONTRACTS.md` > code.

## Hard rules
- Runtime stays standard-library only (`dependencies = []`). No network at evaluation time.
- Never change the reward formula, the five tools, or frozen contracts without an ADR in
  `docs/DECISIONS.md` and lead-architect (Claude) approval.
- Truth never reaches the agent process: no imports of `sim/` or `verification/` from `env/` or
  `agents/` that run on the agent side; no truth in observations, errors, logs or files under `episodes/`.
- Only edit files your task in `docs/ai/TASKS.md` lists; ownership is in `docs/ai/OWNERSHIP.md`.
- Deterministic: no wall-clock, `hash()`, set iteration order or unseeded random in outputs.
- No fabricated results. Benchmark numbers come from committed scripts and raw outputs.
- All data fictional; no real company names or PII.

## Workflow
- One task per worktree: `git worktree add ../ledgerforge-<task> -b agent/<task>`.
- Before done: `make lint test` green, plus the task's acceptance tests. Commit as `<type>: <what>`.
- Report exact commands and results in `docs/ai/INTEGRATION.md` under your task id.
