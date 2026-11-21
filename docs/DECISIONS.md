# Architecture decision records

Format: context → decision → consequence. Newest last. Scoring-contract changes require a new ADR.

## ADR-001 Standard-library-only runtime
Context: 2 CPU / 4 GB / offline grading; every dependency is attack and licence surface.
Decision: runtime `dependencies = []`. Dev only: pytest, ruff, jsonschema (all MIT). No Pydantic,
Faker, NetworkX, pandas. Matching uses a 20-line Kuhn algorithm; vocabulary is curated in `sim/profiles.py`.
Consequence: validation is hand-written (`contracts/submission.py`) and must be tested exhaustively.

## ADR-002 Ledger in functional currency
Decision: all ledger rows are in `base_currency`; native amounts live on documents; FX differences on
settlement go to `7600 FX Difference`.
Consequence: FX error amounts are unambiguous base-currency ledger impacts.

## ADR-003 Journal grouping without journal_id
Decision: group key = payment_id → invoice_id → exact timestamp. Manual journals get unique timestamps.
Consequence: the official CSV shape is preserved; balance is checkable by anyone.

## ADR-004 Canonical ids are doc ids
Decision: `affected_ids` are document ids (sets); business ids are accepted and normalised by the
matcher. Evidence may be doc ids, ledger row ids or fx ids `date:SRC:TGT`.

## ADR-005 All expected amounts in base currency
Decision: expected amount = ledger impact in base currency (see CONTRACTS §3); tolerance 1 minor unit,
compared by absolute value.

## ADR-006 One allowed evidence set per issue (for now)
Decision: each truth issue carries exactly one minimal evidence set; extra evidence ids are harmless.
Consequence: simple and strict. Revisit if baseline analysis shows legitimate alternative proofs.

## ADR-007 Duplicates use a variant invoice number
Decision: the duplicate never reuses the exact invoice_id (keeps `get_record(invoices, id)` unique);
it reuses supplier, currency, total and line items. Credit-note+reissue and recurring services are
legitimate look-alikes.

## ADR-008 Fault preconditions prevent cascades
Decision: F1/F3/F4 targets are unpaid at injection time (F1 interaction A excepted by design), F2 only
on payments without a legitimate remainder (any currency since ADR-015); foreign payments settle one invoice fully.
Consequence: every injected fault yields exactly the declared issues; enforced again by ADR-009.

## ADR-009 Independent auditor as acceptance gate
Decision: `verification/auditor.py` recomputes all issues from public data and published rules only;
an episode is accepted only if auditor issues == truth (type, ids, amount, currency), there are no
invariant violations, and each allowed evidence set resolves and is derivable by the auditor.
Consequence: no unprovable or unlabelled issue can ship. Auditor and generator share only
`contracts/money.py` (the published semantics) — a bug there would affect both; mitigated by unit
tests on money/FX and hand-made mutation tests.

## ADR-010 Evaluator in a separate OS process
Decision: the environment spawns `python -m ledgerforge.evaluation.service`; generation and truth live
there; the agent side receives public data and a reward (train) or an ack (eval).
Consequence: truth is never in the agent's memory; the oracle runs on the trusted runner side by
regenerating the same seed.

## ADR-011 Submit args are the submission payload
Context: spec §10.2 `submit(findings)` + §10.4 payload `{episode_id, findings}`.
Decision: `{"tool": "submit", "args": {"episode_id", "findings"}}`. Anything else → −1.

## ADR-012 Ownership split and the Claude-built slice
Context: brief assigns env/evaluator/baselines/benchmark to Codex, but Phase 4 needs a working slice
before contracts can be judged.
Decision: Claude wrote minimal `env/`, `evaluation/`, `agents/oracle.py`, `benchmark/trajectory.py`
for the slice. Codex takes ownership of these files from TASKS.md on, hardens them and adds
baselines/benchmark. Claude keeps `contracts/`, `sim/`, `verification/`.

## ADR-013 Truncation scoring
Decision: truncated episodes score an empty submission with inspection_steps = all steps taken.
On a clean episode that gives `1 − 0.002·100 = 0.8`; on a faulted one −1 (clipped).

## ADR-014 id_salt is a digit derangement; size gate
Context: paired ID transforms must be equivalent problems; a hash rename would erase duplicate-variant
cues (`-1`, `A`) and make the salted twin harder. `n_invoices=150` produced 243 documents (> 200).
Decision: rename every public id by a salted digit derangement (bijective, shape-preserving, every id
changes); re-run the gate on the renamed episode. Cap `n_invoices` at 100 (worst measured 176 docs) and
reject any episode outside 200–2000 ledger rows / 20–200 documents in the gate.
Consequence: renamed ids may coincide with ids of the *other* episode of a pair (harmless). Ledger size
stays ≈250–600 rows, inside the supported range but not near 2000 (superseded by ADR-016).

## ADR-015 Allocation faults on any payment currency (generator 0.2.0)
Context: ADR-008 limited F2 to base-currency payments, and the fault drew its moved amount from the
remittance (payment currency) while editing a base-currency AP row. That was a latent units bug,
masked only by the base-currency restriction. The rule-based reconciler reached F1 1.0 partly
because it skips foreign payments.
Decision: F2 may target any fully allocated payment. The moved amount is drawn from the
base-currency AP relief row, and a misapplied target must share the payment's currency. The auditor
was already currency-generic, so the contract and the issue amounts (base currency) are unchanged.
Generator version 0.2.0; open episodes and benchmark outputs were regenerated.
Consequence: about 27% of allocation faults are now on foreign payments. The reconciler misses those
(3 false negatives on train + mirror, F1 0.98) and still has no false positives.

## ADR-016 Ledger size scales with difficulty (generator 0.3.0)
Context: ADR-014 left ledgers at ≈250–600 rows, far from the 2000-row upper bound the spec supports.
Decision: invoices carry up to 3 / 4 / 5 / 6 line items (basic → expert, `profiles.MAX_LINE_ITEMS`)
and bank-fee filler tops the ledger up to 200 / 400 / 800 / 1600 rows (`profiles.TARGET_LEDGER_ROWS`,
plus up to 40). Measured over the open episodes: 226–1638 rows; documents still ≤ 200.
Consequence: larger ledgers cost list steps (reconciler ≈22–25 inspection steps instead of ≈16) but
add no new look-alikes, so they do not make labels harder to derive. The reconciler's foreign-payment
shortcut was removed in the same change (Codex-owned file, one-line deletion, recorded in
INTEGRATION.md); it again scores F1 1.0, with 0 FP.

## ADR-017 Rule ablation instead of more look-alikes
Context: CL-09 planned extra hard negatives, but the generator already emits recurring services,
credit note + reissue, instalments, split remittances, advances, timezone-boundary invoices and
early next-period invoices. A policy that encodes every published rule will always reach F1 1.0;
that is what the acceptance gate promises. The useful question is whether a policy that *skips* a
rule is punished.
Decision: `ReconcilerPolicy(naive={...})` swaps a published rule for a common shallow heuristic
(duplicates by supplier + total, period by printed date, FX at the period-end rate, allocation at the
payment-date rate). `benchmark/ablation.py` measures each swap on train + dev + mirror and writes
`outputs/reports/ablation.md`. Default behaviour is unchanged.
Consequence: measured on 40 episodes, every shortcut costs F1 (0.42 → 0.08) and all four together
give F1 0.045 / reward −0.94. The look-alikes are load-bearing. CL-09 closed without new generators.
The Docker image installs only the `test` dependency group (pytest, jsonschema); ruff stays in `dev`.
