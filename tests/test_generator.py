import pytest

from ledgerforge.contracts.schemas import ScenarioConfig
from ledgerforge.sim.episode import generate_episode
from ledgerforge.sim.export import read_public, write_private, write_public
from ledgerforge.verification.auditor import audit

CONFIGS = {
    "clean": {},
    "duplicate": {"faults": {"duplicate_invoice": 1}},
    "allocation": {"faults": {"payment_allocation": 2}},
    "fx": {"faults": {"fx_rate": 1}},
    "period": {"faults": {"reporting_period": 1}},
    "interaction_a": {"interactions": {"duplicate_with_allocation": 1}},
    "interaction_b": {"interactions": {"fx_with_period": 1}},
    "max_errors": {
        "faults": {
            "duplicate_invoice": 2,
            "payment_allocation": 2,
            "fx_rate": 2,
            "reporting_period": 2,
        },
        "interactions": {"duplicate_with_allocation": 1, "fx_with_period": 1},
    },
}


@pytest.mark.parametrize("name", CONFIGS)
@pytest.mark.parametrize("seed", range(5))
def test_truth_equals_independent_audit(name, seed):
    cfg = ScenarioConfig.from_dict(CONFIGS[name])
    public, truth = generate_episode(seed, cfg)
    result = audit(public.to_dict())
    assert result.violations == []
    assert result.keys() == {
        (t.type, t.affected_ids, t.expected_amount_minor, t.currency) for t in truth.issues
    }
    assert len(truth.issues) == cfg.total_errors()
    assert 200 <= len(public.ledger) <= 2000 and 20 <= len(public.invoices) <= 200


def test_same_seed_same_episode_different_seed_differs():
    cfg = ScenarioConfig.from_dict(CONFIGS["duplicate"])
    a, b, c = (generate_episode(s, cfg) for s in (3, 3, 4))
    assert a[0] == b[0] and a[1] == b[1]
    assert a[0].manifest["episode_id"] != c[0].manifest["episode_id"]


def test_episode_id_does_not_reveal_seed():
    public, _ = generate_episode(12345, ScenarioConfig())
    assert "12345" not in public.manifest["episode_id"]


def test_public_files_round_trip_and_private_files_separate(tmp_path):
    public, truth = generate_episode(2, ScenarioConfig.from_dict(CONFIGS["fx"]))
    write_public(public, tmp_path / "public")
    write_private(truth, tmp_path / "private")
    assert read_public(tmp_path / "public") == public
    assert {p.name for p in (tmp_path / "public").iterdir()} == {
        "manifest.json",
        "policy.json",
        "ledger.csv",
        "invoices.jsonl",
        "payments.jsonl",
        "fx.csv",
    }


def test_auditor_detects_a_hand_made_duplicate_in_a_clean_episode():
    public, _ = generate_episode(1, ScenarioConfig())
    ep = public.to_dict()
    inv = next(
        i for i in ep["invoices"] if any(r["invoice_id"] == i["invoice_id"] for r in ep["ledger"])
    )
    copy = {**inv, "doc_id": "DOC-COPY0001", "invoice_id": inv["invoice_id"] + "-X"}
    rows = [
        {**r, "row_id": r["row_id"] + "X", "invoice_id": copy["invoice_id"]}
        for r in ep["ledger"]
        if r["invoice_id"] == inv["invoice_id"] and not r["payment_id"]
    ]
    ep["invoices"].append(copy)
    ep["ledger"].extend(rows)
    types = [i["type"] for i in audit(ep).issues]
    assert types == ["duplicate_invoice"]
