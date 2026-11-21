import subprocess
import sys
from typing import Any

import pytest

from ledgerforge.benchmark.trajectory import run_episode
from ledgerforge.contracts.schemas import ERROR_TYPES, MAX_FINDINGS, MAX_STEPS, AgentPolicy
from ledgerforge.env.env import AuditEnv

CASES = [(1, {}), *((seed, {"faults": {fault: 1}}) for seed, fault in enumerate(ERROR_TYPES, 2))]


@pytest.fixture(params=["random_explorer", "reconciler", "flag_all"])
def policy(request: pytest.FixtureRequest) -> AgentPolicy:
    if request.param == "random_explorer":
        from ledgerforge.agents.random_explorer import RandomExplorerPolicy

        return RandomExplorerPolicy(seed=7)
    if request.param == "reconciler":
        from ledgerforge.agents.reconciler import ReconcilerPolicy

        return ReconcilerPolicy()
    from ledgerforge.agents.flag_all import FlagAllPolicy

    return FlagAllPolicy()


@pytest.mark.parametrize("seed,config", CASES)
def test_baseline_terminates_within_the_step_budget_and_repeats(
    env: AuditEnv, policy: AgentPolicy, seed: int, config: dict[str, Any]
) -> None:
    records = run_episode(env, policy, seed, config)
    assert 1 < len(records) <= MAX_STEPS
    assert records[-1]["terminated"] and not records[-1]["truncated"]
    assert records[-1]["report"]["valid"]
    assert records == run_episode(env, policy, seed, config)


def test_random_explorer_seed_changes_investigation(env: AuditEnv) -> None:
    from ledgerforge.agents.random_explorer import RandomExplorerPolicy

    first = run_episode(env, RandomExplorerPolicy(seed=11), 3)
    second = run_episode(env, RandomExplorerPolicy(seed=19), 3)
    assert [row["action"] for row in first[:-1]] != [row["action"] for row in second[:-1]]


def test_flag_all_submits_to_the_limit_across_fault_types(env: AuditEnv) -> None:
    from ledgerforge.agents.flag_all import FlagAllPolicy

    final = run_episode(env, FlagAllPolicy(), 1)[-1]
    findings = final["action"]["args"]["findings"]
    assert len(findings) == MAX_FINDINGS
    assert {finding["type"] for finding in findings} == set(ERROR_TYPES)
    assert final["report"]["fp"] == MAX_FINDINGS


@pytest.mark.parametrize(
    "seed,config",
    [
        *CASES,
        (9, {"interactions": {"duplicate_with_allocation": 1}}),
        (10, {"interactions": {"fx_with_period": 1}, "base_currency": "USD", "order_salt": "a"}),
    ],
)
def test_reconciler_checks_public_evidence_with_no_false_positives(
    env: AuditEnv, seed: int, config: dict[str, Any]
) -> None:
    from ledgerforge.agents.reconciler import ReconcilerPolicy

    report = run_episode(env, ReconcilerPolicy(), seed, config)[-1]["report"]
    expected = sum(config.get("faults", {}).values()) + 2 * sum(
        config.get("interactions", {}).values()
    )
    assert report["fp"] == 0 and report["tp"] + report["fn"] == expected
    # Known blind spot (reconciler shortcut): allocation faults on foreign payments (ADR-015).
    allocation = config.get("faults", {}).get("payment_allocation", 0) + sum(
        config.get("interactions", {}).values()
    )
    assert report["fn"] <= allocation


def test_baseline_imports_stay_on_the_agent_side() -> None:
    code = """
import sys
from ledgerforge.agents import flag_all, random_explorer, reconciler
from ledgerforge.benchmark.trajectory import run_episode
from ledgerforge.env.env import AuditEnv

env = AuditEnv()
try:
    for policy in (
        flag_all.FlagAllPolicy(),
        random_explorer.RandomExplorerPolicy(),
        reconciler.ReconcilerPolicy(),
    ):
        run_episode(env, policy, 1, {"faults": {"duplicate_invoice": 1}})
finally:
    env.close()

forbidden = ("ledgerforge.evaluation", "ledgerforge.sim", "ledgerforge.verification")
loaded = [name for name in sys.modules if name.startswith(forbidden)]
if loaded:
    raise AssertionError(loaded)
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False, timeout=10
    )
    assert result.returncode == 0, result.stderr
