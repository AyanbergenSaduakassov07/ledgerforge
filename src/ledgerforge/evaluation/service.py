"""Evaluator process. Owns generation and private truth; speaks JSON lines on stdin/stdout.

The agent-side environment only ever receives the public episode and a score (train mode) or an
acknowledgement (eval mode). Truth never crosses this boundary.

Requests:
  {"cmd": "reset", "seed": int, "config": {...}}            -> {"public": {...}}
  {"cmd": "score", "submission": any, "inspection_steps": n} -> {"reward": r, "report": {...}}
                                                                 (eval mode: {"accepted": true})
  {"cmd": "report"}                                          -> {"reports": [...]}  (end of run)
"""

from __future__ import annotations

import json
import sys
from typing import Any

from ledgerforge.contracts.schemas import ScenarioConfig
from ledgerforge.evaluation.matcher import score
from ledgerforge.sim.episode import GenerationFailed, generate_episode

MODES = ("train", "eval")


class Evaluator:
    def __init__(self, mode: str = "train") -> None:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        self.mode = mode
        self.reports: list[dict[str, Any]] = []
        self._truth = None
        self._aliases: dict[str, str] = {}
        self._episode_id = ""

    def handle(self, req: dict[str, Any]) -> dict[str, Any]:
        cmd = req.get("cmd")
        if cmd == "reset":
            public, truth = generate_episode(
                int(req["seed"]), ScenarioConfig.from_dict(req.get("config"))
            )
            self._truth, self._episode_id = list(truth.issues), truth.episode_id
            self._aliases = {i["invoice_id"]: i["doc_id"] for i in public.invoices}
            self._aliases |= {p["payment_id"]: p["doc_id"] for p in public.payments}
            return {"public": public.to_dict()}
        if cmd == "score":
            if self._truth is None:
                return {"error": "no active episode"}
            report = score(
                req.get("submission"),
                self._episode_id,
                self._truth,
                self._aliases,
                int(req["inspection_steps"]),
            ).to_dict()
            self._truth = None  # one scored submission per episode
            self.reports.append(report)
            if self.mode == "eval":
                return {"accepted": True}
            return {"reward": report["reward"], "report": report}
        if cmd == "report":
            return {"reports": self.reports}
        return {"error": "unknown command"}


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "train"
    ev = Evaluator(mode)
    for line in sys.stdin:
        try:
            resp = ev.handle(json.loads(line))
        except (ValueError, KeyError, TypeError, GenerationFailed) as e:
            resp = {"error": f"{type(e).__name__}: {e}"}  # config errors only; no truth inside
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
