# Handoff to Codex

State (2026-11-21): contracts frozen (docs/CONTRACTS.md v1.0.0). Vertical slice works: generator →
gate → evaluator process → env → oracle → reward 1.0 → trajectory replay. `make verify` green.

## Start a task

```bash
cd ~/Desktop/Projects/ledgerforge
git worktree list && git branch --list 'agent/*'      # make sure the task is free
git worktree add ../ledgerforge-cx-01 -b agent/cx-01
cd ../ledgerforge-cx-01 && uv sync --frozen && make lint test
```

## Prompt (paste into Codex)

> You are working on LedgerForge, an RL environment for financial-audit agents. Read `AGENTS.md`,
> then `docs/ai/TASKS.md` task **CX-01**, then `docs/CONTRACTS.md` sections 4, 6 and 7 only.
> Work only in the files the task lists. Keep runtime standard-library only. Do not change the
> reward formula, tool set, or any frozen contract; if you think one is wrong, write the argument in
> `docs/ai/INTEGRATION.md` and stop. Write failing tests first, then code. Finish with
> `make lint test` green, commit on branch `agent/cx-01` as `fix:`/`feat:` commits, and append to
> `docs/ai/INTEGRATION.md` the exact commands you ran and their results. Do not merge.

Next tasks in order: CX-01 → CX-02 → CX-03 → CX-04 (needs CL-02) → CX-05. One worktree per task.
