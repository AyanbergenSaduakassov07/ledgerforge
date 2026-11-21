# LedgerForge contracts (frozen v1.0.0)

Status: **frozen for the vertical slice** on 2026-11-21. Changing anything here that affects scoring
needs a new ADR in `DECISIONS.md` and a lead-architect (Claude) review. Code of record:
`src/ledgerforge/contracts/` (Python) and `schemas/*.schema.json` (JSON Schema 2020-12). Executable
checks: `tests/test_contracts.py`, `tests/test_matcher.py`, `tests/test_env.py`.

## 1. Money, time, FX (`contracts/money.py`)

| Rule | Value |
|---|---|
| Amounts | integers in minor units; exponents KZT/USD/EUR/RUB/CNY 2, JPY 0, KWD 3 |
| Ledger currency | every ledger row is in `base_currency` (functional currency); native amounts live on documents |
| Rate | decimal string, target units per **one** source unit; `fx.csv` holds business days, period ±21 days |
| Conversion | `round_half_even(amount_minor × rate × 10^(exp_target − exp_source))` |
| Recognition date | calendar date of `issued_at` (invoice) / `timestamp` (payment) at the episode `timezone_offset` (policy.json) |
| FX date | the recognition date; no row that day → most recent earlier row |
| Period | `period_start ≤ recognition date ≤ period_end`, inclusive |
| Timestamps | ISO 8601 with explicit offset, seconds precision; fixed offsets, no DST, no tz database |

## 2. Public files

`manifest.json`, `policy.json`, `ledger.csv`, `invoices.jsonl`, `payments.jsonl`, `fx.csv`. Schemas:
`schemas/{manifest,ledger_row,invoice,payment,fx_row}.schema.json`. Missing references are explicit
nulls (JSON `null`; in CSV an empty field).

- `ledger.csv`: `row_id, timestamp, account, debit_minor, credit_minor, currency, entity_id, invoice_id, payment_id`.
  Exactly one of debit/credit is non-zero.
- `invoices.jsonl`: `doc_id, invoice_id, entity_id, issued_at, due_at, currency, total_minor, line_items[]`
  (`description, quantity, unit_price_minor, amount_minor`). Credit notes have negative quantities and total.
- `payments.jsonl`: `doc_id, payment_id, timestamp, currency, amount_minor, invoice_refs[]`
  (`invoice_id, amount_minor` in payment currency).
- `fx.csv`: `date, source_currency, target_currency, rate`; its id is `fx_id = "date:SRC:TGT"`.

### Journal grouping (the CSV has no journal_id)
Rows group by `payment_id` if set, else `invoice_id` if set, else exact `timestamp` (manual journals
get unique timestamps). Every group balances. Invoice journal: Dr expense lines / Cr `2100 Accounts
Payable`. Payment journal: Dr AP per ref (tagged with `invoice_id`), Dr `2190 Supplier Advances` for
amount above the refs, Cr `1010 Bank`, residual to `7600 FX Difference`.

### Remittance intent vs recorded allocation
`invoice_refs` is the remitter's intent. The recorded allocation is the AP debit rows tagged with the
payment's `payment_id`. Expected AP relief per ref = `round_half_even(ref_amount × invoice_AP_credit / invoice_total)`.

## 3. Private files (evaluator only)

`truth.json` (`schemas/truth.schema.json`) and `provenance.json` (seed, attempt, config, generator
version, per-fault mutation record with before/after and counterfactual). Python: `TruthIssue`,
`PrivateTruthBundle` in `contracts/schemas.py`.

### Canonical issues

| type | affected_ids (doc ids, set) | expected_amount_minor (base ccy, > 0) | allowed evidence set |
|---|---|---|---|
| `duplicate_invoice` | {original, duplicate} | AP credit of the later-issued copy | {orig, dup, dup AP row} |
| `payment_allocation` | {payment, intended invoice} | expected AP relief − recorded relief | {payment, invoice, misposted row} |
| `fx_rate` | {invoice} | \|AP booked − AP at correct rate\| | {invoice, AP row, fx_id of correct rate} |
| `reporting_period` | {invoice} | AP booked | {invoice, AP row} |

Duplicates repeat the supplier obligation (same entity, currency, total, line items incl. PO/service
month) under a **different** invoice number variant (`-1`, `A`, separator removed). Exceptions that are
not duplicates: an earlier copy cancelled by a matching credit note (credit note + reissue), recurring
monthly services (line description names the month).

## 4. Environment API (`env/env.py`)

```
reset(seed: int, config: dict | None) -> (observation, info{"episode_id"})
step(action) -> (observation, reward: float, terminated: bool, truncated: bool, info)
EnvAction       = {"tool": str, "args": object}
EnvObservation  = {"result": any} | {"error": {"code", "message"}}, plus "steps_remaining"
```

