"""Run a policy through the environment, log every step, and replay a log deterministically."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from ledgerforge.contracts.schemas import MAX_STEPS, AgentPolicy
from ledgerforge.env.env import AuditEnv


def run_episode(
    env: AuditEnv, policy: AgentPolicy, seed: int, config: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    obs, info = env.reset(seed, config)
    policy.reset(obs)
    records: list[dict[str, Any]] = []
    for step in range(1, MAX_STEPS + 1):
        action = policy.act(obs)
        obs, reward, terminated, truncated, step_info = env.step(action)
        records.append(
            {
                "episode_id": info["episode_id"],
                "seed": seed,
                "config": config,
                "policy": policy.name,
                "step": step,
                "action": deepcopy(action),
                "observation": deepcopy(obs),
                "reward": reward,
                "terminated": terminated,
                "truncated": truncated,
                "report": step_info.get("report"),
            }
        )
        if terminated or truncated:
            break
    return records


def replay(env: AuditEnv, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Re-execute logged actions on a fresh reset; return the regenerated records."""
    first = records[0]
    _, info = env.reset(first["seed"], first["config"])
    out = []
    for rec in records:
        obs, reward, terminated, truncated, step_info = env.step(rec["action"])
        out.append(
            {
                **rec,
                "episode_id": info["episode_id"],
                "observation": obs,
                "reward": reward,
                "terminated": terminated,
                "truncated": truncated,
                "report": step_info.get("report"),
            }
        )
    return out


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
