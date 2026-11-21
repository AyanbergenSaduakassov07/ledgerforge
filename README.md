# LedgerForge

**A causal, self-verifying reinforcement-learning environment for financial-audit agents.**

Every episode is a fictional company's accounting quarter: a balanced double-entry ledger, supplier
invoices, payments with remittance advice, and a daily FX table. Faults are injected *causally*:
the generator edits the books the way a real clerk's mistake would. An independent auditor must
re-derive every injected fault from the public files before the episode ships. The agent investigates
through five tools and submits evidence-backed findings, and an evaluator in a separate OS process
scores them with the official F1-based reward.

> REC Genesis Hackathon 2026, FinTech track. All companies, people and amounts are synthetic.
> No real company data, no PII. Runtime: the Python standard library only. Offline, CPU-only, no API keys.

| | |
|---|---|
| Fault types | duplicate invoice · payment allocation · FX date/rate · reporting period, plus 2 interactions |
| Hard negatives | 7 families of legitimate look-alikes (recurring services, credit-note reissues, instalments, …) |
| Ground truth | acceptance gate: an independent auditor must reproduce the truth exactly |
| Agent interface | Gym-style `reset` / `step`, 5 tools, 100 steps, 60 s |
| Reward | `clip(2·F1 − 1 − 0.002·steps, −1, 1)`, one-to-one matching, 1-minor-unit tolerance |
| Isolation | truth lives only in a separate evaluator process |
| Robustness | id-renaming and row-shuffling twins give identical rewards (20/20 pairs) |
| Verification | `make verify` (local) or `docker run --network none` (container): both pass |

---

## Contents

