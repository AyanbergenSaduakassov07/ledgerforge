> Copied verbatim from the team's Master Spec v2.0. Precedence: official brief
> (`docs/official_case_ru.pdf`) > this spec > research report > library docs.
> Where this spec and the brief differ, the brief wins; deviations are logged in
> `docs/DECISIONS.md`.

# LEDGERFORGE
## Master Product Requirements & Engineering Architecture
**Version:** 2.0 — Hackathon Implementation Specification  
**Project:** REC Genesis Hackathon 2026 — FinTech Track  
**Challenge:** RL Environments for Financial Audit Model Training  
**Online submission deadline:** 22 November 2026, 23:59 (Astana, UTC+5)  
**Team:** 2 human developers using Claude Code and OpenAI Codex  
**Status:** Architecture approved; implementation and contract freeze pending

---

# 1. EXECUTIVE SUMMARY

LedgerForge is a deterministic, evidence-driven financial simulation and reinforcement-learning evaluation platform.

Its primary purpose is to create realistic fictional companies, generate internally consistent financial records, introduce controlled accounting discrepancies, expose a restricted investigation environment to AI agents, and independently evaluate their findings against hidden ground truth.

LedgerForge is **not** a conventional accounting application, payment processor, financial chatbot, fraud classifier, or automated audit report generator.

It is the environment in which financial-auditing agents can be trained, tested, compared and evaluated.

The system must support the complete lifecycle:

1. Generate a coherent fictional financial world.
2. Generate invoices, payments, journal entries, FX rates and accounting policies.
3. Apply controlled, causally documented financial faults.
4. Verify that every injected issue can be independently proved from public evidence.
5. Publish only approved observations to an agent.
6. Allow the agent to investigate using five restricted actions.
7. Accept structured findings with affected record IDs, financial amounts and supporting evidence.
8. Match findings against evaluator-private ground truth.
9. Calculate the exact competition reward.
10. Record trajectories and benchmark policies.
11. Reproduce the episode and verify invariance under valid ID/order transformations.

LedgerForge's differentiator is its **causal, proof-backed financial simulation**.

A generated anomaly is not accepted simply because its generator labels it as an anomaly. It must be independently discoverable, quantitatively correct and attributable to a documented change in a valid financial history.

## Product positioning

**Name:** LedgerForge  
**Descriptor:** Causal Financial Audit RL Environment  
**Tagline:** Generate financial worlds. Investigate anomalies. Verify every claim.

**Pitch statement:**

"LedgerForge generates reproducible, industry-realistic financial investigations with causally injected accounting errors and independently verifiable evidence. AI auditors investigate these worlds through restricted tools and receive rigorous, attack-resistant evaluation rather than subjective feedback."

---

# 2. SOURCE-OF-TRUTH PRIORITY

Implementation decisions must follow this order:

1. **Official hackathon PDF** — authoritative requirements, schemas, scoring and submission constraints.
2. **This master specification** — selected architecture and implementation decisions.
3. **Financial audit research report** — scenario realism, accounting references and industry context.
4. **Upstream dependency documentation** — actual library APIs, supported versions and licenses.
5. **Agent recommendations** — non-binding implementation proposals.

If a recommendation conflicts with the hackathon PDF, the PDF wins.

Do not silently replace official requirements with ideas from the research report.

Examples of prohibited substitutions:

- Do not replace the five official environment actions with a richer custom action space.
- Do not replace the required F1-based reward with a weighted fraud-scoring formula.
- Do not require model fine-tuning, network access, paid APIs or GPUs for official evaluation.
- Do not rely on an additional financial document type unless it is accessible through the declared public interface.
- Do not require an elaborate audit memo instead of the prescribed findings structure.

All deviations or interpretations must be documented in `docs/DECISIONS.md`.

---

# 3. HACKATHON TASK AND SUCCESS CRITERIA

## 3.1 Official challenge

Build a reproducible RL environment for financial audit models, including synthetic company documents, restricted investigation tools, hidden financial errors, recorded trajectories and a correct reward function.

Training model weights is optional.

The judged deliverable is the environment and evaluator, not the performance of an agent built by the team.

## 3.2 Scoring rubric

| Category | Points | Main objective |
|---|---:|---|
| Contract and isolation | 25 | Correct reset/step, schemas, limits, invalid actions, termination and no truth leakage |
| Data and ground truth | 25 | Valid accounting, controlled discrepancies and independently sufficient evidence |
| Reward robustness | 25 | Exact matching, correct F1, attack resistance and proper false-positive handling |
| Reproducibility/generalization | 15 | Deterministic replay, ID-renaming and record-order invariance |
| Engineering/explanation | 10 | One-command verification, versioning, trajectories, measured failures and limitations |
| **Total** | **100** | |

**Primary objective:** Maximize correctness across the full 100-point rubric.

**Secondary objective:** Differentiate through causal modeling, industry realism, evidence proofs and an optional AI-assisted demo.

Do not sacrifice correctness for presentation features.

## 3.3 Required episode characteristics

An episode represents one fictional company and one reporting period.

Supported range:

- 200–2,000 ledger rows.
- 20–200 documents.
- 0–12 financial errors.
- Four independently configurable mandatory error types.
- Two interacting-error scenarios.
- Completely clean companies.
- Legitimate hard negatives and distractors.

Generated data must vary identifiers, entity names, amounts, currencies, order, dates, timezones and error combinations.

Difficulty should require investigation, not arbitrary confusion or missing information.

## 3.4 Runtime targets

Design the official verification environment for the suggested autonomous evaluation limits:

- Python 3.11.
- Two CPU cores.
- 4 GB RAM.
- No GPU.
- No network.
- Approximately 1 GB solution footprint.
- 60 seconds per episode.
- Maximum 100 agent steps.

These are the brief's proposed resource limits; implementation should aim to meet them conservatively.

---

# 4. SYSTEM ARCHITECTURE

Use a **Python modular monolith** with explicit interfaces and separate agent/evaluator execution boundaries.

