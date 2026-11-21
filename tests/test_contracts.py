"""Frozen contracts: public files, truth and submissions validate against schemas/*.json."""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ledgerforge.agents.oracle import OraclePolicy
from ledgerforge.contracts.schemas import ScenarioConfig
from ledgerforge.contracts.submission import MalformedSubmission, validate_submission
from ledgerforge.sim.episode import generate_episode

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/submission_valid.json").read_text())


def schema(name):
    s = json.loads((ROOT / "schemas" / f"{name}.schema.json").read_text())
    Draft202012Validator.check_schema(s)
    return Draft202012Validator(s)


@pytest.fixture(scope="module")
def episode():
    cfg = {
        "faults": {
            "duplicate_invoice": 1,
            "payment_allocation": 1,
            "fx_rate": 1,
            "reporting_period": 1,
        },
        "interactions": {"duplicate_with_allocation": 1, "fx_with_period": 1},
    }
    return generate_episode(4, ScenarioConfig.from_dict(cfg))


def test_public_tables_match_schemas(episode):
    public, _ = episode
    schema("manifest").validate(public.manifest)
    for table, name in (
        ("ledger", "ledger_row"),
        ("invoices", "invoice"),
        ("payments", "payment"),
        ("fx", "fx_row"),
    ):
        v = schema(name)
        for row in getattr(public, table):
            v.validate(row)
    assert public.manifest["counts"]["ledger"] == len(public.ledger)


def test_truth_and_oracle_submission_match_schemas(episode):
    public, truth = episode
    schema("truth").validate(truth.truth_dict())
    obs = {"manifest": public.manifest}
    sub = OraclePolicy(truth).act(obs)["args"]
    schema("submission").validate(sub)
    assert len(validate_submission(sub, truth.episode_id)) == len(truth.issues)


def test_fixture_is_valid():
    schema("submission").validate(FIXTURE)
    validate_submission(FIXTURE, FIXTURE["episode_id"])


def mutate(path, value):
    sub = copy.deepcopy(FIXTURE)
    target = sub
    for key in path[:-1]:
        target = target[key]
    if value is KeyError:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return sub


@pytest.mark.parametrize(
    "sub",
    [
        None,
        [],
        "x",
        {"findings": []},
        mutate(["episode_id"], "EP-other"),
        mutate(["extra"], 1),
        mutate(["findings"], [FIXTURE["findings"][0]] * 31),
        mutate(["findings", 0, "type"], "fraud"),
        mutate(["findings", 0, "affected_ids"], []),
        mutate(["findings", 0, "evidence_ids"], ["E"] * 11),
        mutate(["findings", 0, "claimed_amount_minor"], 1.5),
        mutate(["findings", 0, "claimed_amount_minor"], True),
        mutate(["findings", 0, "currency"], "TENGE"),
        mutate(["findings", 0, "explanation"], "x" * 1001),
        mutate(["findings", 0, "explanation"], KeyError),
        mutate(["findings", 0, "bonus"], "x"),
    ],
)
def test_malformed_submissions_rejected(sub):
    with pytest.raises(MalformedSubmission):
        validate_submission(sub, FIXTURE["episode_id"])


@pytest.mark.parametrize(
    "bad",
    [
        {"n_invoices": 5},
        {"faults": {"fraud": 1}},
        {"unknown_key": 1},
        {"faults": {"duplicate_invoice": 13}},
        {"difficulty": "impossible"},
        {"interactions": ["duplicate_with_allocation"]},
        {"faults": [1]},
        {"faults": {"fx_rate": True}},
        {"n_invoices": "50"},
        {"distractors": "yes"},
        {"id_salt": 7},
        {"industry": ["construction"]},
        {"schema_version": None},
    ],
)
def test_invalid_configs_rejected(bad):
    with pytest.raises(ValueError):
        ScenarioConfig.from_dict(bad).validate()
