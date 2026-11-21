"""A seeded control that samples public record pages and submits no findings."""

from __future__ import annotations

from random import Random
from typing import Any

from ledgerforge.contracts.schemas import MAX_PAGE, TABLES

_INSPECTION_BUDGET = 8


class RandomExplorerPolicy:
    name = "random_explorer"

    def __init__(self, seed: int = 0) -> None:
        self._seed = seed

    def reset(self, observation: dict[str, Any]) -> None:
        self._episode_id = observation["manifest"]["episode_id"]
        self._rng = Random(f"{self._seed}:{self._episode_id}")
        self._cursors: dict[str, str | None] = dict.fromkeys(TABLES)
        self._table: str | None = None
        self._inspections = 0

    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        if self._table is not None:
            cursor = observation.get("result", {}).get("next_cursor")
            if cursor is None:
                del self._cursors[self._table]
            else:
                self._cursors[self._table] = cursor
        if self._inspections >= _INSPECTION_BUDGET or not self._cursors:
            return {"tool": "submit", "args": {"episode_id": self._episode_id, "findings": []}}
        self._table = self._rng.choice(tuple(self._cursors))
        self._inspections += 1
        return {
            "tool": "list_records",
            "args": {"table": self._table, "limit": MAX_PAGE, "cursor": self._cursors[self._table]},
        }