The conceptual architecture is:

    Scenario Configuration
              |
              v
    Canonical Financial World
              |
              v
    Financial Event / Evidence Graph
              |
              v
    Fault Injection & Composition
              |
              v
    Independent Acceptance Gate
              |
         +----+----+
         |         |
         v         v
    Public Data   Private Ground Truth
         |         |
         v         v
    RL Environment  Independent Evaluator
         |         ^
         v         |
    Agent Policies |
         |         |
         +----+----+
              |
              v
    Trajectories / Benchmarks / Reports
              |
              v
    Optional Visualization & Cloud AI Gateway

There are three major systems.

## System A — Financial Simulation

Owns:

- Canonical financial event graph.
- Accounting policy engine.
- Money and FX calculation.
- Scenario and industry configuration.
- Fault operators and composition.
- Ground truth and provenance.
- Evidence construction.
- Public/private export.
- Independent generation acceptance.

## System B — RL and Evaluation

Owns:

- `reset` and `step`.
- Five permitted agent actions.
- Observation restrictions.
- Agent budgets.
- Episode lifecycle.
- Private evaluator process.
- Finding normalization and matching.
- Exact terminal reward.
- Baseline policy adapters.
- Trajectory recording and benchmarks.
- Adversarial and metamorphic testing.

## System C — Optional AI and Presentation

Owns:

- Deterministic semantic audit compiler.
- Privacy-aware cloud LLM adapter.
- Restricted investigation planner.
- Evidence-processing helpers.
- Interactive benchmark and investigation UI.
- Post-evaluation causal graph visualization.

Systems A and B must run completely without System C.

---

# 5. FINANCIAL DOMAIN MODEL

## 5.1 Three distinct representations

LedgerForge must distinguish:

**Canonical business reality:** The actual fictional economic events.

**Recorded accounting reality:** What has been entered into invoices, payment allocations, journal records and accounting periods.

**Evaluator-private discrepancy truth:** The verifiable difference between correct treatment and recorded treatment.

This separation is required for meaningful fault injection and evidence generation.

A ledger row is not automatically authoritative merely because it exists.

## 5.2 Internal graph nodes

Implement typed Python dataclasses with indexed dictionaries and optional NetworkX projections.

Core entities:

- `Company`
- `ReportingPeriod`
- `Counterparty`
- `Contract`
- `PurchaseOrder`
- `AcceptanceEvent`
- `Invoice`
- `InvoiceLine`
- `BankMovement`
- `PaymentAllocation`
- `JournalEntry`
- `JournalLine`
- `FXRate`
- `AccountingPolicy`
- `SupportingDocument`
- `BusinessEvent`

Internal relationships include:

- `ISSUED_BY`
- `RELATES_TO_CONTRACT`
- `REFERENCES_PO`
- `SUPPORTED_BY_ACCEPTANCE`
- `SETTLES_INVOICE`
- `ALLOCATED_TO`
- `POSTED_AS`
- `VALUED_WITH_RATE`
- `BELONGS_TO_PERIOD`
- `SUPPORTED_BY_DOCUMENT`

The graph is an internal private model.

Do not expose the complete graph or its private causal metadata to the agent.

Do not add Neo4j or another graph database.

## 5.3 Money representation

Rules:

- Amounts use integer minor units.
- Each currency has a defined exponent.
- FX rates are decimal strings.
- Calculations use Python `Decimal`.
- Never compare native amounts from different currencies directly.
- Define rounding mode explicitly.
- Define FX rate direction explicitly: target-currency units per one source-currency unit.
- Preserve native transaction currency and functional/base-currency valuation separately.
- All timestamps are ISO-8601 with offsets.
- Reporting-period interpretation uses the episode timezone.

Use the standard library where possible.

## 5.4 Accounting invariants

At minimum:

1. Valid journal groups must balance under the defined currency and functional-currency rules.
2. Every record reference resolves or is explicitly null.
3. Invoice outstanding balances reconcile to allocations and approved adjustments.
4. Bank movement amounts reconcile to their supported settlements or explicitly permitted unapplied balances.
5. Duplicate invoice errors correspond to unsupported repeated obligations, not simply matching amounts.
6. FX conversions obey declared policy, selected date and rounding.
7. Recognition dates and posted periods agree with declared accounting rules except for injected faults.
8. Credit notes, refunds, recurring charges and legitimate split payments can be generated without becoming false anomalies.
9. All generated records satisfy the public schema.
10. Every labelled issue has sufficient publicly accessible evidence.

A balanced journal can still contain an accounting error. Do not classify all deviations using debit-credit imbalance alone.

---

# 6. INDUSTRY DESIGN

Use **one accounting engine with multiple industry scenario profiles**.

## Flagship industry: Industrial procurement, infrastructure and energy suppliers

Primary region: fictional companies operating in Kazakhstan or Central Asia.

Realistic processes:

- Supplier contracting.
- Purchase orders.
- Equipment procurement.
- Subcontractor invoices.
- Bank and treasury payments.
- Partial allocations.
- Imported equipment invoiced in USD/EUR.
- KZT functional-currency reporting.
- Delivery and milestone acceptance.
- Month-end and year-end closing.

## Additional industry profiles

**Construction:** milestone billing, subcontractors, project services, acceptance certificates and period-end expenses.

**Manufacturing:** imported materials, goods receipts, supplier settlements and foreign-currency obligations.

**Retail/services:** recurring invoices, instalments, refunds, split payments and legitimate near-duplicates.

Industry-specific fields should be generated only where they support evidence or realism. They must not create unnecessary mandatory error types.

The industry profile changes transaction patterns and document descriptions; it does not rewrite the core accounting semantics.

All entities and transactions are synthetic.

No real KMG, KazTransOil, Samruk-Kazyna, government or private-company financial data may be used.

---

# 7. FAULT-INJECTION ENGINE

Implement four mandatory independent causal operators.

Each operator must:

1. Select a valid business event.
2. Verify preconditions.
3. Apply a controlled accounting mutation.
4. Record before/after state.
5. Generate exact discrepancy truth.
6. Identify public evidence requirements.
7. Verify the resulting issue independently.
8. Reject the candidate if the mutation is unprovable or creates unintended issues.

