"""Independent public-data auditor.

Reads ONLY the public episode (manifest, policy, ledger, invoices, payments, fx) and recomputes
every discrepancy from the published rules. It never sees generator provenance. The acceptance
gate requires its findings to equal the declared truth exactly, which proves that (a) every
labelled issue is provable from public evidence and (b) there is no unlabelled extra issue.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

from ledgerforge.contracts.money import FxTable, convert, in_period, local_date, parse_ts
from ledgerforge.contracts.schemas import (
    ACC_ADVANCES,
    ACC_AP,
    ACC_BANK,
    DUPLICATE_INVOICE,
    FX_RATE,
    PAYMENT_ALLOCATION,
    REPORTING_PERIOD,
)


@dataclass
class AuditResult:
    issues: list[dict[str, Any]] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    def keys(self) -> set[tuple]:
        return {issue_key(i) for i in self.issues}


def issue_key(issue: dict[str, Any]) -> tuple:
    amount = issue.get("amount_minor", issue.get("expected_amount_minor"))
    return issue["type"], tuple(sorted(issue["affected_ids"])), amount, issue["currency"]


def _net(rows: list[dict[str, Any]]) -> int:
    return sum(r["debit_minor"] - r["credit_minor"] for r in rows)


def journal_key(row: dict[str, Any]) -> str:
    """Published grouping rule: payment_id, else invoice_id, else exact timestamp."""
    if row["payment_id"]:
        return f"pay:{row['payment_id']}"
    if row["invoice_id"]:
        return f"inv:{row['invoice_id']}"
    return f"ts:{row['timestamp']}"


class _Ctx:
    def __init__(self, ep: dict[str, Any]) -> None:
        m, p = ep["manifest"], ep["policy"]
        self.base, self.tz = m["base_currency"], p["timezone_offset"]
        self.start, self.end = m["period_start"], m["period_end"]
        self.fx = FxTable(ep["fx"])
        self.invoices = {i["invoice_id"]: i for i in ep["invoices"]}
        self.payments = ep["payments"]
        self.journals: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in ep["ledger"]:
            self.journals[journal_key(row)].append(row)
        self.out = AuditResult()

    def to_base(self, amount: int, currency: str, day: str) -> int | None:
        if currency == self.base:
            return amount
        found = self.fx.effective(currency, self.base, day)
        return None if found is None else convert(amount, currency, self.base, found[1])

    def ap_row(self, invoice_id: str) -> dict[str, Any] | None:
        rows = [r for r in self.journals.get(f"inv:{invoice_id}", []) if r["account"] == ACC_AP]
        return rows[0] if len(rows) == 1 else None

    def add(self, type_: str, affected: list[str], amount: int, evidence: set[str]) -> None:
        self.out.issues.append(
            {
                "type": type_,
                "affected_ids": sorted(affected),
                "amount_minor": abs(amount),
                "currency": self.base,
                "evidence_ids": sorted(evidence),
            }
        )


def _check_ledger(c: _Ctx) -> None:
    for key, rows in c.journals.items():
        if _net(rows):
            c.out.violations.append(f"journal {key} does not balance")
        for r in rows:
            if r["currency"] != c.base:
                c.out.violations.append(f"row {r['row_id']} not in base currency")
            if not in_period(local_date(r["timestamp"], c.tz), c.start, c.end):
                c.out.violations.append(f"row {r['row_id']} posted outside the period")
            if r["invoice_id"] and r["invoice_id"] not in c.invoices:
                c.out.violations.append(f"row {r['row_id']} references unknown invoice")


def _check_invoices(c: _Ctx) -> None:
    """Posting, FX valuation (F3) and reporting period (F4)."""
    for inv in c.invoices.values():
        rec = local_date(inv["issued_at"], c.tz)
        posted = f"inv:{inv['invoice_id']}" in c.journals
        if not posted:
            if in_period(rec, c.start, c.end):
                c.out.violations.append(f"in-period invoice {inv['doc_id']} never posted")
            continue
        ap = c.ap_row(inv["invoice_id"])
        if ap is None:
            c.out.violations.append(f"invoice {inv['doc_id']} has no single AP row")
            continue
        booked = ap["credit_minor"] - ap["debit_minor"]
        if not in_period(rec, c.start, c.end):
            c.add(REPORTING_PERIOD, [inv["doc_id"]], booked, {inv["doc_id"], ap["row_id"]})
        if inv["currency"] == c.base:
            if booked != inv["total_minor"]:
                c.out.violations.append(f"base invoice {inv['doc_id']} booked at wrong amount")
            continue
        found = c.fx.effective(inv["currency"], c.base, rec)
        if found is None:
            c.out.violations.append(f"no fx rate for invoice {inv['doc_id']}")
            continue
        expected = convert(inv["total_minor"], inv["currency"], c.base, found[1])
        if expected != booked:
            c.add(
                FX_RATE, [inv["doc_id"]], booked - expected, {inv["doc_id"], ap["row_id"], found[0]}
            )


def _line_key(inv: dict[str, Any], sign: int) -> tuple:
    lines = tuple(
        sorted(
            (
                li["description"],
                sign * li["quantity"],
                li["unit_price_minor"],
                sign * li["amount_minor"],
            )
            for li in inv["line_items"]
        )
    )
    return inv["entity_id"], inv["currency"], sign * inv["total_minor"], lines


def _check_duplicates(c: _Ctx) -> None:
    """F1: same supplier, currency, amount and identical line items (incl. PO / service month),
    both posted, and not cancelled by a matching credit note."""
    posted = [i for i in c.invoices.values() if f"inv:{i['invoice_id']}" in c.journals]
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    cancels: dict[tuple, int] = defaultdict(int)
    for inv in posted:
        if inv["total_minor"] > 0:
            groups[_line_key(inv, 1)].append(inv)
        else:
            cancels[_line_key(inv, -1)] += 1
    for key, invs in groups.items():
        live = sorted(invs, key=lambda i: (parse_ts(i["issued_at"]), i["doc_id"]))[cancels[key] :]
        for dup in live[1:]:
            ap = c.ap_row(dup["invoice_id"])
            if ap is not None:
                c.add(
                    DUPLICATE_INVOICE,
                    [live[0]["doc_id"], dup["doc_id"]],
                    ap["credit_minor"] - ap["debit_minor"],
                    {live[0]["doc_id"], dup["doc_id"], ap["row_id"]},
                )


def _relief(c: _Ctx, invoice_id: str, amount: int) -> int:
    inv, ap = c.invoices[invoice_id], c.ap_row(invoice_id)
    booked = ap["credit_minor"] - ap["debit_minor"]
    value = Decimal(amount) * Decimal(booked) / Decimal(inv["total_minor"])
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def _check_payments(c: _Ctx) -> None:
    """F2: remittance intent (invoice_refs) vs the AP allocation actually recorded."""
    for pay in c.payments:
        day = local_date(pay["timestamp"], c.tz)
        rows = c.journals.get(f"pay:{pay['payment_id']}", [])
        if not in_period(day, c.start, c.end) or not rows:
            c.out.violations.append(f"payment {pay['doc_id']} outside period or unposted")
            continue
        refs = {ref["invoice_id"]: ref["amount_minor"] for ref in pay["invoice_refs"]}
        if any(i not in c.invoices or c.ap_row(i) is None for i in refs):
            c.out.violations.append(f"payment {pay['doc_id']} references unposted invoice")
            continue
        bank = -_net([r for r in rows if r["account"] == ACC_BANK])
        if bank != c.to_base(pay["amount_minor"], pay["currency"], day):
            c.out.violations.append(f"payment {pay['doc_id']} bank amount mismatch")
        ap_rows = [r for r in rows if r["account"] == ACC_AP]
        actual: dict[str, int] = defaultdict(int)
        for r in ap_rows:
            actual[r["invoice_id"]] += r["debit_minor"] - r["credit_minor"]
        remainder = pay["amount_minor"] - sum(refs.values())
        legit_adv = c.to_base(remainder, pay["currency"], day) if remainder else 0
        adv_rows = [r for r in rows if r["account"] == ACC_ADVANCES]
        stray = {r["row_id"] for r in ap_rows if r["invoice_id"] not in refs}
        if _net(adv_rows) != legit_adv:
            stray |= {r["row_id"] for r in adv_rows}
        shortfalls = {i: _relief(c, i, a) - actual.get(i, 0) for i, a in refs.items()}
        shortfalls = {i: s for i, s in shortfalls.items() if s}
        if stray and not shortfalls:
            c.out.violations.append(f"payment {pay['doc_id']} has unexplained allocation rows")
        for invoice_id, short in shortfalls.items():
            doc = c.invoices[invoice_id]["doc_id"]
            c.add(PAYMENT_ALLOCATION, [pay["doc_id"], doc], short, {pay["doc_id"], doc} | stray)


def audit(ep: dict[str, Any]) -> AuditResult:
    c = _Ctx(ep)
    _check_ledger(c)
    _check_invoices(c)
    _check_duplicates(c)
    _check_payments(c)
    c.out.issues.sort(key=issue_key)
    return c.out
