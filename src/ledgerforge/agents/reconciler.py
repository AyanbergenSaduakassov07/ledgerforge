"""A deterministic baseline that reconciles public documents with posted amounts."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from ledgerforge.contracts.money import FxTable, convert, in_period, local_date, parse_ts
from ledgerforge.contracts.schemas import (
    ACC_ADVANCES,
    ACC_AP,
    DUPLICATE_INVOICE,
    FX_RATE,
    MAX_EVIDENCE,
    MAX_FINDINGS,
    MAX_PAGE,
    PAYMENT_ALLOCATION,
    REPORTING_PERIOD,
    TABLES,
)

# Shallow heuristics an auditor might use instead of a published rule (ablation, ADR-017).
NAIVE_RULES = ("duplicates", "period", "fx", "allocation")


class ReconcilerPolicy:
    """Encodes the published rules. `naive` swaps chosen rules for a common shallow heuristic:
    duplicates: same supplier + total (ignores line items and credit notes);
    period: the printed document date instead of the policy timezone;
    fx: the period-end rate instead of the recognition-date rate;
    allocation: remittance at the payment-date rate instead of proportional AP relief.
    """

    def __init__(self, naive: frozenset[str] | set[str] = frozenset()) -> None:
        unknown = set(naive) - set(NAIVE_RULES)
        if unknown:
            raise ValueError(f"unknown naive rules: {sorted(unknown)}")
        self.naive = frozenset(naive)
        self.name = "reconciler" if not naive else "naive_" + "+".join(sorted(naive))

    def reset(self, observation: dict[str, Any]) -> None:
        self._manifest = observation["manifest"]
        self._timezone = observation["policy"]["timezone_offset"]
        self._base = self._manifest["base_currency"]
        self._exponents = self._manifest.get("currency_exponents")  # None -> contract table
        self._tables = iter(TABLES)
        self._table: str | None = None
        self._rows: dict[str, list[dict[str, Any]]] = {table: [] for table in TABLES}
        self._fx_table: FxTable | None = None  # built once all fx pages are read

    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        cursor = None
        if self._table is not None:
            result = observation.get("result")
            if result is None:
                return self._submit([])
            self._rows[self._table].extend(result["rows"])
            cursor = result["next_cursor"]
        if cursor is None:
            self._table = next(self._tables, None)
        if self._table is None:
            return self._submit(self._findings()[:MAX_FINDINGS])
        if observation["steps_remaining"] <= 1:
            return self._submit([])
        return {
            "tool": "list_records",
            "args": {"table": self._table, "cursor": cursor, "limit": MAX_PAGE},
        }

    def _submit(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "tool": "submit",
            "args": {"episode_id": self._manifest["episode_id"], "findings": findings},
        }

    def _findings(self) -> list[dict[str, Any]]:
        postings = {}
        payment_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in self._rows["ledger"]:
            if row["payment_id"]:
                payment_rows[row["payment_id"]].append(row)
            elif row["invoice_id"] and row["account"] == ACC_AP:
                postings[row["invoice_id"]] = row
        invoices = {
            invoice["invoice_id"]: invoice
            for invoice in sorted(self._rows["invoices"], key=lambda doc: doc["doc_id"])
            if invoice["invoice_id"] in postings
        }
        return [
            *self._invoice_findings(invoices, postings),
            *self._duplicate_findings(invoices, postings),
            *self._payment_findings(invoices, postings, payment_rows),
        ]

    def _invoice_findings(
        self, invoices: dict[str, dict[str, Any]], postings: dict[str, dict[str, Any]]
    ) -> Iterator[dict[str, Any]]:
        fx = self._fx()
        for invoice_id, invoice in invoices.items():
            row = postings[invoice_id]
            docs = [invoice["doc_id"]]
            evidence = [row["row_id"]]
            booked = row["credit_minor"] - row["debit_minor"]
            day = local_date(invoice["issued_at"], self._timezone)
            printed = invoice["issued_at"][:10]
            period_day = printed if "period" in self.naive else day
            start, end = self._manifest["period_start"], self._manifest["period_end"]
            if not in_period(period_day, start, end):
                yield self._finding(
                    REPORTING_PERIOD, docs, booked, evidence, "Issued outside the posted period."
                )
            currency = invoice["currency"]
            rate_day = end if "fx" in self.naive else day
            rate = fx.effective(currency, self._base, rate_day) if currency != self._base else None
            if rate is not None:
                rate_id, rate_value = rate
                expected = convert(
                    invoice["total_minor"], currency, self._base, rate_value, self._exponents
                )
                if expected != booked:
                    yield self._finding(
                        FX_RATE,
                        docs,
                        booked - expected,
                        [*evidence, rate_id],
                        "Posted value differs from the published recognition-date rate.",
                    )

    def _duplicate_findings(
        self, invoices: dict[str, dict[str, Any]], postings: dict[str, dict[str, Any]]
    ) -> Iterator[dict[str, Any]]:
        charges: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
        credits: dict[tuple, int] = defaultdict(int)
        for invoice in invoices.values():
            sign = 1 if invoice["total_minor"] > 0 else -1
            items = tuple(
                sorted(
                    (
                        line["description"],
                        sign * line["quantity"],
                        line["unit_price_minor"],
                        sign * line["amount_minor"],
                    )
                    for line in invoice["line_items"]
                )
            )
            signature = (
                invoice["entity_id"],
                invoice["currency"],
                abs(invoice["total_minor"]),
                () if "duplicates" in self.naive else items,
            )
            if sign == 1:
                charges[signature].append(invoice)
            elif "duplicates" not in self.naive:
                credits[signature] += 1
        for signature, group in charges.items():
            ordered = sorted(group, key=lambda doc: (parse_ts(doc["issued_at"]), doc["doc_id"]))
            outstanding = ordered[credits[signature] :]
            for later in outstanding[1:]:
                row = postings[later["invoice_id"]]
                yield self._finding(
                    DUPLICATE_INVOICE,
                    [outstanding[0]["doc_id"], later["doc_id"]],
                    row["credit_minor"],
                    [row["row_id"]],
                    "Same supplier, currency, amount and line items without an offsetting credit.",
                )

    def _payment_findings(
        self,
        invoices: dict[str, dict[str, Any]],
        postings: dict[str, dict[str, Any]],
        payment_rows: dict[str, list[dict[str, Any]]],
    ) -> Iterator[dict[str, Any]]:
        for payment in sorted(self._rows["payments"], key=lambda doc: doc["doc_id"]):
            refs = {ref["invoice_id"]: ref["amount_minor"] for ref in payment["invoice_refs"]}
            actual: dict[str, int] = defaultdict(int)
            advances, stray = [], []
            for row in payment_rows.get(payment["payment_id"], []):
                if row["account"] == ACC_AP:
                    actual[row["invoice_id"]] += row["debit_minor"] - row["credit_minor"]
                    if row["invoice_id"] not in refs:
                        stray.append(row["row_id"])
                elif row["account"] == ACC_ADVANCES:
                    advances.append(row)
            posted_advance = sum(row["debit_minor"] - row["credit_minor"] for row in advances)
            if posted_advance != payment["amount_minor"] - sum(refs.values()):
                stray.extend(row["row_id"] for row in advances)
            naive = "allocation" in self.naive
            if not stray and not naive:
                continue
            for invoice_id, amount in sorted(refs.items()):
                invoice = invoices.get(invoice_id)
                if not invoice or not invoice["total_minor"]:
                    continue
                posting = postings[invoice_id]
                booked = posting["credit_minor"] - posting["debit_minor"]
                expected = (
                    self._at_payment_rate(payment, amount)
                    if naive
                    else round(Decimal(amount) * booked / invoice["total_minor"])
                )
                shortfall = expected - actual[invoice_id]
                if shortfall:
                    yield self._finding(
                        PAYMENT_ALLOCATION,
                        [payment["doc_id"], invoice["doc_id"]],
                        shortfall,
                        sorted(stray),
                        "Remittance references differ from the posted payable allocations.",
                    )

    def _at_payment_rate(self, payment: dict[str, Any], amount: int) -> int:
        if payment["currency"] == self._base:
            return amount
        day = local_date(payment["timestamp"], self._timezone)
        rate = self._fx().effective(payment["currency"], self._base, day)
        if rate is None:  # the generator always publishes a covering rate; fail loudly if not
            raise ValueError(f"no FX rate for {payment['currency']} on or before {day}")
        return convert(amount, payment["currency"], self._base, rate[1], self._exponents)

    def _fx(self) -> FxTable:
        if self._fx_table is None:
            self._fx_table = FxTable(self._rows["fx"])
        return self._fx_table

    def _finding(
        self, kind: str, docs: list[str], amount: int, rows: list[str], explanation: str
    ) -> dict[str, Any]:
        return {
            "type": kind,
            "affected_ids": sorted(docs),
            "claimed_amount_minor": abs(amount),
            "currency": self._base,
            "evidence_ids": [*sorted(docs), *rows][:MAX_EVIDENCE],
            "explanation": explanation,
        }