## F1 — Duplicate invoice

Generate an unsupported second accounting obligation corresponding to one underlying genuine supplier transaction.

Valid evidence may include:

- Two invoice records.
- Same counterparty and underlying commercial obligation.
- Supporting PO/acceptance relationship.
- Related journal postings.

Do not automatically label repeated amounts, monthly invoices or legitimate reissues as errors.

Distinguish duplicate invoice recording from duplicate bank payment.

## F2 — Missing/partial payment allocation

Generate a real payment whose posted allocation is missing, partial or incorrectly assigned relative to the supported remittance.

Valid evidence may include:

- Payment record.
- Invoice and remittance reference.
- Accounting allocation.
- Ledger postings.
- Policy treatment for unapplied amounts.

A legitimate instalment is not an error.

## F3 — Incorrect FX rate/date

Record a transaction using a rate inconsistent with the policy-defined recognition date or selected FX rate.

Evidence:

- Native-currency invoice/payment.
- Recognition-date evidence.
- Applicable policy.
- FX table.
- Actual functional-currency posting.

Specify whether the claimed discrepancy is in native or functional currency; the default for an FX valuation discrepancy should be the base-currency difference.

## F4 — Incorrect reporting period

Record a valid economic event in a period inconsistent with the declared recognition and cutoff rules.

Evidence:

- Economic-event or acceptance date.
- Accounting policy.
- Invoice/service information.
- Actual ledger timestamp.
- Correct reporting period.

Late payment alone does not prove an accounting cutoff error.

## Two mandatory interacting scenarios

### Interaction A: Duplicate invoice + incorrect payment allocation

A genuine obligation is recorded twice and a payment is partially or incorrectly allocated.

There must be two independently substantiated findings.

### Interaction B: Incorrect FX recognition date + reporting-period cutoff

An economic event belongs to one period but is posted in another using a rate selected from an incorrect date.

The FX and cutoff errors must remain independently provable even though they affect related accounting events.

## Four-world composition testing

For each interacting pair, validate:

- Clean world.
- Fault A only.
- Fault B only.
- Both faults together.

Confirm exact declared truth, evidence availability and no hidden accidental third anomaly.

## Ground-truth convention

Each truth issue must define:

- `issue_id`
- `type`
- `affected_ids`
- `expected_amount_minor`
- `currency`
- `allowed_evidence_sets`

Provenance separately describes the mutation, cause, original event and counterfactual correction.

Use one documented canonical affected-ID convention per error type.

For example, duplicate invoice findings should use the two unique document IDs or record IDs chosen by the contract, not an ambiguous reused supplier invoice number.

Finalize these ID choices before implementing injectors and matching.

---

# 8. EPISODE GENERATION

## 8.1 Configuration

Support:

- Schema/config version.
- Seed.
- Industry profile.
- Company base currency.
- Reporting period and timezone.
- Number of ledger entries and documents.
- Error counts by type.
- Interacting-error count.
- Difficulty level.
- FX/date and rounding rules.
- Distractor configuration.

Use independently derived random streams for generation phases where useful.

A candidate rejected during generation must be retried through a deterministic attempt sequence.

## 8.2 Difficulty profiles

**Basic:** Simple independent issue with straightforward evidence.

**Intermediate:** Several independent errors, legitimate distractors and partial payments.

**Advanced:** Interacting faults, cross-currency accounting and period boundaries.

**Expert:** More complex relationships, multiple entities and harder evidence selection.

All difficulty profiles must remain solvable under the specified tool and time budgets.

Do not encode fault types through obvious ID suffixes, special timestamps or record positions.

## 8.3 Public file contracts

Produce the official files exactly as required:

**manifest.json**
- `schema_version`
- `episode_id`
- `base_currency`
- `period_start`
- `period_end`
- `timezone`
- record and document counts
- rounding rules

**ledger.csv**
- `row_id`
- `timestamp`
- `account`
- `debit_minor`
- `credit_minor`
- `currency`
- `entity_id`
- `invoice_id`
- `payment_id`

**invoices.jsonl**
- `doc_id`
- `invoice_id`
- `entity_id`
- `issued_at`
- `due_at`
- `currency`
- `total_minor`
- `line_items`

**payments.jsonl**
- `doc_id`
- `payment_id`
- `timestamp`
- `currency`
- `amount_minor`
- `invoice_refs`

**fx.csv**
- `date`
- `source_currency`
- `target_currency`
- `rate`

**policy.json**
- FX-rate date selection.
- Reporting-period boundaries.
- Currency rounding.
- Other explicitly declared permitted treatments needed for the synthetic scenarios.

Use null for missing references.

Additional metadata or supporting documents must not make the official schema invalid. Where schema extensions are necessary, define and version them explicitly.

## 8.4 Private files

**truth.json**
- issue IDs/types
- affected IDs
- claimed discrepancy amounts and currencies
- allowed evidence sets

**provenance.json**
- canonical source event
- causal mutation
- before/after record states
- internal verification details
- counterfactual correction

The agent never sees private truth or provenance, their file paths, seeds or scorer diagnostics.

---

# 9. INDEPENDENT EVIDENCE VERIFICATION

The generator must not validate its own truth simply by reading its recorded mutation metadata.

Use an independent validator that reconstructs discrepancies from public records and public policies.

For each issue, validate:

- Relevant public records exist.
- Evidence IDs resolve through permitted tools.
- The financial computation is independently reproducible.
- The amount and currency are correct.
- The declared error type matches the facts.
- At least one complete allowed evidence set proves the issue.
- No unintended unlabelled error is present.

A candidate failing any requirement is rejected and regenerated.

## Counterfactual corrections

Maintain a private pre-mutation accounting state.

For each issue, calculate the correction required to restore the valid state.

For interacting faults, compare individual and combined corrections so aggregate effects are not counted twice.

Counterfactual correction quality is an internal diagnostic. It must not replace the official reward function.

