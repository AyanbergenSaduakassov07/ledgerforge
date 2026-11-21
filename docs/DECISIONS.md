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
on base-currency payments without a legitimate remainder; foreign payments settle one invoice fully.
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
stays ≈250–600 rows, inside the supported range but not near 2000.
