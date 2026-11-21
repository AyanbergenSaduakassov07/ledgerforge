# LedgerForge

A causal financial-audit RL environment. Each episode is a fictional company's accounting period with
injected, independently verified faults. An agent inspects the books through five tools and submits
evidence-backed findings, which earn the official F1-based reward.

All entities and amounts are synthetic: no real company data, no PII.

## Hackathon task

REC Genesis Hackathon 2026, FinTech track: build a reproducible RL environment in which an agent
finds duplicate invoices, payment allocation errors, wrong FX dates/rates and wrong reporting periods
in generated financial records. Scoring uses a fixed terminal reward. Design rationale:
[docs/DESIGN_NOTE.md](docs/DESIGN_NOTE.md).

## Architecture

```
sim/world.py ── balanced double-entry company ──► sim/faults.py ── causal fault injection
                                                        │ truth + provenance
verification/auditor.py ◄── public files only ──────────┤  acceptance gate: audit == truth
                                                        ▼
evaluation/service.py (separate process, holds truth) ◄─JSON lines─► env/env.py (public data only)
evaluation/matcher.py: one-to-one matching → reward                      ▲ 5 tools
                                                                    agents/* policies
```

Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Decisions: [docs/DECISIONS.md](docs/DECISIONS.md).

## Installation