Initial observation: `task, manifest, policy, tables{name:{key, rows}}, actions, steps_remaining`.

| tool | args | result |
|---|---|---|
| `list_records` | `table, cursor?, limit≤50` | `{rows, next_cursor}` (cursor = opaque offset string; stable) |
| `get_record` | `table, id` | row; keys: ledger→row_id, invoices→invoice_id, payments→payment_id, fx→fx_id |
| `get_document` | `doc_id` | invoice or payment; `"manifest"`/`"policy"` also accepted |
| `calculator` | `expression` (≤256 chars) | `{value}`; decimal literals, `+ - * /`, parentheses only |
| `submit` | **the Submission itself** `{episode_id, findings}` | `{accepted: true}`; terminates |

Error codes: `unknown_tool, bad_args, bad_table, not_found, bad_cursor, bad_limit, calc_error,
episode_over`. Every non-submit step counts (including errors). 100 steps max including submit; at the
limit or after 60 s the episode truncates and an empty submission is scored. After the end, actions
return `episode_over` and do not advance.

## 5. Submission (`contracts/submission.py`, `schemas/submission.schema.json`)

```
Submission = {"episode_id": str, "findings": [Finding] (≤30)}
Finding    = {type, affected_ids (1..10), claimed_amount_minor: int, currency, evidence_ids (0..10),
              explanation (≤1000 chars)}
```

Exactly these keys; anything else, a wrong episode_id, a bool/float amount → malformed → reward −1.
Normalisation before matching: type trimmed and lower-cased, currency upper-cased, ids trimmed,
business ids (`invoice_id`, `payment_id`) mapped to `doc_id`, id lists treated as sets, amount by
absolute value, explanation ignored. (The JSON schema's `type` enum is case-sensitive; the Python
validator is authoritative and accepts any case.)

## 6. Scoring (`evaluation/matcher.py`)

TP needs: same type, same affected set, `|claimed − expected| ≤ 1` minor unit, same currency, evidence ⊇
an allowed set. One-to-one maximum matching (Kuhn), deterministic order. Repeats are FP.
`F1 = 2TP/(2TP+FP+FN)`; no truth and no findings → 1; truth empty with findings → 0.
`reward = clip(2·F1 − 1 − 0.002·inspection_steps, −1, 1)`; malformed → −1.
`ScoreReport`: `episode_id, valid, tp, fp, fn, precision, recall, f1, inspection_steps, reward, matched, error`.

## 7. Evaluator process protocol (`evaluation/service.py`)

JSON lines over stdin/stdout of `python -m ledgerforge.evaluation.service <train|eval>`:
`reset → {public}`, `score → {reward, report}` (train) or `{accepted}` (eval), `report → {reports}`.
One scored submission per episode. Truth stays in the evaluator process.

## 8. Python-side shapes

| Contract | Where | Form |
|---|---|---|
| ScenarioConfig | `contracts/schemas.py` | frozen dataclass, `from_dict` rejects unknown keys, `validate()` |
| FinancialWorld | `sim/world.py::World` | internal, mutable during generation, never exported |
| FaultResult | `sim/faults.py` | dict `{type, affected_ids, expected_amount_minor, currency, allowed_evidence_sets, provenance}` |
| EvidenceCertificate | `verification/auditor.py::AuditResult` | auditor issue `{type, affected_ids, amount_minor, currency, evidence_ids}` derived from public data only |
| PublicEpisode / PrivateTruthBundle / TruthIssue | `contracts/schemas.py` | frozen dataclasses |
| ScoreReport | `evaluation/matcher.py` | frozen dataclass |
| AgentPolicy | `contracts/schemas.py` | Protocol: `name`, `reset(obs)`, `act(obs) -> EnvAction` |

## 9. Determinism

Each generation phase uses `random.Random(f"ledgerforge:{seed}:{attempt}:{phase}")` (string seeds are
SHA-512 hashed by CPython, independent of `PYTHONHASHSEED`). Acceptance-gate failures retry with
`attempt+1` (≤20). `episode_id` comes from the RNG and does not contain the seed. Same seed + config →
byte-identical public and private data (tested across processes). Config `order_salt` reshuffles
public table order; `id_salt` renames every public id (doc, invoice, payment, row, entity, episode)
with a salted digit derangement — shape-preserving, bijective, fx ids unchanged; truth is renamed
identically and the renamed episode re-passes the gate (`sim/salt.py`, `tests/test_metamorphic.py`).
Provenance mutation records keep the unsalted ids.

Size gate: an episode ships only with 200–2000 ledger rows and 20–200 documents; `n_invoices` ≤ 100.
