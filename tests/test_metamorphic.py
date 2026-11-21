"""Paired transforms (id_salt, order_salt) give equivalent episodes; size limits hold."""

import time

import pytest

from ledgerforge.agents.oracle import OraclePolicy
from ledgerforge.contracts.schemas import ScenarioConfig
from ledgerforge.sim.episode import generate_episode
from ledgerforge.sim.salt import digit_table

MIXED = {
    "faults": {"duplicate_invoice": 1, "payment_allocation": 1, "fx_rate": 1},
    "interactions": {"duplicate_with_allocation": 1, "fx_with_period": 1},
}


def gen(seed, **extra):
    return generate_episode(seed, ScenarioConfig.from_dict({**MIXED, **extra}))


def public_ids(public):
    ids = {r["row_id"] for r in public.ledger}
    for d in public.invoices + public.payments:
        ids |= {d["doc_id"], d.get("invoice_id"), d.get("payment_id"), d.get("entity_id")}
    return ids - {None}


def shape(issue):
    return issue.type, issue.expected_amount_minor, issue.currency, len(issue.affected_ids)


@pytest.mark.parametrize("seed", range(10))
def test_id_salt_renames_everything_and_keeps_the_problem(seed):
    base_pub, base_truth = gen(seed)
    pub, truth = gen(seed, id_salt=f"pair-{seed}")
    t = digit_table(f"pair-{seed}")
    assert all(i.translate(t) != i for i in public_ids(base_pub))
    assert {i.translate(t) for i in public_ids(base_pub)} == public_ids(pub)
    assert pub.fx == base_pub.fx
    assert truth.episode_id == pub.manifest["episode_id"] != base_truth.episode_id
    assert sorted(map(shape, truth.issues)) == sorted(map(shape, base_truth.issues))
    renamed = {
        (i.type, tuple(sorted(x.translate(t) if x[0] != "2" else x for x in i.affected_ids)))
        for i in base_truth.issues
    }
    assert {(i.type, tuple(sorted(i.affected_ids))) for i in truth.issues} == renamed


@pytest.mark.parametrize("salt", ["a", "b", "zz"])
def test_digit_table_is_a_derangement(salt):
    out = "0123456789".translate(digit_table(salt))
    assert sorted(out) == list("0123456789")
    assert all(a != b for a, b in zip(out, "0123456789", strict=True))


def test_oracle_reward_identical_across_paired_transforms(env):
    for seed in range(3):
        rewards = []
        for extra in ({}, {"id_salt": "p"}, {"order_salt": "p"}):
            cfg = {**MIXED, **extra}
            _, truth = generate_episode(seed, ScenarioConfig.from_dict(cfg))
            obs, _ = env.reset(seed, cfg)
            _, reward, *_ = env.step(OraclePolicy(truth).act(obs))
            rewards.append(reward)
        assert rewards == [1.0, 1.0, 1.0]


def test_order_salt_only_reorders():
    base_pub, base_truth = gen(5)
    pub, truth = gen(5, order_salt="x")
    key = lambda rows, k: sorted(rows, key=lambda r: r[k])  # noqa: E731
    assert key(pub.ledger, "row_id") == key(base_pub.ledger, "row_id")
    assert pub.ledger != base_pub.ledger
    assert truth.issues == base_truth.issues


def test_largest_episode_fits_official_ranges_and_budget():
    cfg = {
        "difficulty": "expert",
        "n_invoices": 100,
        "faults": {
            "duplicate_invoice": 2,
            "payment_allocation": 2,
            "fx_rate": 2,
            "reporting_period": 2,
        },
        "interactions": {"duplicate_with_allocation": 1, "fx_with_period": 1},
    }
    t0 = time.perf_counter()
    pub, truth = generate_episode(11, ScenarioConfig.from_dict(cfg))
    elapsed = time.perf_counter() - t0
    assert len(truth.issues) == 12
    assert 200 <= len(pub.ledger) <= 2000
    assert 20 <= len(pub.invoices) + len(pub.payments) <= 200
    assert elapsed < 5.0
