"""Causal fault operators. Each one picks a valid business event, checks preconditions, applies
one controlled accounting mutation, and returns the exact discrepancy plus its public evidence.

Preconditions keep faults from cascading into unintended extra issues (e.g. FX and cutoff
targets are unpaid, allocation targets are base-currency payments without a legitimate
unapplied remainder). The acceptance gate re-proves every claim independently anyway.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

from ledgerforge.contracts.money import add_days, convert, parse_offset, parse_ts
from ledgerforge.contracts.schemas import (
    ACC_ADVANCES,
    ACC_AP,
    DUPLICATE_INVOICE,
    DUPLICATE_WITH_ALLOCATION,
    ERROR_TYPES,
    FX_RATE,
    FX_WITH_PERIOD,
    PAYMENT_ALLOCATION,
    REPORTING_PERIOD,
)
from ledgerforge.sim.world import World, invoice_lines, make_invoice, post_regular

EXCLUDED = {"cn_set", "unposted", "tz_boundary", "faulted", "recurring"}
PAID = {"paid", "instalment", "split"}


class NoCandidate(Exception):
    """Preconditions cannot be met in this world; the generator retries with a new attempt."""


def _spec(
    type_: str,
    affected: list[str],
    amount: int,
    currency: str,
    evidence: list[str],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    if amount <= 0:
        raise NoCandidate(f"{type_} produced a zero discrepancy")
    return {
        "type": type_,
        "affected_ids": sorted(affected),
        "expected_amount_minor": amount,
        "currency": currency,
        "allowed_evidence_sets": [sorted(evidence)],
        "provenance": provenance,
    }


def _eligible(w: World, extra_excluded: set[str] = frozenset()) -> list[dict[str, Any]]:
    return [
        i
        for i in w.invoices
        if i["total_minor"] > 0
        and f"inv:{i['doc_id']}" in w.journals
        and not w.meta[i["doc_id"]]["tags"] & (EXCLUDED | extra_excluded)
    ]


def _local(w: World, ts: str):
    return parse_ts(ts).astimezone(parse_offset(w.tz))


def duplicate_invoice(
    w: World,
    r: random.Random,
    original: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """F1: the same supplier obligation is entered a second time under a mangled number."""
    candidates = [original] if original else _eligible(w)
    r.shuffle(candidates)
    for orig in candidates:
        issued = _local(w, orig["issued_at"])
        for delta in (
            timedelta(days=r.randint(1, 6), seconds=r.randint(0, 3600)),
            timedelta(hours=r.randint(1, 3)),
        ):
            if (issued + delta).date().isoformat() <= w.end:
                break
        else:
            continue
        vendor = next(v for v in w.vendors if v["entity_id"] == orig["entity_id"])
        dup = make_invoice(
            w, r, vendor, issued + delta, invoice_lines(w, orig), ("faulted", "duplicate")
        )
        oid = orig["invoice_id"]
        variants = [f"{oid}-1", f"{oid}A", oid.replace("-", "") if "-" in oid else f"{oid}/1"]
        existing = {i["invoice_id"] for i in w.invoices}
        dup["invoice_id"] = next((v for v in variants if v not in existing), f"{oid}-DUP")
        post_regular(w, r, dup)
        w.meta[orig["doc_id"]]["tags"].add("faulted")
        amount = -w.meta[dup["doc_id"]]["ap"]
        spec = _spec(
            DUPLICATE_INVOICE,
            [orig["doc_id"], dup["doc_id"]],
            amount,
            w.base,
            [orig["doc_id"], dup["doc_id"], w.meta[dup["doc_id"]]["ap_row"]],
            {
                "operator": "duplicate_invoice",
                "original": orig["doc_id"],
                "duplicate": dup["doc_id"],
                "duplicate_invoice_id": dup["invoice_id"],
                "counterfactual": {
                    "remove_journal": f"inv:{dup['doc_id']}",
                    "ap_overstatement_minor": amount,
                },
            },
        )
        return spec, dup
    raise NoCandidate("no invoice can be duplicated inside the period")


def payment_allocation(
    w: World,
    r: random.Random,
    payment: dict[str, Any] | None = None,
    invoice_id: str | None = None,
    target_doc: str | None = None,
) -> dict[str, Any]:
    """F2: remittance says invoice I, the ledger allocates part/all of it elsewhere."""
    candidates = (
        [payment]
        if payment
        else [
            p
            for p in w.payments
            if p["currency"] == w.base
            and p["invoice_refs"]
            and p["amount_minor"] == sum(x["amount_minor"] for x in p["invoice_refs"])
            and "faulted" not in w.meta[p["doc_id"]]["tags"]
        ]
    )
    if not candidates:
        raise NoCandidate("no base-currency payment with remittance references")
    pay = r.choice(candidates)
    ref = (
        next(x for x in pay["invoice_refs"] if x["invoice_id"] == invoice_id)
        if invoice_id
        else r.choice(pay["invoice_refs"])
    )
    entity = w.meta[pay["doc_id"]]["entity_id"]
    refs = {x["invoice_id"] for x in pay["invoice_refs"]}
    if target_doc:
        variant, target = "misapplied", w.doc(target_doc)
    else:
        variant = r.choice(("missing", "partial", "misapplied"))
        others = [
            i
            for i in _eligible(w, {"duplicate"})
            if i["entity_id"] == entity and i["currency"] == w.base and i["invoice_id"] not in refs
        ]
        target = r.choice(others) if variant == "misapplied" and others else None
        if variant == "misapplied" and target is None:
            variant = "partial"
    a = ref["amount_minor"]
    x = a if variant == "missing" else r.randint(max(1, a * 15 // 100), max(1, a * 85 // 100))
    journal = w.journals[f"pay:{pay['doc_id']}"]
    ap_row = next(
        row
        for row in journal["lines"]
        if row["account"] == ACC_AP and row["invoice_id"] == ref["invoice_id"]
    )
    before = dict(ap_row)
    ap_row["debit_minor"] -= x
    if ap_row["debit_minor"] == 0:
        journal["lines"].remove(ap_row)
    account, inv_id = (ACC_AP, target["invoice_id"]) if target else (ACC_ADVANCES, None)
    new_row = w.row(r, ap_row["timestamp"], account, x, entity, inv_id, pay["payment_id"])
    journal["lines"].append(new_row)
    w.meta[pay["doc_id"]]["tags"].add("faulted")
    inv_doc = w.inv_doc(ref["invoice_id"])
    return _spec(
        PAYMENT_ALLOCATION,
        [pay["doc_id"], inv_doc],
        x,
        w.base,
        [pay["doc_id"], inv_doc, new_row["row_id"]],
        {
            "operator": "payment_allocation",
            "variant": variant,
            "payment": pay["doc_id"],
            "invoice": inv_doc,
            "misposted_to": target["doc_id"] if target else ACC_ADVANCES,
            "before": before,
            "after_new_row": new_row,
            "counterfactual": {"restore_allocation_minor": x},
        },
    )


def fx_rate(w: World, r: random.Random) -> dict[str, Any]:
    """F3: a foreign invoice valued with the rate of a date other than its recognition date."""
    candidates = [
        i
        for i in _eligible(w)
        if i["currency"] != w.base and not w.meta[i["doc_id"]]["tags"] & PAID
    ]
    r.shuffle(candidates)
    for inv in candidates:
        meta = w.meta[inv["doc_id"]]
        rec = w.rec_day(inv["issued_at"])
        posted_day = _local(w, meta["posted_at"]).date().isoformat()
        options = [posted_day] if posted_day != rec else []
        options += [add_days(rec, -k) for k in r.sample(range(3, 13), 4)]
        correct_id, correct_ap = meta["rate_fx_id"], meta["ap"]
        for wrong in options:
            wrong_id, rate = w.fx.effective(inv["currency"], w.base, wrong)
            if (
                wrong_id == correct_id
                or convert(inv["total_minor"], inv["currency"], w.base, rate) == -correct_ap
            ):
                continue
            w.post_invoice(inv, _local(w, meta["posted_at"]), rate_day=wrong)
            meta["tags"].add("faulted")
            amount = abs(meta["ap"] - correct_ap)
            return _spec(
                FX_RATE,
                [inv["doc_id"]],
                amount,
                w.base,
                [inv["doc_id"], meta["ap_row"], correct_id],
                {
                    "operator": "fx_rate",
                    "invoice": inv["doc_id"],
                    "correct_rate_id": correct_id,
                    "used_rate_id": wrong_id,
                    "counterfactual": {
                        "correct_ap_minor": -correct_ap,
                        "booked_ap_minor": -meta["ap"],
                    },
                },
            )
    raise NoCandidate("no unpaid foreign invoice for an FX fault")


def reporting_period(
    w: World,
    r: random.Random,
    foreign: bool = False,
    wrong_rate: bool = False,
) -> list[dict[str, Any]]:
    """F4: an invoice recognised in the next period is booked before period end.

    With wrong_rate (interaction B) it is also valued at the booking-date rate, giving a second,
    independently provable FX finding on the same invoice.
    """
    vendors = [v for v in w.vendors if (v["currency"] != w.base) == foreign] or w.vendors
    vendor = r.choice(vendors)
    issued_day = add_days(w.end, r.randint(1, 5))
    inv = make_invoice(
        w, r, vendor, w.local_dt(issued_day, r.randint(9, 17) * 3600), tags=("faulted", "cutoff")
    )
    post_day = add_days(w.end, -r.randint(0, 3))
    rec = w.rec_day(inv["issued_at"])
    w.post_invoice(
        inv,
        w.local_dt(post_day, r.randint(10, 18) * 3600),
        rate_day=post_day if wrong_rate else None,
    )
    meta = w.meta[inv["doc_id"]]
    booked = -meta["ap"]
    specs = [
        _spec(
            REPORTING_PERIOD,
            [inv["doc_id"]],
            booked,
            w.base,
            [inv["doc_id"], meta["ap_row"]],
            {
                "operator": "reporting_period",
                "invoice": inv["doc_id"],
                "recognition_date": rec,
                "booked_on": post_day,
                "counterfactual": {"move_to_period_of": rec, "amount_minor": booked},
            },
        )
    ]
    if wrong_rate:
        if inv["currency"] == w.base:
            raise NoCandidate("interaction B needs a foreign-currency vendor")
        correct_id, rate = w.fx.effective(inv["currency"], w.base, rec)
        correct = convert(inv["total_minor"], inv["currency"], w.base, rate)
        if correct_id == meta["rate_fx_id"]:
            raise NoCandidate("booking date and recognition date share one rate")
        specs.append(
            _spec(
                FX_RATE,
                [inv["doc_id"]],
                abs(booked - correct),
                w.base,
                [inv["doc_id"], meta["ap_row"], correct_id],
                {
                    "operator": "fx_rate(interaction_b)",
                    "invoice": inv["doc_id"],
                    "correct_rate_id": correct_id,
                    "used_rate_id": meta["rate_fx_id"],
                    "counterfactual": {"correct_ap_minor": correct, "booked_ap_minor": booked},
                },
            )
        )
    return specs


def duplicate_with_allocation(w: World, r: random.Random) -> list[dict[str, Any]]:
    """Interaction A: obligation recorded twice; its payment is partly applied to the copy."""
    singles = [
        p
        for p in w.payments
        if p["currency"] == w.base
        and len(p["invoice_refs"]) == 1
        and "faulted" not in w.meta[p["doc_id"]]["tags"]
    ]
    eligible = {i["invoice_id"]: i for i in _eligible(w)}
    pairs = [
        (p, eligible[p["invoice_refs"][0]["invoice_id"]])
        for p in singles
        if p["invoice_refs"][0]["invoice_id"] in eligible
        and p["invoice_refs"][0]["amount_minor"] == p["amount_minor"]
    ]
    if not pairs:
        raise NoCandidate("no fully paid base-currency invoice for interaction A")
    pay, orig = r.choice(pairs)
    dup_spec, dup = duplicate_invoice(w, r, orig)
    alloc_spec = payment_allocation(w, r, pay, orig["invoice_id"], dup["doc_id"])
    return [dup_spec, alloc_spec]


def inject(w: World) -> list[dict[str, Any]]:
    """Apply the configured faults in a fixed order (deterministic for a given seed/attempt)."""
    r = w.rng("faults")
    specs: list[dict[str, Any]] = []
    for _ in range(w.config.interactions.get(DUPLICATE_WITH_ALLOCATION, 0)):
        specs += duplicate_with_allocation(w, r)
    for _ in range(w.config.interactions.get(FX_WITH_PERIOD, 0)):
        specs += reporting_period(w, r, foreign=True, wrong_rate=True)
    for type_ in ERROR_TYPES:
        for _ in range(w.config.faults.get(type_, 0)):
            if type_ == DUPLICATE_INVOICE:
                specs.append(duplicate_invoice(w, r)[0])
            elif type_ == PAYMENT_ALLOCATION:
                specs.append(payment_allocation(w, r))
            elif type_ == FX_RATE:
                specs.append(fx_rate(w, r))
            else:
                specs += reporting_period(w, r, foreign=r.random() < 0.5)
    return specs


__all__ = ["NoCandidate", "inject", "date"]