## Evidence reachability

A valid proof must be discoverable through the actual public agent interface.

Do not create evidence certificates relying on inaccessible contracts, internal object pointers or hidden graph nodes.

Test that a bounded reference investigation can retrieve the necessary public evidence within 100 actions.

---

# 10. OFFICIAL RL ENVIRONMENT

## 10.1 Required methods

    reset(seed, config) -> (observation, info)

    step(action) -> (
        observation,
        reward,
        terminated,
        truncated,
        info
    )

This is a JSON-compatible Gymnasium-style contract.

Subclassing the Gymnasium library is optional.

## 10.2 Official actions

Exactly five actions are available:

1. `list_records(table, cursor, limit)`
2. `get_record(table, id)`
3. `get_document(doc_id)`
4. `calculator(expression)`
5. `submit(findings)`

Do not expose extra agent tools such as SQL execution, arbitrary graph traversal, shell access or filesystem search.

Internal helpers may exist, but any agent's case-specific data access must pass through the official interface.

## 10.3 Constraints

- Maximum 100 steps, including submission.
- Maximum 50 rows per list page.
- Stable pagination.
- Unknown IDs and invalid actions consume a step and return bounded errors.
- Calculator allows arithmetic and decimal literals only.
- No code execution through calculator.
- No free-form SQL, shell, files or network access.
- Submitting terminates the episode.
- Step/time exhaustion truncates the episode with an empty final submission.
- Subsequent actions after termination/truncation cannot advance the episode.

The initial observation contains the task, manifest, a concise policy summary and remaining budget.

Observations never contain hidden truth, provenance or fault-generation hints.

## 10.4 Submission schema

The submission payload is:

    {
      "episode_id": "...",
      "findings": [
        {
          "type": "...",
          "affected_ids": ["..."],
          "claimed_amount_minor": 0,
          "currency": "...",
          "evidence_ids": ["..."],
          "explanation": "..."
        }
      ]
    }

Constraints:

- Maximum 30 findings.
- Maximum 10 evidence IDs per finding.
- Maximum 1,000 characters of explanation per finding.
- Wrong structure terminates the episode with reward -1 and a private evaluator diagnostic.

The explanation is concise evidence-based justification, not hidden model reasoning.

## 10.5 Isolation

The agent runs in a process without access to private truth files or evaluation internals.

A process boundary or equivalent enforceable filesystem boundary is required for adversarial testing.

A mere Python naming convention such as `_private` is not an isolation mechanism.

No private file should be mounted into an untrusted agent process.

---

# 11. MATCHER AND REWARD ENGINE

Implement the official scoring logic without modification.

## 11.1 True-positive requirements

A submitted finding can match a truth issue only if all conditions pass:

1. Correct error type.
2. Correct canonical affected IDs.
3. Correct currency.
4. Claimed discrepancy amount within the publicly defined tolerance.
5. At least one complete acceptable evidence set.

Use deterministic one-to-one matching.

Candidate matching edges should be computed independently of submission order.

Use maximum-cardinality bipartite matching, with deterministic tie-breaking for ambiguous assignments.

Unmatched or repeated submitted findings are false positives.

Unmatched truth issues are false negatives.

## 11.2 Metrics

    Precision = TP / (TP + FP)
    Recall    = TP / (TP + FN)
    F1        = 2TP / (2TP + FP + FN)

At zero denominators, precision or recall is zero.

Special cases:

- Empty truth + empty findings => F1 = 1.
- Empty truth + nonempty findings => F1 = 0.
- Nonempty truth + empty findings => F1 = 0.

## 11.3 Official terminal reward

    reward = clip(
        2 * F1 - 1 - 0.002 * inspection_steps,
        -1,
        1
    )

Define inspection steps consistently with the official action sequence and publish this interpretation.

Exploratory actions return zero intermediate reward.

In open training, terminal reward follows the required contract.

During closed testing, the evaluator retains actual scoring and diagnostics until the run ends. No intermediate correctness feedback may leak to the agent.

## 11.4 Mandatory adversarial tests

- Perfect evidence-backed findings beat silence on flawed books.
- Silence beats false accusations on clean books.
- Repeated findings do not increase reward.
- Flagging every record/type receives a poor score.
- Invalid evidence never earns a true positive.
- Wrong IDs never earn a true positive.
- Wrong currency never earns a true positive.
- Wrong amount outside tolerance never earns a true positive.
- Malformed submission returns -1.
- Cost of inspection has a relatively small effect between otherwise equal results.
- Agent cannot submit twice to improve its result.
- Reward result is invariant under submission ordering where the set of findings is equivalent.

Do not reward persuasive explanations without factual correctness.

---

# 12. BASELINE AGENTS AND BENCHMARK

Implement four mandatory policies:

**Random Explorer:** Fixed-seed random investigation.

**Simple Reconciler:** Uses visible invoice, payment, ledger and policy evidence to detect straightforward discrepancies.

**Flag-All Attacker:** Mass-submits suspected errors to test false-positive resistance.

**Evaluator-only Oracle:** Privileged reference adapter with correct findings and evidence. It must be confined to evaluator-side testing.

The oracle is not evidence that a normal agent can audit successfully.

## Benchmark data

Produce:

- 10 open training episodes.
- 10 open development episodes.
- Four policy adapters.
- Recorded trajectories.
- A separate reproducibility/robustness benchmark.
- Failure-analysis report.

Mirror the official closed evaluation with an additional local suite containing 20 episodes, including at least five clean and five interacting-error episodes, and 20 paired ID/order transformations.

## Trajectories

Create `trajectories.jsonl` with:

- `episode_id`
- `step`
- `action`
- `observation`
- `reward`
- `terminated`
- `truncated`

No private truth in observations.

## Reported diagnostics

For each policy, report:

- Precision.
- Recall.
- F1.
- Terminal reward/return.
- Inspection steps.
- Runtime.
- Failure categories.

Report measured results only. Do not hardcode PASS statuses or synthetic performance claims.

---

# 13. OPEN-SOURCE STRATEGY AND DEPENDENCIES

