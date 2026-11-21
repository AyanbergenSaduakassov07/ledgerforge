"""Adversarial scoring checks through the public environment entry point."""

import json
import subprocess
import sys
from itertools import permutations
from random import Random
from statistics import mean
from typing import Any

import pytest

from ledgerforge.agents.flag_all import FlagAllPolicy
from ledgerforge.agents.oracle import OraclePolicy
from ledgerforge.benchmark.trajectory import run_episode
from ledgerforge.contracts.schemas import ERROR_TYPES, INTERACTIONS, ScenarioConfig
from ledgerforge.env.env import AuditEnv
from ledgerforge.sim.episode import generate_episode


def test_flagging_everything_has_negative_mean_reward(env: AuditEnv) -> None:
    faulted = [
        *({"faults": {kind: 1}} for kind in ERROR_TYPES for _ in range(2)),
        *({"interactions": {kind: 1}} for kind in INTERACTIONS),
    ]
    policy = FlagAllPolicy()
    rewards = []
    for seed, config in enumerate([*faulted, *({} for _ in range(5))], start=31):
        final = run_episode(env, policy, seed, config)[-1]
        assert final["terminated"] and final["report"]["valid"]
        assert final["report"]["fp"] > 0
        rewards.append(final["reward"])
    assert len(rewards) == 15
    assert mean(rewards) < 0.0


def _oracle_findings(env: AuditEnv, seed: int, config: dict[str, Any]) -> list[dict[str, Any]]:
    _, truth = generate_episode(seed, ScenarioConfig.from_dict(config))
    initial, _ = env.reset(seed, config)
    oracle = OraclePolicy(truth)
    oracle.reset(initial)
    return oracle.act(initial)["args"]["findings"]


def _submit(
    env: AuditEnv, seed: int, config: dict[str, Any], findings: list[dict[str, Any]]
) -> tuple[float, dict[str, Any]]:
    _, info = env.reset(seed, config)
    _, reward, terminated, truncated, final = env.step(
        {"tool": "submit", "args": {"episode_id": info["episode_id"], "findings": findings}}
    )
    assert terminated and not truncated and final["report"]["valid"]
    return reward, final["report"]


def test_reward_is_invariant_across_twenty_finding_permutations(env: AuditEnv) -> None:
    seed = 17
    config = {"interactions": dict.fromkeys(INTERACTIONS, 1)}
    oracle = _oracle_findings(env, seed, config)
    assert len(oracle) == 4
    duplicate = {**oracle[0], "explanation": "The same claim with different wording."}
    # Two minor units exceed the frozen one-unit tolerance.
    wrong_amount = {**oracle[-1], "claimed_amount_minor": oracle[-1]["claimed_amount_minor"] + 2}
    findings = [*oracle, duplicate, wrong_amount]
    orders = Random(17).sample(list(permutations(range(len(findings)))), 20)
    for order in orders:
        reward, report = _submit(env, seed, config, [findings[i] for i in order])
        assert (report["tp"], report["fp"], report["fn"]) == (4, 2, 0)
        assert reward == pytest.approx(0.6)


def test_persuasive_explanation_does_not_rescue_a_wrong_amount(env: AuditEnv) -> None:
    seed = 23
    config = {"faults": {"duplicate_invoice": 1}}
    [correct] = _oracle_findings(env, seed, config)
    good_reward, good_report = _submit(env, seed, config, [correct])
    assert (good_reward, good_report["tp"]) == (1.0, 1)

    wrong = {
        **correct,
        "claimed_amount_minor": correct["claimed_amount_minor"] + 2,
        "explanation": (
            "I independently reconciled both supplier documents against the posted AP entry. "
            "The evidence confirms this exact overstatement."
        ),
    }
    reward, report = _submit(env, seed, config, [wrong])
    assert (reward, report["tp"], report["fp"], report["fn"]) == (-1.0, 0, 1, 1)


@pytest.mark.parametrize(
    "line",
    [
        '{"cmd": "reset", "seed": Infinity, "config": {}}',
        '{"cmd": "reset", "seed": 1.5}',
        '{"cmd": "reset", "seed": true}',
        '{"cmd": "reset", "seed": "7"}',
        '{"cmd": "score", "submission": {}, "inspection_steps": 1e999}',
        "[]",
        "null",
        "not json",
    ],
)
def test_hostile_request_gets_an_error_and_the_evaluator_survives(line: str) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "ledgerforge.evaluation.service", "train"],
        input=line + '\n{"cmd": "report"}\n',
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    replies = [json.loads(r) for r in proc.stdout.splitlines()]
    assert len(replies) == 2 and "error" in replies[0], proc.stderr
    assert replies[1] == {"reports": []}
