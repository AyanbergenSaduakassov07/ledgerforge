# LedgerForge — design note

**Problem.** An audit agent can't be trained or measured without books whose errors are known
*and provable*. Labels that a hand-written generator merely asserts can be wrong, and reward on wrong
labels teaches the wrong thing. LedgerForge produces fictional books in which every labelled error is
re-derived by an independent auditor before the episode ships.

**Causal generation.** `sim/world.py` simulates business events (purchase orders, invoices, payments,
FX settlements) and posts balanced double-entry journals. `sim/faults.py` then mutates the *causal
record*, for example by booking an invoice at the wrong FX date or allocating a payment to the wrong
invoice. It lets the ledger consequences follow, rather than editing ledger rows directly. Each fault
records its before/after values and counterfactual in `provenance.json`. Two interactions are
designed in: a duplicate invoice that a payment then settles, and an FX error inside a misallocated
payment.

**Acceptance gate (ADR-009).** `verification/auditor.py` reads only the public files and published
rules (CONTRACTS §1–3) and recomputes every issue. An episode is released only when:
- the audit result equals the truth (type, ids, amount, currency);
- every journal balances;
- each allowed evidence set resolves and can be derived from public data;
- the episode's size is inside the official range.

A failed check retries with a new deterministic attempt (≤20). This makes "unprovable label" a
generation failure, not a scoring risk.

**Isolation (ADR-010).** Truth lives in a separate evaluator process that speaks JSON lines. The
environment process holds only public data, and eval mode returns no reward until the run report.
Baselines may import only `contracts/`; a test enforces this in a fresh interpreter.

**Reward.** `clip(2·F1 − 1 − 0.002·steps, −1, 1)` with one-to-one matching. A true positive needs:
- the right type;
- the exact affected-id set;
- an amount within one minor unit;
- the right currency;
- a complete evidence set.

Flag-everything scores negative, silence on flawed books scores −1, and malformed output scores −1.

**Robustness checks.**
- Metamorphic pairs: `id_salt` renames every id by a digit derangement and `order_salt` permutes
  tables, both without changing the problem. Oracle reward is identical across each pair.
- Reproducibility: the same seed yields byte-identical episodes across processes.
- Committed open episodes regenerate byte-identically from `episodes/splits.json`.

**Deliberate limits.**
- One minimal evidence set per issue (ADR-006).
- Ledger size scales with difficulty up to ≈1640 rows; the bulk at higher levels is routine bank-fee journals (ADR-016).
- Agent and evaluator run as the same OS user, so isolation is a process boundary, not a sandbox.
- A rule-based reconciler that encodes the published rules saturates the benchmark (F1 1.0).
- The runtime uses the standard library only (ADR-001).