Use mature open-source components for infrastructure.

Keep causal finance logic, evidence certificates, official action enforcement, evaluator matching predicates and reward policy under LedgerForge control.

## 13.1 Required or strongly preferred runtime components

| Component | Repository | License | Purpose |
|---|---|---|---|
| Pydantic | https://github.com/pydantic/pydantic | MIT | Schemas, structured contracts and validation |
| Faker | https://github.com/joke2k/faker | MIT | Seeded fictional company and entity data |
| NetworkX | https://github.com/networkx/networkx | BSD-3-Clause | Graph relationships and bipartite matching |
| RapidFuzz | https://github.com/rapidfuzz/RapidFuzz | MIT | Candidate duplicate matching and hard-negative generation |
| Python standard library | Python 3.11 | PSF | Decimal, CSV/JSON, random, subprocesses, datetime, arithmetic parsing |

A dependency should only be included if its functionality is actively used.

Do not introduce a graph database or external SQL service.

## 13.2 Test and engineering dependencies

| Component | Repository | Role |
|---|---|---|
| pytest | https://github.com/pytest-dev/pytest | Unit/integration tests |
| Hypothesis | https://github.com/HypothesisWorks/hypothesis | Property-based and metamorphic tests; MPL-2.0 |
| Syrupy | https://github.com/syrupy-project/syrupy | Deterministic snapshot tests |
| pytest-cov | https://github.com/pytest-dev/pytest-cov | Coverage measurement |
| jsonschema | https://github.com/python-jsonschema/jsonschema | JSON Schema verification |
| uv | https://github.com/astral-sh/uv | Dependency management and lockfile |
| Ruff | https://github.com/astral-sh/ruff | Linting and formatting |
| Gitleaks | https://github.com/gitleaks/gitleaks | Development-time secret scanning |
| Bandit | https://github.com/PyCQA/bandit | Development-time security checks |

Dev tools must not become dependencies of the official runtime unless needed.

Resolve compatible package versions and lock them rather than guessing version numbers.

## 13.3 Accounting reference repositories

**R3n0va Synthetic Accounting Data Generator**  
https://github.com/R3n0va/synthetic-accounting-data-generator  
License: MIT.

Primary architectural reference for configuration-driven generation, seeded datasets, account relations, manifest exports and validation.

Review before reusing code. Its German accounting scenario logic is not directly portable to the official benchmark.

**python-accounting**  
https://github.com/ekmungai/python-accounting  
License: MIT.

Reference for accounting entries, account models and double-entry semantics. Avoid depending on its full SQLAlchemy/database infrastructure by default.

**RegLedger**  
https://github.com/TEHILLA-O/regledger  
License: MIT.

Reference for payment reconciliation, synthetic payments, exceptions and review workflows. Do not adopt its complete PostgreSQL/dbt/Airflow stack.

**Inspect AI**  
https://github.com/UKGovernmentBEIS/inspect_ai  
License: MIT.

Reference for model evaluation and trace/report design. Do not replace the official RL contract with its framework.

These are **reference candidates**, not automatically imported dependencies.

If implementation code is copied, the agent must record the exact repository, commit, file, license and modifications in `THIRD_PARTY_NOTICES.md`.

Do not assume a repository is mature because its README is impressive. Verify selected modules with targeted tests.

## 13.4 Optional cloud LLM stack

**Pydantic AI**  
https://github.com/pydantic/pydantic-ai  
MIT.

Preferred optional typed-model adapter.

Use provider-compatible structured outputs where available.

Do not require a model provider for any official test, benchmark, generation or verification command.

**Presidio**  
https://github.com/data-privacy-stack/presidio  
MIT.

Optional PII detection and anonymization. Do not claim Presidio guarantees confidentiality.

**Promptfoo**  
https://github.com/promptfoo/promptfoo  
MIT.

Optional prompt-injection and cloud-agent security test runner.

## 13.5 Optional UI stack

Preferred polished demo:

- FastAPI — https://github.com/fastapi/fastapi — MIT.
- React + Vite.
- React Flow — https://github.com/xyflow/xyflow — MIT.
- TanStack Table — https://github.com/TanStack/table — MIT.
- Recharts — https://github.com/recharts/recharts — MIT.

Fallback rapid UI:

- Streamlit — https://github.com/streamlit/streamlit — Apache-2.0.

Choose one frontend architecture. Do not maintain both.

## 13.6 Explicit non-selections

- Beancount: GPL-2.0-only; reference concepts without copying code.
- SDV: licensing and statistical generation model do not align with this core.
- Neo4j: unnecessary database infrastructure.
- LangGraph, Semantic Kernel and a large MCP stack: unnecessary for the prescribed five-tool protocol.
- Full LiteLLM proxy: unnecessary unless model-provider complexity demonstrably justifies it.
- PostgreSQL, Airflow, Kafka, Kubernetes and Redis: not required.
- GPU model serving: prohibited as an official grading dependency.

## 13.7 Licensing procedure

Before adopting third-party code:

1. Verify its exact license at a selected commit.
2. Check subdirectory and dependency licenses.
3. Preserve required notices.
4. Record changes to borrowed code.
5. Pin tested package versions.
6. Generate a third-party notice file.
7. Check redistribution compatibility.

Use MIT as the provisional LedgerForge project license unless the maintainers choose another compatible license.

Do not copy GPL implementation files into an MIT-only core.

---

# 14. CLOUD SEMANTIC AUDIT GATEWAY

This optional extension adapts the deterministic semantic compiler principle from a previous industrial analytics project.

**Principle:** The LLM proposes an investigation. Deterministic software validates, compiles and executes permitted operations.

The cloud model must not be the authoritative financial calculator, evaluator or data-access controller.

## 14.1 Pipeline

    Restricted public observations
              |
              v
    Local semantic catalog
              |
              v
    Egress/privacy policy
              |
              v
    Cloud LLM investigation proposal
              |
              v
    Pydantic structured-output validation
              |
              v
    Deterministic audit compiler
              |
              v
    Official environment actions
              |
              v
    Local numerical reconciliation
              |
              v
    Evidence-backed finding proposal