1. [Quick start for judges](#1-quick-start-for-judges)
2. [The problem](#2-the-problem)
3. [How an episode is made](#3-how-an-episode-is-made)
4. [The simulated company](#4-the-simulated-company)
5. [Fault types](#5-fault-types)
6. [Legitimate look-alikes](#6-legitimate-look-alikes-hard-negatives)
7. [Ground truth you can trust: the acceptance gate](#7-ground-truth-you-can-trust-the-acceptance-gate)
8. [Agent interface](#8-agent-interface)
9. [Submission format](#9-submission-format)
10. [Reward computation](#10-reward-computation)
11. [Anti-cheating and robustness](#11-anti-cheating-and-robustness)
12. [Baselines and results](#12-baselines-and-results)
13. [Rule ablation: are the look-alikes load-bearing?](#13-rule-ablation-are-the-look-alikes-load-bearing)
14. [Live demonstration](#14-live-demonstration)
15. [Dataset](#15-dataset)
16. [Reproducibility](#16-reproducibility)
17. [Repository layout](#17-repository-layout)
18. [How it was built](#18-how-it-was-built)
19. [Status](#19-status)
20. [Limitations and next steps](#20-limitations-and-next-steps)
21. [Third-party components and licence](#21-third-party-components-and-licence)

---

## 1. Quick start for judges

Requirements: Python 3.11 and [uv](https://docs.astral.sh/uv/) 0.11, or Docker.

```bash
make verify          # uv sync --frozen, ruff lint + format check, full pytest suite, oracle demo
make walkthrough     # the 8-step pitch on one episode (≈2 s)
make bench           # all baselines on train/dev/mirror + 20 metamorphic pairs + failure analysis
make ablation        # the rule-ablation table in section 13
```

`make verify` ends with three lines like
`seed=0 episode=EP-… reward=1.000 tp=1 fp=0 fn=0 replay=identical`.

Container, fully offline:

```bash
docker build -t ledgerforge .
docker run --rm --network none ledgerforge   # pytest (176 tests) + oracle demo with replay
```

Verified on 2026-11-21: the image builds, and the container passes all 176 tests and the replay demo
with networking disabled.

---

## 2. The problem

Audit agents need an environment, not a spreadsheet of labels. Static audit datasets have three
problems an RL environment must solve:

- **Unverifiable labels.** If the generator says "this is an error" but the public data does not
  prove it, an agent is trained on noise. LedgerForge accepts an episode only if an independent
  auditor, reading public files alone, reproduces every label exactly.
- **Shortcut learning.** If every invoice with a repeated total is a duplicate, an agent learns
  "flag repeated totals". LedgerForge generates legitimate transactions that look like each fault,
  so each shortcut is punished (measured in section 13).
- **Leakage and gaming.** If the truth sits in the agent's memory, or the reward can be farmed by
  spamming findings, the benchmark measures nothing. Truth stays in a separate process, matching is
  one-to-one, and a malformed or spammy submission scores −1.

---

## 3. How an episode is made

```
 seed + config
      │
      ▼
 sim/world.py      build a balanced company: vendors, FX table, invoices, payments, payroll,
      │            depreciation, bank fees. Every journal balances.
      ▼
 sim/faults.py     inject faults causally: copy an invoice, retag a payment row, book at the
      │            wrong rate, move a posting date. Record truth + provenance (before/after rows).
      ▼
 sim/salt.py       optional: rename every id (digit derangement) and shuffle every table
      │
      ▼
 verification/     independent auditor, public files + published rules only.
 auditor.py        audit == truth (type, ids, amount, currency) and evidence resolves? and the
      │            ledger is 200–2000 rows, 20–200 documents, every journal balanced?
      │            no → regenerate with the next attempt (up to 20)
      ▼
 episode/          public: manifest, policy, ledger.csv, invoices.jsonl, payments.jsonl, fx.csv
 private/          truth.json + provenance.json (evaluator only, git-ignored)
```

At run time:

```
 agent policy ──action──► env/env.py (public data only) ──JSON lines──► evaluation/service.py
      ▲                        5 tools, step/time limits          (separate OS process, holds truth)
      └──observation, reward◄──────────────────────────────────── evaluation/matcher.py → reward
```

Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Design rationale:
[docs/DESIGN_NOTE.md](docs/DESIGN_NOTE.md). Every decision: [docs/DECISIONS.md](docs/DECISIONS.md)
(ADR-001 … ADR-017).

---

## 4. The simulated company

Each episode is one quarter of an accounts-payable department.

- **Vendors**: 7–12 fictional suppliers, each with its own currency (base or one of
  USD/EUR/CNY/RUB/JPY/KWD) and timezone offset. Four industries (industrial procurement,
  construction, manufacturing, retail services) with curated line-item catalogues.
- **Invoices**: 30–100 by difficulty, 1–6 line items each. Posted as *debit expense / credit AP* in
  the base currency at the recognition-date FX rate.
- **Payments**: full, instalment, multi-invoice remittances, and unapplied advances. Each payment
  carries remittance advice (`invoice_refs`) and is posted as *debit AP / credit bank*, with FX
  differences to `7600`.
- **Background**: monthly payroll and payout, depreciation, and bank-fee journals. Ledgers are about
  200 / 400 / 800 / 1600 rows from basic to expert (ADR-016).
- **FX table**: daily rates with gaps (weekends), so "the most recent earlier rate" matters.

The rules an auditor needs are **published in every episode** as `policy.json`:

```json
{
  "timezone_offset": "+05:00",
  "recognition_date": "local calendar date of invoice issued_at / payment timestamp at timezone_offset",
  "period_bounds": "inclusive",
  "fx_rule": "rate of the recognition date; if fx.csv has no row that date, the most recent earlier row",
  "rounding": "ROUND_HALF_EVEN to the target currency minor unit",
  "ledger_currency": "all ledger rows are in base_currency",
  "journal_grouping": "rows group by payment_id, else invoice_id, else timestamp; every group balances",
  "ap_relief": "AP debit for a payment ref = round_half_even(ref_amount * invoice AP credit / invoice total)",
  "amount_tolerance_minor": 1
}
```

No hidden rule decides any label. Money is always integer minor units, and the ledger is always in
the base currency (ADR-002).

---

## 5. Fault types

| Type | How it is injected | `affected_ids` | Expected amount (base currency) |
|---|---|---|---|
| `duplicate_invoice` | A second invoice with the same supplier, currency, total and line items under a variant number (`-1`, `A`), posted again | original + duplicate doc | AP credit of the later copy |
| `payment_allocation` | The remittance says invoice I, but the ledger moves part or all of the AP relief to another invoice or to advances (variants: missing, partial, misapplied; any payment currency) | payment + intended invoice | expected − recorded AP relief |
| `fx_rate` | The invoice is booked at the rate of a wrong date | invoice | \|AP booked − AP at the correct rate\| |
| `reporting_period` | An invoice issued outside the period is posted inside it | invoice | AP booked |

**Interactions** (two issues that touch the same documents):
- `duplicate_with_allocation`: a duplicate that is later paid through a misallocated payment.
- `fx_with_period`: an FX error on an invoice that is also in the wrong period.

Preconditions stop cascades: each injected fault yields exactly the declared issues (ADR-008), and
the gate checks this again.

---

## 6. Legitimate look-alikes (hard negatives)

| Look-alike | Looks like | Why it is *not* an error | Shortcut it traps |
|---|---|---|---|
| Recurring monthly service | duplicate | same amount and vendor, different service month in the line items | "same supplier + total = duplicate" |
| Credit note + reissue | duplicate | the credit note cancels the original, so the reissue is the only open charge | ignoring credit notes |
| Instalment payments | allocation | two partial remittances for one invoice, each relieving its share | expecting one full payment |
| Multi-invoice remittance | allocation | one payment settling two invoices | per-payment single-invoice logic |
| Supplier advance | allocation | a payment with no remittance reference legitimately goes to `2190` | "every unapplied payment is wrong" |
| Timezone-boundary invoice | period | the vendor's printed date is outside the period, the local date inside | using the printed date |
| Early next-period invoice | period | received in `invoices.jsonl`, correctly not posted yet | flagging all out-of-period documents |

---

## 7. Ground truth you can trust: the acceptance gate

`verification/auditor.py` is a second, independent implementation of the published rules. It never
sees the generator's truth. An episode is accepted only if:

1. auditor issues == truth issues, compared on type, affected ids, amount and currency;
2. every journal balances and no invariant is violated;
3. each issue's evidence set resolves to real public ids and is derivable by the auditor;
4. the ledger is 200–2000 rows and there are 20–200 documents (ADR-014).

Otherwise the generator retries with the next attempt number, up to 20 times. A salted
(renamed and shuffled) episode goes through the gate again. This is test-enforced:
`tests/test_generator.py::test_truth_equals_independent_audit`.

The generator and the auditor share only `contracts/money.py` (rounding, FX lookup, local dates),
which has its own unit tests (ADR-009).

---

## 8. Agent interface

```python
from ledgerforge.env.env import AuditEnv

env = AuditEnv("train")  # "eval": no reward until the run report
obs, info = env.reset(seed=7, config={"faults": {"fx_rate": 1}, "difficulty": "advanced"})
# obs: task text, manifest, policy (published rules), table sizes, tool list, steps_remaining

obs, reward, terminated, truncated, info = env.step(
    {"tool": "list_records", "args": {"table": "invoices", "limit": 50}}
)
```

| Tool | Args | Returns |
|---|---|---|
| `list_records` | `table`, `cursor`, `limit ≤ 50` | a page of rows + `next_cursor` |
| `get_record` | `table`, `id` | one row (ledger `row_id`, invoices `invoice_id`, payments `payment_id`, fx `date:SRC:TGT`) |
| `get_document` | `doc_id` | an invoice or payment; also `"manifest"` / `"policy"` |
| `calculator` | `expression` (≤256 chars) | exact decimal arithmetic: `+ - * /` and parentheses |
| `submit` | `{episode_id, findings}` | ends the episode; reward in train mode |

Limits: 100 steps and 60 s per episode. Tool errors (bad table, bad cursor, unknown id) come back as
observations with an error code; they never crash the episode. A truncated episode is scored as an
empty submission (ADR-013). Full contract: [docs/CONTRACTS.md](docs/CONTRACTS.md) §4–5.

Scenario config: `difficulty` (basic / intermediate / advanced / expert), `industry`,
`base_currency`, `faults` (count per type), `interactions`, `distractors`, `n_invoices` (20–100),
`id_salt`, `order_salt`.

---

## 9. Submission format

```json
{
  "episode_id": "EP-029cb5604418",
  "findings": [
    {
      "type": "fx_rate",
      "affected_ids": ["DOC-62992300"],
      "claimed_amount_minor": 9063230,
      "currency": "KZT",
      "evidence_ids": ["DOC-62992300", "R5061322", "2026-02-03:JPY:KZT"],
      "explanation": "Posted value differs from the published recognition-date rate."
    }
  ]
}
```

That finding was submitted by the rule-based reconciler on seed 7. It scored TP 1, FP 0, FN 0 and
reward 0.964 after 18 inspection steps.

- At most 30 findings, 1–10 affected ids and 0–10 evidence ids each; explanations up to 1000 chars.
- Evidence may be document ids, ledger row ids or FX ids `date:SRC:TGT`.
- Business ids (`invoice_id`, `payment_id`) are accepted and normalised to doc ids. Id lists are
  sets; type and currency are case-insensitive.
- Extra keys, a wrong `episode_id`, or a float/bool amount make the submission malformed: reward −1.

---

## 10. Reward computation

```
reward = clip(2·F1 − 1 − 0.002·inspection_steps, −1, 1)
F1     = 2·TP / (2·TP + FP + FN)        (no truth and no findings → F1 = 1)
```

A finding is a true positive only if **all** hold:
- same `type`;
- the same set of `affected_ids`;
- `|claimed − expected| ≤ 1` minor unit (absolute values);
- the same `currency`;
- `evidence_ids` contain an allowed evidence set.

Matching is a one-to-one maximum matching (Kuhn's algorithm, deterministic order), so a repeated
finding is a false positive. The explanation is ignored for scoring, so a persuasive explanation
cannot rescue a wrong amount (tested).

**Worked example** (the walkthrough episode): 2 faults, both found, no false positives, 20
inspection steps → F1 = 1 → reward = 2·1 − 1 − 0.04 = **0.960**. The flag-all attacker on the same
episode: 30 findings, 0 correct → F1 = 0 → reward = −1 − 0.004 → clipped to **−1.000**.

Edge cases (empty truth, malformed payloads, truncation, duplicates): [docs/EVALUATION.md](docs/EVALUATION.md).

---

## 11. Anti-cheating and robustness

| Threat | Defence | Checked by |
|---|---|---|
| Reading the truth | Truth exists only in `python -m ledgerforge.evaluation.service`; the env holds public data | `test_baseline_imports_stay_on_the_agent_side` (agent code never imports sim/verification/evaluation) |
| Spamming findings | One-to-one matching; FP lowers F1; flag-all scores −1 | adversarial suite, benchmark |
| Memorising ids or row order | `id_salt` renames every id (digit derangement), `order_salt` shuffles every table | 20/20 metamorphic pairs: identical oracle reward and replay |
| Malformed or oversized payloads | Strict validator; anything off-contract scores −1 | `tests/test_contracts.py`, `tests/test_matcher.py`, adversarial suite |
| Hanging the evaluator | 10 s request timeout; 60 s episode deadline; 100-step cap | `tests/test_env.py` |
| Arguing instead of proving | Explanations are not scored; amounts and evidence are | adversarial suite |
| Non-determinism | Seeded RNG per phase; byte-identical regeneration | `tests/test_release.py` |

Known limit: agent and evaluator run as the same OS user, so isolation is a process boundary, not a
sandbox ([docs/SECURITY.md](docs/SECURITY.md)).

---

## 12. Baselines and results

| Policy | File | What it does |
|---|---|---|
| Oracle | `agents/oracle.py` | Evaluator-side upper bound: submits the truth (not an ordinary agent) |
| Reconciler | `agents/reconciler.py` | Rule-based: reads every table, applies the published rules, submits findings with evidence |
| Random explorer | `agents/random_explorer.py` | Seeded control: samples 8 record pages, submits nothing |
| Flag-all attacker | `agents/flag_all.py` | Submits 30 guessed findings across all types |

Measured with `make bench` (committed: `outputs/benchmarks/summary.md`, `metrics.json`,
`trajectories.jsonl`). Means over episodes:

| Policy | train F1 | dev F1 | dev reward | mirror (20) F1 | mirror reward | inspection steps |
|---|---:|---:|---:|---:|---:|---:|
| Oracle (upper bound) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0 |
| Reconciler | 1.000 | 1.000 | 0.955 | 1.000 | 0.950 | ≈22–25 |
| Random explorer | 0.200 | 0.200 | −0.603 | 0.250 | −0.504 | 8 |
| Flag-all attacker | 0.000 | 0.000 | −1.000 | 0.000 | −1.000 | 2 |

How to read this:
- **The reconciler proves that labels can be derived, not that auditing is easy.** It was written
  against the same published rules as the generator and the auditor, and reads every row within
  about 25 of its 100 steps. Its perfect F1 is the acceptance gate's promise made visible: every
  label is derivable from public data. The 0 false positives across 40 episodes show the
  look-alikes are distinguishable by the published rules.
- **The open challenge is for learned or LLM agents** that must discover these rules from
  `policy.json` and the data. Section 13 shows how hard each rule is to skip.
- The random explorer scores F1 > 0 only on clean episodes, where an empty submission is correct.
- The mirror split is the local closed-eval mirror: 20 configs across all industries, difficulties,
  base currencies (KZT, USD, EUR), interactions and multi-fault mixes.
- Failure analysis (`outputs/reports/failure_analysis.md`): 71 TP, 0 FP, 0 FN for the reconciler.

---

## 13. Rule ablation: are the look-alikes load-bearing?

`make ablation` runs the reconciler with one published rule at a time replaced by the shallow
heuristic an inexperienced auditor (or a pattern-matching model) would use, on all 40 episodes
(train + dev + mirror). Committed: `outputs/reports/ablation.md`.

| Variant | Shortcut instead of the published rule | TP | FP | FN | mean F1 | mean reward |
|---|---|---:|---:|---:|---:|---:|
| reconciler | none | 71 | 0 | 0 | **1.000** | 0.953 |
| naive duplicates | same supplier + total, ignore line items and credit notes | 71 | 120 | 0 | 0.418 | −0.201 |
| naive period | printed document date instead of the policy timezone | 71 | 81 | 0 | 0.487 | −0.064 |
| naive FX | period-end rate instead of the recognition-date rate | 40 | 888 | 31 | 0.083 | −0.866 |
| naive allocation | remittance at the payment-date rate instead of proportional AP relief | 64 | 469 | 7 | 0.199 | −0.640 |
| all four | all of the above | 27 | 1101 | 44 | **0.045** | −0.939 |

Each shortcut is caught by its look-alike family: recurring services and credit-note reissues
trap naive duplicate matching, timezone-boundary invoices trap printed dates, daily FX gaps trap a
single closing rate, and FX settlement differences trap allocation checks at the payment rate.
**No single shortcut solves the benchmark; skipping any one published rule turns a positive reward
negative.** (ADR-017)

---

## 14. Live demonstration

```bash
make walkthrough          # or: uv run python -m ledgerforge.walkthrough --seed 2006
```

Eight steps on one construction-company episode with an interacting duplicate + allocation fault:

1. generate a company (period, base currency, table sizes);
2. follow one invoice → ledger → payment chain;
3. the reconciler investigates through the five tools only (21 steps: 20 page reads + submit);
4. show the injected discrepancy (trusted-runner view);
5. show the evidence-backed submission;
6. reward from the separate evaluator: **+0.960** (TP 2, FP 0, FN 0);
7. flag-all on the same episode: **−1.000** (FP 30); oracle: **+1.000**;
8. rename every id and shuffle every table: the reconciler again scores **+0.960**, identical.

Excerpt:

```
== 6. Reward computed by the separate evaluator process
   reward=+0.960  tp=2 fp=0 fn=0  F1=1.00  inspection_steps=20
== 7. Attack and upper bound on the same episode
   flag-all : reward=-1.000  tp=0 fp=30 fn=2  F1=0.00  inspection_steps=2
   oracle   : reward=+1.000  tp=2 fp=0 fn=0  F1=1.00  inspection_steps=0
== 8. Same problem after renaming every id and shuffling every table
   reconciler: reward=+0.960  tp=2 fp=0 fn=0  F1=1.00  inspection_steps=20
   reward identical to step 6: True
```

The command exits non-zero if the reward changes after renaming.

---

## 15. Dataset

Each episode directory holds six public files (schemas in `schemas/`, field rules in
[docs/CONTRACTS.md](docs/CONTRACTS.md) §1–2):

| File | Content |
|---|---|
| `manifest.json` | episode id, versions, base currency, period, timezone, row counts |
| `policy.json` | the published audit rules (section 4) |
| `ledger.csv` | `row_id, timestamp, account, debit_minor, credit_minor, currency, entity_id, invoice_id, payment_id` |
| `invoices.jsonl` | `doc_id, invoice_id, entity_id, issued_at, due_at, currency, total_minor, line_items[]` |
| `payments.jsonl` | `doc_id, payment_id, timestamp, currency, amount_minor, invoice_refs[]` |
| `fx.csv` | `date, source_currency, target_currency, rate` |

Sample rows:

```
row_id,timestamp,account,debit_minor,credit_minor,currency,entity_id,invoice_id,payment_id
R2198597,2026-01-01T06:11:40+05:00,1300 Inventory,320827681,0,KZT,V-6230,SF-3011,
R2680563,2026-01-01T06:11:40+05:00,2100 Accounts Payable,0,320827681,KZT,V-6230,SF-3011,
```

Open sets: `episodes/train/` (10) and `episodes/dev/` (10), with seeds and configs in
`episodes/splits.json`. Together they cover clean books, every fault type, both interactions, all
difficulties and a 10-issue expert mix. Truth is regenerated into git-ignored `private/`.

```bash
uv run ledgerforge release                                     # regenerate both sets
uv run ledgerforge generate --seed 3 --count 2 --config '{"faults":{"fx_rate":1}}'
uv run ledgerforge audit episodes/train/<EP-id>                # independent public-data audit
```

---

## 16. Reproducibility

- Same seed + config → byte-identical episode on any machine with Python 3.11 (CONTRACTS §9). Every
  random phase has its own seeded RNG.
- `tests/test_release.py` regenerates every committed episode and compares bytes.
- Every trajectory is logged (`outputs/trajectories/*.jsonl`) and replayed; replay must be identical.
- The benchmark rerun reproduces all scores (runtimes vary).

```bash
uv sync --frozen && make verify
uv run ledgerforge release && git status --short episodes/     # no diff = reproduced
```

---

## 17. Repository layout

| Path | Role |
|---|---|
| `src/ledgerforge/contracts/` | frozen shapes, money/FX/time semantics, submission validator |
| `src/ledgerforge/sim/` | company world, causal faults, salting, episode I/O |
| `src/ledgerforge/verification/` | independent auditor (acceptance gate) |
| `src/ledgerforge/env/` | Gym-style environment, tools, calculator |
| `src/ledgerforge/evaluation/` | evaluator process, matcher, reward |
| `src/ledgerforge/agents/` | oracle, reconciler (with naive switches), random explorer, flag-all |
| `src/ledgerforge/benchmark/` | trajectory logging/replay, benchmark runner, failure analysis, ablation |
| `src/ledgerforge/walkthrough.py` | the 8-step demo |
| `schemas/` | JSON schemas for every public file and the submission |
| `episodes/` | 20 open episodes + `splits.json` |
| `outputs/` | committed benchmark, failure analysis and ablation reports |
| `docs/` | contracts, architecture, design note, ADRs, evaluation, security, scenarios |
| `tests/` | 176 tests: contracts, money, generator gate, env, matcher, adversarial, baselines, release |

---

## 18. How it was built

Two AI coding agents under one human owner, with a written contract first:

- **Claude** (lead architect) owned the contracts, the simulator, the auditor and the docs.
- **Codex** owned the environment hardening, baselines, adversarial suite, benchmark runner and failure
  analysis (tasks CX-01…05). The remaining Codex scope (ablation, CX-06) was later handed to Claude.
- Each task was built in its own git worktree and merged one at a time after review and
  `make verify`. Every merge is logged in [docs/ai/INTEGRATION.md](docs/ai/INTEGRATION.md); the
  backlog is [docs/ai/TASKS.md](docs/ai/TASKS.md).
- Every design choice is an ADR in [docs/DECISIONS.md](docs/DECISIONS.md), including the ones that
  fixed our own mistakes. ADR-015 records a latent unit bug found while hardening allocation faults.

---

## 19. Status

| Area | State |
|---|---|
| Generator: 4 faults, 2 interactions, 7 look-alike families | Implemented, verified by tests |
| Independent auditor acceptance gate + size gate | Implemented, verified by tests |
| Environment: 5 tools, limits, isolated evaluator, matcher, reward | Implemented, verified by tests |
| Trajectory log + deterministic replay | Implemented, verified by tests |
| `id_salt` / `order_salt` metamorphic pairs | Implemented; 20/20 pairs invariant |
| 10 train + 10 dev episodes | Implemented; byte-identical regeneration tested |
| 4 baseline policies + rule ablation | Implemented, tested, results committed |
| Adversarial suite (flag-all, permutations, malformed, limits) | Implemented, tested |
| Docker image, offline run | Verified 2026-11-21 (`--network none`, 176 tests + demo pass) |

---

## 20. Limitations and next steps

- **Rule-based saturation.** A policy that encodes all published rules scores F1 1.0. That is by
  design (labels must be derivable), but it means the benchmark discriminates between agents by
  how well they *discover* the rules, not by hidden traps. Section 13 quantifies the cost of each
  missing rule.
- **One evidence set per issue** (ADR-006): alternative valid proofs are not credited.
- **Process isolation, not a sandbox**: agent and evaluator run as the same OS user.
- **Scope**: one AP-centric chart of accounts. No revenue, payroll-detail or tax faults.
- **Ledger bulk**: rows added at higher difficulty are routine bank-fee journals, not new look-alikes (ADR-016).

Next steps: an LLM-agent adapter (optional, outside official verification), receivables and VAT
faults, and partial-observability variants where some documents must be requested.

---

## 21. Third-party components and licence

Runtime: Python standard library only (ADR-001). Dev and test: pytest, ruff, jsonschema (MIT),
pinned in `uv.lock`. No code was copied from other projects; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Licence: MIT.
