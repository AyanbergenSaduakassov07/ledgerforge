"""Gym-style audit environment. Holds only public data; truth lives in the evaluator process.

reset(seed, config) -> (observation, info)
step(action)        -> (observation, reward, terminated, truncated, info)
action = {"tool": <one of TOOLS>, "args": {...}}; submit args = {"episode_id", "findings"}
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from typing import Any

from ledgerforge.contracts.schemas import (
    EPISODE_TIME_LIMIT_S,
    MAX_PAGE,
    MAX_STEPS,
    TABLE_KEYS,
    TABLES,
    TOOLS,
    fx_id,
)
from ledgerforge.env.calculator import CalcError, calculate

TASK = (
    "Audit this company's reporting period. Find duplicate invoices, payment allocation "
    "errors, wrong FX dates/rates and wrong reporting periods. Submit findings with canonical "
    "doc ids, the base-currency ledger impact, and evidence ids (doc ids, ledger row ids, "
    "fx ids 'date:SRC:TGT')."
)
_EVALUATOR_TIMEOUT_S = 10.0


class ToolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


class EvaluatorClient:
    """Runs the evaluator in a separate OS process (no shared memory with the agent)."""

    def __init__(self, mode: str = "train") -> None:
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "ledgerforge.evaluation.service", mode],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        self._worker = ThreadPoolExecutor(max_workers=1)
        self._closed = False

    def call(self, request: dict[str, Any]) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("evaluator connection closed")
        pending = self._worker.submit(self._exchange, json.dumps(request) + "\n")
        try:
            resp = pending.result(timeout=_EVALUATOR_TIMEOUT_S)
        except TimeoutError:
            self._proc.kill()
            self.close()
            raise RuntimeError("evaluator request timed out") from None
        except (OSError, EOFError, ValueError):
            self.close()
            raise RuntimeError("evaluator connection lost") from None
        if "error" in resp:
            raise RuntimeError(f"evaluator: {resp['error']}")
        return resp

    def _exchange(self, line: str) -> dict[str, Any]:
        assert self._proc.stdin is not None and self._proc.stdout is not None
        self._proc.stdin.write(line)
        self._proc.stdin.flush()
        reply = self._proc.stdout.readline()
        if not reply.endswith("\n"):
            raise EOFError
        response = json.loads(reply)
        if not isinstance(response, dict):
            raise ValueError("expected an evaluator response object")
        return response

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._worker.shutdown()
        assert self._proc.stdin is not None and self._proc.stdout is not None
        with suppress(OSError):
            self._proc.stdin.close()
        try:
            self._proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()
        finally:
            self._proc.stdout.close()


class AuditEnv:
    def __init__(
        self,
        mode: str = "train",
        evaluator: EvaluatorClient | None = None,
        time_limit_s: float = EPISODE_TIME_LIMIT_S,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.mode = mode
        self.evaluator = evaluator or EvaluatorClient(mode)
        self.time_limit_s = time_limit_s
        self._clock = clock
        self._data: dict[str, Any] = {}
        self._index: dict[str, dict[str, dict[str, Any]]] = {}
        self._docs: dict[str, dict[str, Any]] = {}
        self.steps = 0
        self.done = True

    # --- lifecycle ---------------------------------------------------------------------------
    def reset(
        self,
        seed: int,
        config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        self._data = self.evaluator.call({"cmd": "reset", "seed": seed, "config": config})["public"]
        self._index = {t: {r[TABLE_KEYS[t]]: r for r in self._data[t]} for t in TABLES[:3]}
        self._index["fx"] = {
            fx_id(r["date"], r["source_currency"], r["target_currency"]): r
            for r in self._data["fx"]
        }
        self._docs = {d["doc_id"]: d for d in self._data["invoices"] + self._data["payments"]}
        self.steps, self.done, self._t0 = 0, False, self._clock()
        m = self._data["manifest"]
        obs = {
            "task": TASK,
            "manifest": m,
            "policy": self._data["policy"],
            "tables": {t: {"key": TABLE_KEYS[t], "rows": len(self._data[t])} for t in TABLES},
            "actions": list(TOOLS),
            "steps_remaining": MAX_STEPS,
        }
        return obs, {"episode_id": m["episode_id"]}

    def close(self) -> None:
        self.done = True
        self.evaluator.close()

    # --- step --------------------------------------------------------------------------------
    def step(self, action: Any) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        if self.done:
            return self._obs(error=("episode_over", "call reset() first")), 0.0, True, False, {}
        if self._clock() - self._t0 >= self.time_limit_s:
            return self._finish(None, terminated=False)
        self.steps += 1
        tool = action.get("tool") if isinstance(action, dict) else None
        args = action.get("args", {}) if isinstance(action, dict) else {}
        if tool == "submit":
            return self._finish(args, terminated=True)  # args IS the submission payload
        try:
            if not isinstance(args, dict):
                raise ToolError("bad_args", "args must be an object")
            result = self._dispatch(tool, args)
            obs = self._obs(result=result)
        except ToolError as e:
            obs = self._obs(error=(e.code, e.message))
        if self.steps >= MAX_STEPS or self._clock() - self._t0 >= self.time_limit_s:
            return self._finish(None, terminated=False)
        return obs, 0.0, False, False, {}

    def _finish(
        self, submission: Any, terminated: bool
    ) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        inspection = self.steps - 1 if terminated else self.steps
        if submission is None and not terminated:  # truncated: score an empty submission
            submission = {"episode_id": self._data["manifest"]["episode_id"], "findings": []}
        self.done = True
        resp = self.evaluator.call(
            {"cmd": "score", "submission": submission, "inspection_steps": inspection}
        )
        reward = float(resp["reward"]) if self.mode == "train" else 0.0
        obs = self._obs(result={"accepted": True})
        info = {"report": resp["report"]} if self.mode == "train" else {}
        return obs, reward, terminated, not terminated, info

    def _obs(self, result: Any = None, error: tuple[str, str] | None = None) -> dict[str, Any]:
        obs: dict[str, Any] = {"steps_remaining": MAX_STEPS - self.steps}
        if error:
            obs["error"] = {"code": error[0], "message": error[1]}
        else:
            obs["result"] = result
        return obs

    # --- tools -------------------------------------------------------------------------------
    def _dispatch(self, tool: Any, args: dict[str, Any]) -> Any:
        if tool == "list_records":
            return self._list(args.get("table"), args.get("cursor"), args.get("limit", MAX_PAGE))
        if tool == "get_record":
            table, key = args.get("table"), args.get("id")
            self._table(table)
            if not isinstance(key, str) or key not in self._index[table]:
                raise ToolError("not_found", f"no {table} record with that id")
            return self._index[table][key]
        if tool == "get_document":
            doc_id = args.get("doc_id")
            if not isinstance(doc_id, str) or not doc_id.strip():
                raise ToolError("bad_args", "doc_id must be a non-empty string")
            if doc_id in ("manifest", "policy"):
                return self._data[doc_id]
            if doc_id not in self._docs:
                raise ToolError("not_found", "no document with that id")
            return self._docs[doc_id]
        if tool == "calculator":
            try:
                return {"value": calculate(args.get("expression"))}
            except CalcError as e:
                raise ToolError("calc_error", str(e)) from e
        raise ToolError("unknown_tool", f"tool must be one of {list(TOOLS)}")

    def _table(self, table: Any) -> None:
        if table not in TABLES:
            raise ToolError("bad_table", f"table must be one of {list(TABLES)}")

    def _list(self, table: Any, cursor: Any, limit: Any) -> dict[str, Any]:
        self._table(table)
        rows = self._data[table]
        try:
            start = int(cursor) if cursor is not None else 0
        except (TypeError, ValueError) as e:
            raise ToolError("bad_cursor", "cursor must come from a previous page") from e
        if not 0 <= start <= len(rows):
            raise ToolError("bad_cursor", "cursor out of range")
        if type(limit) is not int or not 1 <= limit <= MAX_PAGE:
            raise ToolError("bad_limit", f"limit must be an integer 1..{MAX_PAGE}")
        end = min(start + limit, len(rows))
        return {"rows": rows[start:end], "next_cursor": str(end) if end < len(rows) else None}
