"""Write an episode to disk. Public and private files go to SEPARATE directories.

CSV: an empty field means null; integers are plain digits. JSONL: one record per line.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from ledgerforge.contracts.schemas import (
    FX_FIELDS,
    LEDGER_FIELDS,
    PrivateTruthBundle,
    PublicEpisode,
)

INT_FIELDS = {"debit_minor", "credit_minor"}


def _csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: "" if row[k] is None else row[k] for k in fields})


def _jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), "utf-8")


def _json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", "utf-8")


def write_public(ep: PublicEpisode, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    _json(out / "manifest.json", ep.manifest)
    _json(out / "policy.json", ep.policy)
    _csv(out / "ledger.csv", LEDGER_FIELDS, ep.ledger)
    _jsonl(out / "invoices.jsonl", ep.invoices)
    _jsonl(out / "payments.jsonl", ep.payments)
    _csv(out / "fx.csv", FX_FIELDS, ep.fx)


def write_private(truth: PrivateTruthBundle, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    _json(out / "truth.json", truth.truth_dict())
    _json(out / "provenance.json", truth.provenance)


def read_public(src: Path) -> PublicEpisode:
    def rows(name: str) -> list[dict[str, Any]]:
        with (src / name).open(encoding="utf-8", newline="") as fh:
            return [
                {k: (None if v == "" else int(v) if k in INT_FIELDS else v) for k, v in r.items()}
                for r in csv.DictReader(fh)
            ]

    def lines(name: str) -> list[dict[str, Any]]:
        return [json.loads(x) for x in (src / name).read_text("utf-8").splitlines() if x]

    return PublicEpisode(
        json.loads((src / "manifest.json").read_text("utf-8")),
        json.loads((src / "policy.json").read_text("utf-8")),
        rows("ledger.csv"),
        lines("invoices.jsonl"),
        lines("payments.jsonl"),
        rows("fx.csv"),
    )