Python 3.11 and [uv](https://docs.astral.sh/uv/) 0.11. The runtime has no third-party dependencies;
dev tools (pytest, ruff, jsonschema) are pinned in `uv.lock`.

```bash
uv sync --frozen
```

## One-command verification (offline, no API keys, no GPU)

```bash
make verify        # uv sync --frozen, ruff, pytest, oracle demo with trajectory replay
```

Expected output ends with three `reward=1.000 ... replay=identical` lines.

Container equivalent: `docker build -t ledgerforge . && docker run --rm --network none ledgerforge`.
**Not verified:** the image build has not completed on the author's machine, because a network stall
blocked package downloads.

## Dataset format

Each episode directory contains `manifest.json`, `policy.json`, `ledger.csv`, `invoices.jsonl`,
`payments.jsonl` and `fx.csv`. Schemas are in `schemas/`; field rules are in
[docs/CONTRACTS.md](docs/CONTRACTS.md) §1–2.
- Money is in integer minor units, and the ledger is in the base currency.
- Missing references are explicit nulls.

Open sets: `episodes/train/` (10) and `episodes/dev/` (10). Their seeds and configs are in
`episodes/splits.json`. Each set includes clean books, every fault type, both interactions and a
10-issue expert mix.

```bash
uv run ledgerforge release      # regenerate both sets; truth goes to git-ignored private/
uv run ledgerforge generate --seed 3 --count 2 --config '{"faults":{"fx_rate":1}}'
uv run ledgerforge audit episodes/train/<EP-id>   # independent public-data audit
```

## Error types

| type | affected_ids | amount (base ccy) |
|---|---|---|
| `duplicate_invoice` | original + duplicate doc | AP credit of the later copy |
| `payment_allocation` | payment + intended invoice | expected − recorded AP relief |
| `fx_rate` | invoice | \|AP booked − AP at correct rate\| |
| `reporting_period` | invoice | AP booked |

Look-alikes that are *not* errors are generated on purpose: credit note plus reissue, recurring
monthly services, supplier advances. There are also two interactions: a duplicate that is later paid,
and an FX error inside a misallocated payment.

## RL interface

```python
from ledgerforge.env.env import AuditEnv

env = AuditEnv("train")  # "eval" withholds reward until the run report
obs, info = env.reset(seed=7, config={"faults": {"duplicate_invoice": 1}})
obs, reward, terminated, truncated, info = env.step(
    {"tool": "list_records", "args": {"table": "invoices", "limit": 50}}
)
```

Tools: `list_records` (page ≤ 50), `get_record`, `get_document`, `calculator`, and `submit`, whose
args are the submission `{episode_id, findings}`. An episode allows at most 100 steps and 60 s.
Full contract: [docs/CONTRACTS.md](docs/CONTRACTS.md) §4–5.

## Reward computation

`reward = clip(2·F1 − 1 − 0.002·inspection_steps, −1, 1)`. A malformed submission scores −1.

A finding is a true positive only if all of these hold:
- the type matches;
- the affected-id set is exact;
- the amount is within 1 minor unit;
- the currency matches;
- the evidence covers an allowed set.

Matching is one-to-one, so repeated findings count as false positives. Edge cases are tabulated in
[docs/EVALUATION.md](docs/EVALUATION.md).

## Baseline policies

| Policy | File | What it does |
|---|---|---|
| Oracle | `agents/oracle.py` | Evaluator-side upper bound: submits the truth (not an ordinary agent) |
| Reconciler | `agents/reconciler.py` | Rule-based: reconciles documents, FX and periods from public data |
| Random explorer | `agents/random_explorer.py` | Seeded control: samples 8 record pages, submits no findings |
| Flag-all attacker | `agents/flag_all.py` | Submits the maximum number of guessed findings |

Measured with `uv run ledgerforge bench`. The table shows means over episodes, taken from the
committed `outputs/benchmarks/summary.md`. Raw per-episode data is in `metrics.json` and
`trajectories.jsonl`.

| Policy | dev F1 | dev reward | mirror (20) F1 | mirror reward | steps |
|---|---:|---:|---:|---:|---:|
| Oracle (upper bound) | 1.000 | 1.000 | 1.000 | 1.000 | 0 |
| Reconciler (rule-based) | 1.000 | 0.967 | 1.000 | 0.968 | ≈16 |
| Random explorer | 0.200 | −0.603 | 0.250 | −0.504 | 8 |
| Flag-all attacker | 0.000 | −1.000 | 0.000 | −1.000 | 2 |

**How to read this:**
- The reconciler's perfect F1 is expected and is not evidence of general audit ability. It was
  written against the same published rules (CONTRACTS §1–3) that the generator and auditor follow,
  and it can read every row within 16 of its 100 steps. It shows that every label can be derived from
  public data, which is what the acceptance gate promises.
- The open challenge is for learned or LLM agents that do not have these rules hard-coded.
- The random explorer scores F1 > 0 only on clean episodes, where an empty submission is correct.
- The mirror split is the local closed-eval mirror (≥5 clean, ≥5 interacting). Its 20 paired
  id/order transforms passed replay and oracle-reward invariance.

## Replay and benchmark

```bash
uv run ledgerforge demo --count 3   # oracle episodes → outputs/trajectories/demo.jsonl, replayed and compared
```

uv run ledgerforge bench            # all 4 policies on train/dev/mirror + 20 metamorphic pairs → outputs/benchmarks/

## Demonstration

```bash
make walkthrough    # uv run python -m ledgerforge.walkthrough [--seed N]
```

Runs the eight pitch points on one interaction episode, in order:
1. generate a company;
2. show an invoice → ledger → payment chain;
3. let the rule-based reconciler investigate;
4. show the injected duplicate+allocation interaction (trusted-runner view);
5. show its evidence-backed findings;
6. show the evaluator's reward;
7. show flag-all and the oracle on the same episode;
8. rename every id, shuffle every table, and show the reward is unchanged.

The command exits non-zero if the reward changes after renaming.

## Optional cloud / UI

None. Official verification needs no cloud gateway, frontend or API key.

## Status

| Area | State |
|---|---|
| Generator, 4 faults + 2 interactions, auditor acceptance gate | Implemented, verified by tests |
| Environment, 5 tools, isolated evaluator, matcher, reward | Implemented, verified by tests |
| Trajectory log + deterministic replay | Implemented, verified by tests |
| `id_salt` / `order_salt` metamorphic pairs | Implemented; oracle reward invariant (tested) |
| 10 train + 10 dev episodes | Implemented; byte-identical regeneration tested |
| 4 baseline policies | Implemented, tested |
| Adversarial suite (flag-all, permutations, malformed, limits) | Implemented, tested |
| Benchmark runner + `trajectories.jsonl` | Implemented; rerun reproduces all scores (runtimes vary) |
| Docker image | Not verified |

Test count: run `uv run pytest -q`.

## Third-party components

Runtime: Python standard library only. Dev: pytest, ruff, jsonschema (MIT). No code was copied from
other projects. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). License: MIT.

## Limitations

- Each issue has exactly one minimal evidence set (ADR-006), so alternative valid proofs are not
  credited.
- Ledgers are roughly 250–600 rows: inside the 200–2000 range, but far from the upper bound.
- The agent and the evaluator run as the same OS user. Isolation is a process boundary, not a
  sandbox ([docs/SECURITY.md](docs/SECURITY.md)).
- Allocation faults cover base-currency payments only.
- A rule-based policy that encodes the published rules saturates the current benchmark (F1 1.0).
  Harder look-alikes, or making ledgers less complete within the step budget, would be the next lever.
- Synthetic books follow one AP-centric chart of accounts and do not cover revenue, payroll or tax.

## Reproduce

```bash
uv sync --frozen && make verify                              # tests + oracle demo
uv run ledgerforge release && git status --short episodes/  # no diff = episodes reproduced
```

Same seed and config produce byte-identical episodes on any machine with Python 3.11
(CONTRACTS §9).

## Layout

`src/ledgerforge/{contracts,sim,verification,env,evaluation,agents,benchmark}`, `schemas/`, `docs/`,
`episodes/`, `tests/`.
