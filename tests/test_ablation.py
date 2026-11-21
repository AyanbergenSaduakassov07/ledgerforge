import pytest

from ledgerforge.agents.reconciler import NAIVE_RULES, ReconcilerPolicy
from ledgerforge.benchmark.ablation import to_markdown
from ledgerforge.benchmark.trajectory import run_episode
from ledgerforge.env.env import AuditEnv

CASES = [(seed, {"difficulty": "advanced"}) for seed in (1, 2, 3)]


@pytest.mark.parametrize("rule", NAIVE_RULES)
def test_each_shallow_heuristic_is_punished_by_look_alikes(env: AuditEnv, rule: str) -> None:
    fp = sum(
        run_episode(env, ReconcilerPolicy({rule}), seed, config)[-1]["report"]["fp"]
        for seed, config in CASES
    )
    assert fp > 0


def test_default_reconciler_is_unchanged(env: AuditEnv) -> None:
    policy = ReconcilerPolicy()
    assert policy.name == "reconciler"
    assert run_episode(env, policy, 1, {"difficulty": "advanced"})[-1]["report"]["fp"] == 0


def test_unknown_rule_is_rejected() -> None:
    with pytest.raises(ValueError):
        ReconcilerPolicy({"vibes"})


def test_markdown_lists_every_variant() -> None:
    row = {"tp": 1.0, "fp": 0.0, "fn": 0.0, "f1": 1.0, "reward": 0.9}
    assert "| reconciler | 1 | 0 | 0 | 1.000 | 0.900 |" in to_markdown({"reconciler": row}, 1)
