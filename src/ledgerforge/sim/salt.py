"""id_salt metamorphic transform: rename every public id with a salted digit permutation.

A per-salt bijection on digits keeps ids unique and keeps their shape (prefixes, separators,
duplicate-variant suffixes), so the renamed episode is an equivalent audit problem.
fx ids are dates and stay unchanged.
"""

from __future__ import annotations

import random
from typing import Any

from ledgerforge.contracts.schemas import PublicEpisode

DIGITS = "0123456789"
ROW_ID_FIELDS = ("row_id", "entity_id", "invoice_id", "payment_id")
DOC_ID_FIELDS = ("doc_id", "entity_id", "invoice_id", "payment_id")


def digit_table(salt: str) -> dict[int, int]:
    r = random.Random(f"ledgerforge:id_salt:{salt}")
    perm = list(DIGITS)
    while any(a == b for a, b in zip(perm, DIGITS, strict=True)):  # derangement: every id changes
        r.shuffle(perm)
    return str.maketrans(DIGITS, "".join(perm))


def _rename(row: dict[str, Any], fields: tuple[str, ...], table: dict[int, int]) -> dict[str, Any]:
    out = dict(row)
    for f in fields:
        if out.get(f):
            out[f] = out[f].translate(table)
    if "invoice_refs" in out:
        out["invoice_refs"] = [
            {**ref, "invoice_id": ref["invoice_id"].translate(table)} for ref in out["invoice_refs"]
        ]
    return out


def salt_public(public: PublicEpisode, salt: str) -> tuple[PublicEpisode, dict[str, str]]:
    """Return the renamed episode and the old -> new map for every renamed id."""
    t = digit_table(salt)
    ids = {r[f] for r in public.ledger for f in ROW_ID_FIELDS if r.get(f)}
    ids |= {d[f] for d in public.invoices + public.payments for f in DOC_ID_FIELDS if d.get(f)}
    ids.add(public.manifest["episode_id"])
    mapping = {old: old.translate(t) for old in ids}
    manifest = {**public.manifest, "episode_id": mapping[public.manifest["episode_id"]]}
    return (
        PublicEpisode(
            manifest,
            public.policy,
            [_rename(r, ROW_ID_FIELDS, t) for r in public.ledger],
            [_rename(d, DOC_ID_FIELDS, t) for d in public.invoices],
            [_rename(d, DOC_ID_FIELDS, t) for d in public.payments],
            public.fx,
        ),
        mapping,
    )


def salt_spec(spec: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    return {
        **spec,
        "affected_ids": [mapping.get(i, i) for i in spec["affected_ids"]],
        "allowed_evidence_sets": [
            [mapping.get(i, i) for i in ev] for ev in spec["allowed_evidence_sets"]
        ],
    }
