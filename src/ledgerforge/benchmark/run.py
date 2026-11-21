"""Trusted benchmark runner for the open splits and a local closed-eval mirror."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import fmean
from time import perf_counter
from typing import Any, TextIO

from ledgerforge.agents.flag_all import FlagAllPolicy
from ledgerforge.agents.oracle import OraclePolicy
from ledgerforge.agents.random_explorer import RandomExplorerPolicy
from ledgerforge.agents.reconciler import ReconcilerPolicy
from ledgerforge.benchmark.trajectory import replay, run_episode
from ledgerforge.contracts.schemas import (
    DIFFICULTIES,
    ERROR_TYPES,
    GENERATOR_VERSION,
    INDUSTRIES,
    INTERACTIONS,
    SCHEMA_VERSION,
    TABLE_KEYS,
    ScenarioConfig,
)
from ledgerforge.env.env import AuditEnv
from ledgerforge.sim.episode import generate_episode
from ledgerforge.sim.salt import salt_public

Case = dict[str, Any]
_SCORE_METRICS = ("precision", "recall", "f1", "reward", "inspection_steps")
_TRAJECTORY_FIELDS = (
    "episode_id",
    "step",
    "action",
    "observation",
    "reward",
    "terminated",
    "truncated",
)


def _mirror_cases() -> list[Case]:
    currencies = ("KZT", "USD", "EUR")
    cases = []
    for index in range(20):
        config: dict[str, Any] = {
            "industry": INDUSTRIES[index % len(INDUSTRIES)],
            "difficulty": DIFFICULTIES[index % len(DIFFICULTIES)],
            "base_currency": currencies[index % len(currencies)],
        }
        if 5 <= index < 10:
            config["interactions"] = {INTERACTIONS[index % len(INTERACTIONS)]: 1}
        elif index >= 10:
            config["faults"] = {ERROR_TYPES[index % len(ERROR_TYPES)]: 1 + index % 2}
        cases.append({"seed": 3000 + index, "config": config})
    return cases


def _write_trajectory(stream: TextIO, split: str, records: list[dict[str, Any]]) -> None:
    for record in records:
        row = {field: record[field] for field in _TRAJECTORY_FIELDS}
        row.update(split=split, policy=record["policy"])
        stream.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def _run_split(split: str, cases: list[Case], stream: TextIO) -> dict[str, Any]:
    env = AuditEnv("eval" if split == "mirror" else "train")
    runs = []
    try:
        for case in cases:
            seed, config = case["seed"], case["config"]
            _, truth = generate_episode(seed, ScenarioConfig.from_dict(config))
            policies = (
                RandomExplorerPolicy(),
                ReconcilerPolicy(),
                FlagAllPolicy(),
                OraclePolicy(truth),
            )
            for policy in policies:
                start = perf_counter()
                records = run_episode(env, policy, seed, config)
                elapsed = perf_counter() - start
                final = records[-1]
                runs.append(
                    {
                        "policy": policy.name,
                        "seed": seed,
                        "episode_id": final["episode_id"],
                        "steps": final["step"],
                        "runtime_seconds": elapsed,
                    }
                )
                if policy.name != OraclePolicy.name:
                    _write_trajectory(stream, split, records)
        reports = env.evaluator.call({"cmd": "report"})["reports"]
    finally:
        env.close()
    return _summarize(runs, reports)


def _summarize(runs: list[dict[str, Any]], reports: list[dict[str, Any]]) -> dict[str, Any]:
    policies: dict[str, list[dict[str, Any]]] = {}
    fields = ("valid", "tp", "fp", "fn", *_SCORE_METRICS)
    for run, report in zip(runs, reports, strict=True):
        if run["episode_id"] != report["episode_id"]:
            raise RuntimeError("evaluator report belongs to a different benchmark episode")
        row = {key: value for key, value in run.items() if key != "policy"}
        row.update({field: report[field] for field in fields})
        policies.setdefault(run["policy"], []).append(row)
    return {
        policy: {
            "runs": rows,
            "means": {
                field: fmean(row[field] for row in rows)
                for field in (*_SCORE_METRICS, "steps", "runtime_seconds")
            },
        }
        for policy, rows in policies.items()
    }


def _finding_keys(records: list[dict[str, Any]], ids: dict[str, str]) -> list[tuple]:
    findings = records[-1]["action"]["args"]["findings"]
    return sorted(
        (
            item["type"],
            tuple(sorted(ids.get(i, i) for i in item["affected_ids"])),
            item["claimed_amount_minor"],
            item["currency"],
            tuple(sorted(ids.get(i, i) for i in item["evidence_ids"])),
        )
        for item in findings
    )


def _check_pair(env: AuditEnv, case: Case) -> dict[str, Any]:
    seed, config = case["seed"], case["config"]
    salt = f"mirror-{seed}"
    transformed = {**config, "id_salt": salt, "order_salt": salt}
    public, truth = generate_episode(seed, ScenarioConfig.from_dict(config))
    salted_public, salted_truth = generate_episode(seed, ScenarioConfig.from_dict(transformed))
    renamed, mapping = salt_public(public, salt)
    base = run_episode(env, OraclePolicy(truth), seed, config)
    changed = run_episode(env, OraclePolicy(salted_truth), seed, transformed)
    reconciler = ReconcilerPolicy()
    public_runs = [run_episode(env, reconciler, seed, params) for params in (config, transformed)]
    ledgers_reordered = [row["row_id"] for row in renamed.ledger] != [
        row["row_id"] for row in salted_public.ledger
    ]
    tables_equivalent = all(
        {row[key]: row for row in getattr(renamed, table)}
        == {row[key]: row for row in getattr(salted_public, table)}
        for table, key in TABLE_KEYS.items()
        if table != "fx"
    )
    return {
        "seed": seed,
        "salt": salt,
        "checks": {
            "ids_changed": all(old != new for old, new in mapping.items()),
            "order_changed": ledgers_reordered,
            "public_records_equivalent": (
                tables_equivalent
                and renamed.fx == salted_public.fx
                and renamed.manifest == salted_public.manifest
                and renamed.policy == salted_public.policy
            ),
            "findings_equivalent": _finding_keys(base, mapping) == _finding_keys(changed, {}),
            "reward_identical": base[-1]["reward"] == changed[-1]["reward"] == 1.0,
            "replay_identical": all(
                replay(env, trajectory) == trajectory
                for trajectory in (base, changed, *public_runs)
            ),
        },
    }


def _summary_markdown(results: dict[str, Any], passed: int, pairs: int) -> str:
    lines = [
        "# LedgerForge benchmark",
        "",
        "Each metric is the mean across episodes. Runtime covers reset through termination.",
        "Mirror policies ran in eval mode. The trusted runner collected scores after the split.",
        "Paired oracle and reconciler runs were replayed in memory. "
        "Trajectories contain public-policy actions.",
        "",
        "| Split | Policy | Episodes | Precision | Recall | F1 | Reward | "
        "Inspection steps | Runtime (s) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for split, policies in results.items():
        for policy, data in policies.items():
            m = data["means"]
            lines.append(
                f"| {split} | {policy} | {len(data['runs'])} | {m['precision']:.3f} "
                f"| {m['recall']:.3f} | {m['f1']:.3f} | {m['reward']:.3f} "
                f"| {m['inspection_steps']:.2f} | {m['runtime_seconds']:.4f} |"
            )
    lines += [
        "",
        f"Replay, public record and oracle finding equivalence, and oracle reward invariance "
        f"passed on {passed}/{pairs} combined ID and order transformations.",
        "",
    ]
    return "\n".join(lines)


def run_benchmark(splits_path: Path, output: Path) -> bool:
    plan = json.loads(splits_path.read_text(encoding="utf-8"))
    cases = {"train": plan["train"], "dev": plan["dev"], "mirror": _mirror_cases()}
    output.mkdir(parents=True, exist_ok=True)
    with (output / "trajectories.jsonl").open("w", encoding="utf-8") as stream:
        results = {split: _run_split(split, rows, stream) for split, rows in cases.items()}
    env = AuditEnv("train")
    try:
        pairs = [_check_pair(env, case) for case in cases["mirror"]]
    finally:
        env.close()
    passed = sum(all(pair["checks"].values()) for pair in pairs)
    data = {
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "cases": cases,
        "splits": results,
        "pairs": pairs,
    }
    (output / "metrics.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    (output / "summary.md").write_text(
        _summary_markdown(results, passed, len(pairs)), encoding="utf-8"
    )
    return passed == len(pairs)
