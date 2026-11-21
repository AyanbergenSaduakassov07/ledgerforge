"""Episode assembly: world -> faults -> public projection -> independent acceptance gate."""

from __future__ import annotations

from typing import Any

from ledgerforge.contracts.schemas import (
    CURRENCY_EXPONENTS,
    GENERATOR_VERSION,
    SCHEMA_VERSION,
    PrivateTruthBundle,
    PublicEpisode,
    ScenarioConfig,
    TruthIssue,
)
from ledgerforge.sim.faults import NoCandidate, inject
from ledgerforge.sim.salt import salt_public, salt_spec
from ledgerforge.sim.world import World, build_world
from ledgerforge.verification.auditor import audit, issue_key

MAX_ATTEMPTS = 20
LEDGER_ROWS = (200, 2000)  # official episode ranges
DOCS = (20, 200)


class GenerationFailed(RuntimeError):
    """No attempt passed the acceptance gate."""


def policy(w: World) -> dict[str, Any]:
    return {
        "timezone": w.tz_name,
        "timezone_offset": w.tz,
        "recognition_date": "local calendar date of invoice issued_at / payment timestamp "
        "at timezone_offset",
        "period_bounds": "inclusive",
        "fx_rule": "rate of the recognition date; if fx.csv has no row that date, the most "
        "recent earlier row; rate = target units per one source unit",
        "rounding": "ROUND_HALF_EVEN to the target currency minor unit",
        "ledger_currency": "all ledger rows are in base_currency",
        "journal_grouping": "rows group by payment_id, else invoice_id, else timestamp; "
        "every group balances",
        "ap_relief": "AP debit for a payment ref = round_half_even(ref_amount * invoice AP "
        "credit / invoice total); remittance amount above the refs goes to supplier advances",
        "amount_tolerance_minor": 1,
    }


def project(w: World) -> PublicEpisode:
    r = w.rng("order")
    ledger = sorted(w.ledger(), key=lambda row: (row["timestamp"], row["row_id"]))
    invoices, payments = list(w.invoices), list(w.payments)
    if w.config.order_salt:  # metamorphic transform: same world, different public order
        salted = w.rng(f"order:{w.config.order_salt}")
        for table in (ledger, invoices, payments):
            salted.shuffle(table)
    else:
        r.shuffle(invoices)
        r.shuffle(payments)
    fx = sorted(w.fx_rows, key=lambda x: (x["date"], x["source_currency"]))
    currencies = {w.base} | {d["currency"] for d in invoices + payments}
    currencies |= {x[k] for x in fx for k in ("source_currency", "target_currency")}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "episode_id": w.episode_id,
        "base_currency": w.base,
        "currency_exponents": {c: CURRENCY_EXPONENTS[c] for c in sorted(currencies)},
        "period_start": w.start,
        "period_end": w.end,
        "timezone": w.tz_name,
        "counts": {
            "ledger": len(ledger),
            "invoices": len(invoices),
            "payments": len(payments),
            "fx": len(fx),
        },
        "rounding": "ROUND_HALF_EVEN",
    }
    return PublicEpisode(manifest, policy(w), ledger, invoices, payments, fx)


def _gate(public: PublicEpisode, specs: list[dict[str, Any]]) -> list[str]:
    result = audit(public.to_dict())
    problems = list(result.violations)
    docs = len(public.invoices) + len(public.payments)
    if not (LEDGER_ROWS[0] <= len(public.ledger) <= LEDGER_ROWS[1] and DOCS[0] <= docs <= DOCS[1]):
        problems.append(f"size out of official range: ledger={len(public.ledger)} docs={docs}")
    truth = {issue_key(s) for s in specs}
    if result.keys() != truth:
        problems.append(
            f"auditor/truth mismatch: missing={truth - result.keys()} extra={result.keys() - truth}"
        )
    known = {r["row_id"] for r in public.ledger} | {
        d["doc_id"] for d in public.invoices + public.payments
    }
    known |= {f"{x['date']}:{x['source_currency']}:{x['target_currency']}" for x in public.fx}
    found = {issue_key(i): set(i["evidence_ids"]) for i in result.issues}
    for s in specs:
        (allowed,) = s["allowed_evidence_sets"]
        if not set(allowed) <= known:
            problems.append(f"unresolvable evidence in {s['type']}")
        elif not set(allowed) <= found.get(issue_key(s), set()):
            problems.append(f"auditor cannot derive evidence for {s['type']}")
    return problems


def generate_episode(
    seed: int,
    config: ScenarioConfig | None = None,
) -> tuple[PublicEpisode, PrivateTruthBundle]:
    config = config or ScenarioConfig()
    config.validate()
    failures: list[str] = []
    for attempt in range(MAX_ATTEMPTS):
        w = build_world(seed, config, attempt)
        try:
            specs = inject(w)
        except NoCandidate as e:
            failures.append(f"attempt {attempt}: {e}")
            continue
        public = project(w)
        episode_id = w.episode_id
        if config.id_salt:
            public, mapping = salt_public(public, config.id_salt)
            specs = [salt_spec(s, mapping) for s in specs]
            episode_id = public.manifest["episode_id"]
        problems = _gate(public, specs)
        if problems:
            failures.append(f"attempt {attempt}: {problems[:3]}")
            continue
        specs.sort(key=issue_key)
        issues = tuple(
            TruthIssue(
                f"ISS-{i + 1:02d}",
                s["type"],
                tuple(s["affected_ids"]),
                s["expected_amount_minor"],
                s["currency"],
                tuple(tuple(e) for e in s["allowed_evidence_sets"]),
            )
            for i, s in enumerate(specs)
        )
        provenance = {
            "seed": seed,
            "attempt": attempt,
            "config": config.to_dict(),
            "generator_version": GENERATOR_VERSION,
            "mutations": [s["provenance"] for s in specs],
        }
        return public, PrivateTruthBundle(episode_id, issues, provenance)
    raise GenerationFailed(f"seed {seed}: {failures[-3:]}")
