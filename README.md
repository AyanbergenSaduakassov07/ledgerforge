# LedgerForge

A causal financial-audit RL environment for the REC Genesis Hackathon 2026 (FinTech track).
Each episode generates a fictional company's accounting period with known injected faults: duplicate
invoices, payment allocation errors, wrong FX dates/rates and wrong reporting periods. An agent
inspects the books through five tools and submits findings. The episode's reward is the official
F1-based formula.

All entities and amounts are synthetic. There is no real company data and no PII.

## Verify (offline, no API keys, no GPU)

```bash
make verify        # uv sync --frozen, ruff, pytest, scripted oracle demo with trajectory replay
```

Expected tail: three `reward=1.000 ... replay=identical` lines. Container alternative (not yet built
or tested on this machine): `docker build -t ledgerforge . && docker run --rm --network none ledgerforge`.

## Use

```bash
uv run ledgerforge generate --seed 3 --count 2 --config '{"faults":{"fx_rate":1}}'
uv run ledgerforge audit episodes/generated/<EP-id>      # independent public-data audit
uv run ledgerforge demo --count 3                        # oracle run, logs outputs/trajectories/demo.jsonl
```

```python
from ledgerforge.env.env import AuditEnv

env = AuditEnv("train")  # "eval" withholds reward until the run report
obs, info = env.reset(seed=7, config={"faults": {"duplicate_invoice": 1}})
obs, reward, terminated, truncated, info = env.step(
    {"tool": "list_records", "args": {"table": "invoices", "limit": 50}}
)
```

Tools: `list_records`, `get_record`, `get_document`, `calculator`, `submit`. Contracts are in
[docs/CONTRACTS.md](docs/CONTRACTS.md) and the scoring rules in [docs/EVALUATION.md](docs/EVALUATION.md).

## How it works

1. `sim/world.py` builds a balanced double-entry company (≥200 ledger rows, FX table, distractors).
2. `sim/faults.py` injects faults by mutating the causal records and returns a canonical truth issue.
3. `verification/auditor.py` independently recomputes every issue from public files only. An
   episode ships only if the audit equals the truth exactly (acceptance gate).
4. `evaluation/service.py` runs in a separate OS process and holds the truth. The env process never
   sees it.
5. `evaluation/matcher.py`: one-to-one matching, then `reward = clip(2·F1 − 1 − 0.002·steps, −1, 1)`.

## Status (honest)

| Area | State |
|---|---|
| Generator, 4 faults + 2 interactions, auditor gate | working; 120/120 gate passes (8 configs × 15 seeds) |
| Env, 5 tools, evaluator process, matcher, reward | working minimal slice, 123 tests |
| Trajectory log + deterministic replay | working |
| `id_salt` / `order_salt` metamorphic pairs | working; oracle reward invariant |
| Open train/dev episodes (10 + 10) | in `episodes/`, seeds in `episodes/splits.json`; `uv run ledgerforge release` regenerates them and their truth into `private/` |
| Baselines (random, reconciler, flag-all) and benchmark | **planned** (Codex, see docs/ai/TASKS.md) |
| Adversarial security suite (spec §11.4) | partial: malformed submissions, step limits, isolation |
| Docker image | Dockerfile written, **not built yet** |

No benchmark numbers are claimed yet.

## Layout

`src/ledgerforge/{contracts,sim,verification,env,evaluation,agents,benchmark}`, `schemas/` (JSON
Schema), `docs/` (spec, architecture, ADRs), `tests/`. Licence: MIT. See THIRD_PARTY_NOTICES.md.
