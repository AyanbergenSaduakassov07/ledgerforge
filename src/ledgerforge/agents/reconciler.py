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


class ReconcilerPolicy:
    name = "reconciler"

    def reset(self, observation: dict[str, Any]) -> None:
        self._manifest = observation["manifest"]
        self._timezone = observation["policy"]["timezone_offset"]
        self._base = self._manifest["base_currency"]
        self._tables = iter(TABLES)
        self._table: str | None = None
        self._rows: dict[str, list[dict[str, Any]]] = {table: [] for table in TABLES}

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
        fx = FxTable(self._rows["fx"])
        for invoice_id, invoice in invoices.items():
            row = postings[invoice_id]
            docs = [invoice["doc_id"]]
            evidence = [row["row_id"]]
            booked = row["credit_minor"] - row["debit_minor"]
            day = local_date(invoice["issued_at"], self._timezone)
            if not in_period(day, self._manifest["period_start"], self._manifest["period_end"]):
                yield self._finding(
                    REPORTING_PERIOD, docs, booked, evidence, "Issued outside the posted period."
                )
            currency = invoice["currency"]
            rate = fx.effective(currency, self._base, day) if currency != self._base else None
            if rate is not None:
                rate_id, rate_value = rate
                expected = convert(invoice["total_minor"], currency, self._base, rate_value)
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
                items,
            )
            if sign == 1:
                charges[signature].append(invoice)
            else:
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
            # shortcut: checks base-currency remittances only, add FX for foreign allocation faults.
            if payment["currency"] != self._base:
                continue
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
            if not stray:
                continue
            for invoice_id, amount in sorted(refs.items()):
                invoice = invoices.get(invoice_id)
                if not invoice or not invoice["total_minor"]:
                    continue
                posting = postings[invoice_id]
                booked = posting["credit_minor"] - posting["debit_minor"]
                shortfall = (
                    round(Decimal(amount) * booked / invoice["total_minor"]) - actual[invoice_id]
                )
                if shortfall:
                    yield self._finding(
                        PAYMENT_ALLOCATION,
                        [payment["doc_id"], invoice["doc_id"]],
                        shortfall,
                        sorted(stray),
                        "Remittance references differ from the posted payable allocations.",
                    )

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
