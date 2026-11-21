"""A false-positive control that makes unverified claims about visible documents."""

from __future__ import annotations

from typing import Any

from ledgerforge.contracts.schemas import (
    DUPLICATE_INVOICE,
    FX_RATE,
    MAX_FINDINGS,
    MAX_PAGE,
    PAYMENT_ALLOCATION,
    REPORTING_PERIOD,
)


class FlagAllPolicy:
    name = "flag_all"

    def reset(self, observation: dict[str, Any]) -> None:
        self._episode_id = observation["manifest"]["episode_id"]
        self._currency = observation["manifest"]["base_currency"]
        self._invoices: list[dict[str, Any]] | None = None

    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        if "manifest" in observation:
            return {"tool": "list_records", "args": {"table": "invoices", "limit": MAX_PAGE}}
        if self._invoices is None:
            self._invoices = observation["result"]["rows"]
            return {"tool": "list_records", "args": {"table": "payments", "limit": MAX_PAGE}}
        findings = self._flags(observation["result"]["rows"])
        return {"tool": "submit", "args": {"episode_id": self._episode_id, "findings": findings}}

    def _flags(self, payments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        assert self._invoices is not None
        invoices = self._invoices
        by_id = {invoice["invoice_id"]: invoice for invoice in invoices}
        allocation_flags = []
        for payment in payments:
            for ref in payment["invoice_refs"]:
                invoice = by_id.get(ref["invoice_id"])
                if invoice:
                    allocation_flags.append(
                        self._flag(
                            PAYMENT_ALLOCATION,
                            [payment["doc_id"], invoice["doc_id"]],
                            ref["amount_minor"],
                        )
                    )
        findings = []
        for index, invoice in enumerate(invoices):
            doc_id, amount = invoice["doc_id"], invoice["total_minor"]
            findings.extend(
                self._flag(kind, [doc_id], amount) for kind in (FX_RATE, REPORTING_PERIOD)
            )
            if index + 1 < len(invoices):
                other = invoices[index + 1]
                findings.append(
                    self._flag(DUPLICATE_INVOICE, [doc_id, other["doc_id"]], other["total_minor"])
                )
            if index < len(allocation_flags):
                findings.append(allocation_flags[index])
            if len(findings) >= MAX_FINDINGS:
                break
        return findings[:MAX_FINDINGS]

    def _flag(self, kind: str, docs: list[str], amount: int) -> dict[str, Any]:
        return {
            "type": kind,
            "affected_ids": docs,
            "claimed_amount_minor": abs(amount),
            "currency": self._currency,
            "evidence_ids": docs.copy(),
            "explanation": "Automatically flagged without checking the ledger.",
        }