The compiler may use only the five official actions for case-specific investigation.

Internal planning operations do not create additional environment action types.

## 14.2 Closed semantic grammar

Allow high-level intents such as:

- `inspect_invoice`
- `reconcile_payment`
- `compare_invoice_candidates`
- `verify_fx_date`
- `verify_reporting_period`
- `collect_supporting_evidence`
- `prepare_findings`

The model returns typed plans; the compiler converts them into official actions.

Do not execute free-form model-produced Python, SQL, shell commands or arbitrary API calls.

## 14.3 Privacy modes

**Zero-egress:** Entirely local deterministic agent; no cloud calls.

**Metadata-only:** Cloud receives generic schemas, possible audit workflows and permitted operation descriptions. It does not receive case-specific sensitive values.

**Redacted synthetic evidence:** Cloud receives limited, allowlisted, pseudonymized summaries of agent-observed synthetic records.

Pseudonymized amounts and transaction relationships may still reveal sensitive information in a real enterprise setting. Do not represent pseudonymization as a confidentiality guarantee.

## 14.4 Controls

- Default-deny outbound fields.
- No raw private truth or provenance.
- No secrets or real company data.
- Temporary opaque record handles.
- Explicit field-level allowlists.
- Output-schema validation.
- Action budgets enforced locally.
- Prompt-injection tests.
- Egress metadata logging with secret redaction.
- Deterministic local recalculation of financial claims.

The cloud gateway is optional and isolated from official offline verification.

Its performance must be reported separately from mandatory policy adapters.

---

# 15. INTERACTIVE DEMONSTRATION

The frontend should communicate through a minimal API and visualize generated episodes and benchmark traces.

Proposed screens:

## Screen 1 — Scenario Generator

- Select industry.
- Select difficulty.
- Select currency/period.
- Select configurable fault mix.
- Generate a synthetic episode.
- Show record counts and general metadata.

Do not disclose actual hidden error locations to the agent view.

## Screen 2 — Live Investigation / Replay

- Action timeline.
- Retrieved documents and records.
- Remaining steps.
- Evidence collection.
- Structured submitted findings.

## Screen 3 — Causal Evidence Graph

- Invoices, payments, ledger and related records.
- Typed relationships.
- Highlight evidence paths for reviewed findings.
- Post-evaluation privileged truth overlay.

## Screen 4 — Benchmark Laboratory

- Side-by-side baseline policies.
- P/R/F1.
- Reward and step count.
- Runtime.
- Attack-test outcomes.
- Replay invariance.

## Screen 5 — Optional Cloud Assistant

- Select configured provider.
- Choose privacy mode.
- Show approved outbound payload categories.
- Show the proposed semantic plan.
- Show compiled permitted actions.
- Display locally verified findings.

UI must consume existing core functionality and must not develop an alternate private scoring engine.

---

# 16. TARGET REPOSITORY STRUCTURE

    ledgerforge/
    ├── README.md
    ├── AGENTS.md
    ├── CLAUDE.md
    ├── LICENSE
    ├── THIRD_PARTY_NOTICES.md
    ├── .gitignore
    ├── .env.example
    ├── pyproject.toml
    ├── uv.lock
    ├── Makefile
    ├── Dockerfile
    │
    ├── docs/
    │   ├── MASTER_SPEC.md
    │   ├── ARCHITECTURE.md
    │   ├── DECISIONS.md
    │   ├── CONTRACTS.md
    │   ├── SCENARIOS.md
    │   ├── EVALUATION.md
    │   ├── SECURITY.md
    │   ├── BENCHMARK.md
    │   └── LIMITATIONS.md
    │
    ├── docs/ai/
    │   ├── TASKS.md
    │   ├── OWNERSHIP.md
    │   ├── HANDOFF.md
    │   ├── INTEGRATION.md
    │   └── REVIEW_LOG.md
    │
    ├── src/ledgerforge/
    │   ├── contracts/
    │   │   ├── schemas.py
    │   │   ├── actions.py
    │   │   ├── identifiers.py
    │   │   └── versions.py
    │   │
    │   ├── domain/
    │   │   ├── entities.py
    │   │   ├── graph.py
    │   │   ├── money.py
    │   │   ├── accounting.py
    │   │   └── policies.py
    │   │
    │   ├── simulator/
    │   │   ├── scenarios.py
    │   │   ├── world.py
    │   │   ├── projections.py
    │   │   ├── faults.py
    │   │   ├── compositions.py
    │   │   └── export.py
    │   │
    │   ├── verification/
    │   │   ├── invariants.py
    │   │   ├── evidence.py
    │   │   ├── counterfactual.py
    │   │   └── acceptance.py
    │   │
    │   ├── environment/
    │   │   ├── env.py
    │   │   ├── tools.py
    │   │   ├── calculator.py
    │   │   └── state.py
    │   │
    │   ├── evaluation/
    │   │   ├── matcher.py
    │   │   ├── reward.py
    │   │   └── private_runner.py
    │   │
    │   ├── agents/
    │   │   ├── base.py
    │   │   ├── random_policy.py
    │   │   ├── reconciliation_policy.py
    │   │   ├── flag_all_policy.py
    │   │   └── oracle_policy.py
    │   │
    │   ├── benchmark/
    │   │   ├── runner.py
    │   │   ├── trajectories.py
    │   │   ├── metamorphic.py
    │   │   └── reports.py
    │   │
    │   ├── semantic_gateway/
    │   │   ├── catalog.py
    │   │   ├── planner.py
    │   │   ├── compiler.py
    │   │   ├── privacy.py
    │   │   └── model_adapter.py
    │   │
    │   ├── api/
    │   │   └── app.py
    │   │
    │   └── cli.py
    │
    ├── configs/
    │   ├── scenarios/
    │   ├── industries/
    │   └── policies/
    │
    ├── episodes/
    │   ├── train/
    │   └── dev/
    │
    ├── private/
    │   └── .gitkeep
    │
    ├── dashboard/
    ├── tests/
    │   ├── contract/
    │   ├── financial/
    │   ├── generator/
    │   ├── reward/
    │   ├── security/
    │   ├── reproducibility/
    │   └── integration/
    │
    ├── scripts/
    └── outputs/
        ├── trajectories/
        ├── benchmarks/
        └── reports/

