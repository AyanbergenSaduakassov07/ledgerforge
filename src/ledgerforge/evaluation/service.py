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
from ledgerforge.sim.secret import SECRET_ENV, secret_key

MODES = ("train", "eval")


class Evaluator:
    def __init__(self, mode: str = "train") -> None:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        self.mode = mode
        if mode == "eval" and not secret_key():
            # stderr is the operator's console; it never reaches agent observations.
            print(
                f"ledgerforge: WARNING: eval mode without {SECRET_ENV}; episodes are "
                "reproducible from the open generator and the seed",
                file=sys.stderr,
            )
        self.reports: list[dict[str, Any]] = []
        self._truth = None
        self._aliases: dict[str, str] = {}
        self._episode_id = ""

    def handle(self, req: Any) -> dict[str, Any]:
        if not isinstance(req, dict):
            return {"error": "request must be a JSON object"}
        cmd = req.get("cmd")
        if cmd == "reset":
            config = req.get("config")
            if config is not None and not isinstance(config, dict):
                return {"error": "config must be an object or null"}
            public, truth = generate_episode(
                _strict_int(req.get("seed"), "seed"), ScenarioConfig.from_dict(config)
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
                _strict_int(req.get("inspection_steps"), "inspection_steps"),
            ).to_dict()
            self._truth = None  # one scored submission per episode
            self.reports.append(report)
            if self.mode == "eval":
                return {"accepted": True}
            return {"reward": report["reward"], "report": report}
        if cmd == "report":
            return {"reports": self.reports}
        return {"error": "unknown command"}


def _strict_int(value: Any, name: str) -> int:
    # json accepts Infinity/NaN and floats; int() of those crashes or silently truncates
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer")
    return value


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "train"
    ev = Evaluator(mode)
    for line in sys.stdin:
        try:
            resp = ev.handle(json.loads(line))
        except (ValueError, KeyError, TypeError, OverflowError, GenerationFailed) as e:
            resp = {"error": f"{type(e).__name__}: {e}"}  # config errors only; no truth inside
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
