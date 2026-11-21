"""Submission structure validation and finding normalization (published, section 05)."""

from __future__ import annotations

import re
from typing import Any

from ledgerforge.contracts.schemas import (
    ERROR_TYPES,
    MAX_AFFECTED,
    MAX_EVIDENCE,
    MAX_EXPLANATION,
    MAX_FINDINGS,
)

FINDING_KEYS = {
    "type",
    "affected_ids",
    "claimed_amount_minor",
    "currency",
    "evidence_ids",
    "explanation",
}
_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")
_MAX_ID_CHARS = 64


class MalformedSubmission(ValueError):
    """Wrong structure: episode terminates with reward -1 (official)."""


def _id_list(value: Any, name: str, max_len: int, allow_empty: bool) -> list[str]:
    if not isinstance(value, list):
        raise MalformedSubmission(f"{name} must be a list")
    if len(value) > max_len or (not value and not allow_empty):
        raise MalformedSubmission(f"{name} must have {0 if allow_empty else 1}..{max_len} items")
    for item in value:
        if not isinstance(item, str) or not item.strip() or len(item) > _MAX_ID_CHARS:
            raise MalformedSubmission(f"{name} items must be non-empty strings <= 64 chars")
    return value


def validate_submission(payload: Any, episode_id: str) -> list[dict[str, Any]]:
    """Return the raw findings list or raise MalformedSubmission.

    Rules: object with exactly {episode_id, findings}; episode_id must equal the current episode;
    <= 30 findings; each finding has exactly the six official keys; type is one of the four types;
    affected_ids 1..10 strings; claimed_amount_minor is an int (bool rejected); currency is three
    letters; evidence_ids 0..10 strings; explanation is a string <= 1000 chars.
    """
    if not isinstance(payload, dict) or set(payload) != {"episode_id", "findings"}:
        raise MalformedSubmission("submission must be an object with episode_id and findings")
    if payload["episode_id"] != episode_id:
        raise MalformedSubmission("episode_id does not match the current episode")
    findings = payload["findings"]
    if not isinstance(findings, list) or len(findings) > MAX_FINDINGS:
        raise MalformedSubmission(f"findings must be a list of at most {MAX_FINDINGS}")
    for f in findings:
        if not isinstance(f, dict) or set(f) != FINDING_KEYS:
            raise MalformedSubmission(f"each finding must have exactly {sorted(FINDING_KEYS)}")
        if not isinstance(f["type"], str) or f["type"].strip().lower() not in ERROR_TYPES:
            raise MalformedSubmission(f"type must be one of {ERROR_TYPES}")
        _id_list(f["affected_ids"], "affected_ids", MAX_AFFECTED, allow_empty=False)
        _id_list(f["evidence_ids"], "evidence_ids", MAX_EVIDENCE, allow_empty=True)
        amount = f["claimed_amount_minor"]
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise MalformedSubmission("claimed_amount_minor must be an integer")
        if not isinstance(f["currency"], str) or not _CURRENCY_RE.match(f["currency"].strip()):
            raise MalformedSubmission("currency must be a 3-letter code")
        if not isinstance(f["explanation"], str) or len(f["explanation"]) > MAX_EXPLANATION:
            raise MalformedSubmission(f"explanation must be a string <= {MAX_EXPLANATION} chars")
    return findings


def normalize_finding(f: dict[str, Any], aliases: dict[str, str]) -> dict[str, Any]:
    """Canonical form used by the matcher.

    - type: stripped, lower-case.  currency: stripped, upper-case.
    - ids: stripped; business ids (invoice_id, payment_id) map to their doc_id via `aliases`.
    - affected_ids / evidence_ids become sets (order and repeats do not matter).
    - claimed amount compared by absolute value (sign conventions are not tested).
    The explanation is ignored by the matcher.
    """

    def canon(ids: list[str]) -> frozenset[str]:
        return frozenset(aliases.get(i.strip(), i.strip()) for i in ids)

    return {
        "type": f["type"].strip().lower(),
        "affected_ids": canon(f["affected_ids"]),
        "claimed_amount_minor": abs(f["claimed_amount_minor"]),
        "currency": f["currency"].strip().upper(),
        "evidence_ids": canon(f["evidence_ids"]),
    }