Do not automatically populate every module with placeholder abstractions. Create directories and minimal interfaces first; implement iteratively.

Private ground-truth files used for development may exist in a protected evaluator fixture bundle. Never distribute or mount those fixtures into an agent runtime.

---

# 17. ENGINEERING CONTRACTS AND MODULE BOUNDARIES

Before feature implementation, freeze these public interfaces:

- `ScenarioConfig`
- `Company`
- `BusinessEvent`
- `FinancialWorld`
- `PublicEpisode`
- `PrivateTruthBundle`
- `TruthIssue`
- `EvidenceCertificate`
- `FaultResult`
- `EnvAction`
- `EnvObservation`
- `Finding`
- `Submission`
- `ScoreReport`
- `AgentPolicy`

The specific field definitions belong in `docs/CONTRACTS.md` and `contracts/schemas.py`.

## Boundary invariants

- Simulator can generate private truth.
- Environment can read public episode data only.
- Agent cannot import or access the private truth bundle.
- Evaluator can read final submissions plus private truth.
- Benchmark runner may coordinate public and private components but may not expose private truth to policies.
- UI reads only approved, role-appropriate API projections.
- Cloud gateway can operate on authorized observations only.

## Critical contract question

The official CSV format contains no mandatory `journal_id`, whereas the internal model needs grouped balanced entries.

Keep a journal grouping internally and define how that information is projected without violating the official ledger schema.

Similarly, decide how `payments.jsonl.invoice_refs` represents remittance intent versus the actual accounting allocation reflected in the ledger.

These details must be settled with explicit sample episodes before parallel development begins.

---

# 18. TESTING AND RELEASE GATES

## Test suites

**Contracts**
- Valid and invalid reset/step.
- All five tools.
- Pagination limits.
- Unknown identifiers.
- Submit limits.
- Episode termination/truncation.
- Serialization.

**Finance**
- Double-entry consistency.
- Native/functional currency reconciliation.
- Currency exponent handling.
- FX rate direction and rounding.
- Period boundary handling.
- Legitimate refunds and split payments.

**Fault injection**
- Four standalone faults.
- Both interacting cases.
- Clean worlds.
- Counterfactual correction.
- Complete public evidence.
- No unintended errors.

**Reward**
- Exact TP/FP/FN.
- Maximum one-to-one assignment.
- Empty truth behavior.
- Duplicate claims.
- Wrong amounts/currencies/IDs.
- Malformed submissions.
- Inspection cost.

**Security**
- No truth/provenance access.
- No seed leakage.
- No path leakage.
- No arbitrary calculator execution.
- No unsafe cloud output execution.
- No accidental secret exposure.

**Reproducibility**
- Identical seed/config replay.
- Reset isolation.
- Permutation invariance.
- ID-renaming invariance.
- Cross-process deterministic output.

**Performance**
- Episode generation and evaluation within resource limits.
- No network dependency.
- No GPU dependency.
- Reasonable memory and image size.

## Completion gates

**Gate 0:** Contracts and ownership frozen.

**Gate 1:** One full vertical slice works end-to-end.

**Gate 2:** Four error types and two compositions pass independent validation.

**Gate 3:** Official evaluator and all adversarial reward tests pass.

**Gate 4:** Four baselines, trajectories, 10 train and 10 dev episodes, replay and offline container work.

**Gate 5:** Optional cloud gateway and dashboard work without affecting the official core.

A gate is complete only when its acceptance tests pass.

Do not represent a feature as complete because its classes or files exist.

---

# 19. CLAUDE + CODEX COLLABORATION

Use Claude Code as architectural lead and integration coordinator.

Use Codex as independent implementation owner for the environment/evaluation side and as a critical reviewer of financial invariants.

Two human developers approve architectural changes and merges.

## Claude ownership

Claude owns:

- Requirements interpretation and planning.
- Architecture and contracts.
- Financial domain model.
- Scenario generator.
- Fault injection.
- Financial verification.
- Evidence certificates.
- Generator-side tests.
- Final integration.
- README and architecture documentation.
- Optional semantic gateway after the core passes.

## Codex ownership

Codex owns:

- RL environment and tools.
- Safe calculator.
- Evaluator and matcher.
- Reward implementation.
- Agent adapters.
- Trajectory recording.
- Benchmark runner.
- Contract and reward tests.
- Adversarial testing.
- Optional dashboard/backend after the core passes.

The important objective is **non-overlapping file ownership**.

Claude and Codex should agree on interfaces and then work separately.

## Git workflow

Recommended:

- Main branch: `main`.
- Claude branch/worktree: `feat/financial-core`.
- Codex branch/worktree: `feat/evaluation-core`.
- Integration branch: `integration/ledgerforge`.

Use separate Git worktrees when running concurrently.

Do not allow simultaneous edits to the same source file.

Contracts may only be modified through explicit interface-change proposals and human approval after Gate 0.

## Shared agent coordination files

`docs/ai/TASKS.md`
- Task ID.
- Owner.
- Scope.
- Dependencies.
- Acceptance tests.
- Status.
- Commit/branch reference.

`docs/ai/HANDOFF.md`
- Completed work.
- Interface changes.
- Commands run.
- Test outcomes.
- Blockers.
- Next integration step.

`docs/ai/REVIEW_LOG.md`
- Identified defect.
- Severity.
- Reproduction.
- Proposed fix.
- Resolution.

`docs/DECISIONS.md`
- Architecture decision.
- Alternatives.
- Rationale.
- Consequences.

Neither AI agent should rely on the other agent's conversational context. The repository and these files are the shared state.

## Review procedure

At each milestone:

1. Implementer completes the assigned module.
2. Implementer runs targeted tests.
3. Implementer records commands and outputs.
4. Other agent reviews the diff or commit.
5. Reviewer identifies correctness, security and interface risks.
6. Fixes are applied by the file owner.
7. Integrator merges the approved change.
8. Full relevant tests run after merge.

Avoid agents rewriting each other's work without a reviewed handoff.

## Completion definition

Each task is complete only when it has:

- Implemented behavior.
- Relevant tests.
- Accurate documentation.
- No unauthorized schema changes.
- No hidden-truth leakage.
- Recorded test results.
- A reviewable commit or patch.

---

# 20. DELIVERABLES

The official submission must include:

1. Source code and suitable license.
2. Pinned dependencies.
3. Financial generator.
4. RL environment and required actions.
5. Matcher and official terminal reward.
6. Public schemas and policies.
7. 10 train episodes.
8. 10 dev episodes.
9. Tests.
10. Four baseline adapters.
11. `trajectories.jsonl`.
12. Short design note.
13. Container instructions.
14. One-command verification.
15. Demonstration.

Aim for:

    make verify

as the main developer verification command, and provide an equivalent containerized command documented in README.

The official verification should not need the cloud gateway, frontend or API keys.

## README outline

- Product description.
- Hackathon task.
- Architecture overview.
- Installation.
- One-command verification.
- Dataset format.
- Error types.
- RL interface.
- Reward computation.
- Baseline policies.
- Replay and benchmark commands.
- Optional cloud/UI setup.
- Third-party components.
- Limitations.
- How to reproduce reported results.

## Documentation principles

Never fabricate performance claims, successful test results, implemented features or dataset statistics.

Use clear labels:

- Implemented.
- In progress.
- Planned.
- Verified.
- Not verified.

---

# 21. DEMONSTRATION STRATEGY

The main pitch should demonstrate:

1. Generation of a realistic fictional industrial company.
2. Its financial records and supported business relationships.
3. A policy-controlled agent investigation.
4. Discovery of an interacting financial discrepancy.
5. Evidence-backed submission.
6. Independent reward calculation.
7. Failure of a flag-all attack.
8. Equivalent outcome after ID renaming and record permutation.

Show separate actual metrics for:

- Rule-based policy.
- Optional cloud-assisted policy.
- Oracle.
- Attack policy.

Do not conflate oracle performance with ordinary model performance.

The UI should expose complex financial relationships clearly without suggesting that visual polish is the judged deliverable.

---

# 22. RISK REGISTER

## Critical risk: Incorrect financial truth

Mitigation:
- Canonical source event model.
- Independent financial validator.
- Counterfactual correction checks.
- Rejection of unprovable generated cases.

## Critical risk: Ground-truth leakage

Mitigation:
- Separate evaluator process.
- Private fixture access control.
- Explicit observation allowlist.
- Security tests.
- No private artifacts mounted into the agent process.

## Critical risk: Wrong reward behavior

Mitigation:
- Exact published formula.
- Bipartite matching.
- Exhaustive edge-case tests.
- Adversarial submissions.

## High risk: Schema drift between Claude and Codex

Mitigation:
- Contract freeze.
- Shared samples.
- Interface-level tests.
- No unapproved modifications after Gate 0.

## High risk: Cloud inference dependencies

Mitigation:
- Optional adapter only.
- Zero-egress official mode.
- Offline verification independent of provider APIs.

## High risk: Scope expansion

Mitigation:
- Strict gate ordering.
- Optional components after official core.
- Reject speculative features without score or demo impact.

## High risk: Third-party compatibility

Mitigation:
- Small dependency set.
- Exact license and version review.
- Pinned lockfile.
- Targeted integration tests.

---

# 23. IMMEDIATE PROJECT EXECUTION PRIORITIES

Do not begin with the dashboard or the cloud LLM.

**Step 1 — Contract freeze**

Review official PDF and this specification.

Resolve the exact public/private schemas, ID conventions, money semantics, evidence requirements and action contract.

**Step 2 — Scaffold project**

Create root files, package directories, minimal contract types, documentation, test infrastructure and dependency configuration.

**Step 3 — Minimal end-to-end scenario**

One clean company, one duplicate invoice, accessible evidence, one agent interaction and one correct score.

**Step 4 — Complete official functionality**

Four fault types, two interacting cases, clean episodes, reward robustness and all mandatory policies.

**Step 5 — Verification**

Replay, permutation, paired tests, security, performance and offline container.

**Step 6 — Enhancements**

Semantic cloud agent, privacy modes, interactive UI and advanced industry scenario richness.

---

# 24. NON-NEGOTIABLE ENGINEERING PRINCIPLES

1. Financial truth is deterministic, not LLM-generated.
2. Every injected issue must be independently provable.
3. No inaccessible ground-truth evidence.
4. No hidden evaluator information in agent observations.
5. No alteration of the official reward.
6. No additional mandatory actions.
7. No network or paid API requirement for official evaluation.
8. No real financial records.
9. Monetary arithmetic uses exact representations.
10. Reproducibility is a tested property.
11. Agent outputs are untrusted until validated.
12. Dependency reuse must be licensed and documented.
13. No model, UI or benchmark claim without measured evidence.
14. No concurrent modification of owned files.
15. Every milestone ends with executable acceptance tests.

# 25. DEFINITION OF SUCCESS

LedgerForge is ready for submission when an independent evaluator can:

- Launch it through the documented verification command.
- Generate multiple valid synthetic financial episodes.
- Verify all required anomaly types.
- Interact through the exact official tool interface.
- Confirm that findings require correct evidence.
- Run all four baseline adapters.
- Observe attack-resistant reward calculations.
- Reproduce episodes and outcomes.
- Verify invariance under ID and record-order transformations.
- Confirm that hidden ground truth does not leak.
- Inspect real trajectories and benchmark reports.
- Run the mandatory environment without network, GPU or cloud API keys.

The finished product should be impressive because it is **financially rigorous, reproducible, difficult to exploit and supported by independent evidence**.

Everything else is secondary.
