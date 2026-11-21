"""Phase 4 vertical slice: generate -> reset -> inspect -> submit -> match -> reward -> replay."""

import json
import subprocess
import sys
from typing import Any

from conftest import DUP
from ledgerforge.agents.oracle import OraclePolicy
from ledgerforge.benchmark.trajectory import read_jsonl, replay, run_episode, write_jsonl
from ledgerforge.contracts.schemas import ScenarioConfig
from ledgerforge.sim.episode import generate_episode


class InspectThenOracle(OraclePolicy):
    """Spends n inspection steps listing the ledger, then submits the truth."""

    def __init__(self, truth, n):
        super().__init__(truth)
        self.n, self.i = n, 0

    def act(self, observation):
        self.i += 1
        if self.i <= self.n:
            return {"tool": "list_records", "args": {"table": "ledger", "limit": 50}}
        return super().act(observation)


def test_oracle_scores_one_on_duplicate_episode(env):
    _, truth = generate_episode(7, ScenarioConfig.from_dict(DUP))
    records = run_episode(env, OraclePolicy(truth), 7, DUP)
    last = records[-1]
    assert len(records) == 1 and last["terminated"] and not last["truncated"]
    assert last["reward"] == 1.0
    assert last["report"]["tp"] == 1 and last["report"]["fp"] == 0


def test_inspection_steps_are_penalised(env):
    _, truth = generate_episode(7, ScenarioConfig.from_dict(DUP))
    records = run_episode(env, InspectThenOracle(truth, 3), 7, DUP)
    assert [r["reward"] for r in records] == [0.0, 0.0, 0.0, 1.0 - 0.002 * 3]


def test_empty_submission_on_duplicate_episode_scores_minus_one(env):
    obs, info = env.reset(7, DUP)
    sub = {"episode_id": info["episode_id"], "findings": []}
    _, reward, terminated, _, step_info = env.step({"tool": "submit", "args": sub})
    assert terminated and reward == -1.0 and step_info["report"]["fn"] == 1


def test_trajectory_replays_identically(env, tmp_path):
    _, truth = generate_episode(11, ScenarioConfig.from_dict(DUP))
    records = run_episode(env, InspectThenOracle(truth, 2), 11, DUP)
    path = tmp_path / "trajectories.jsonl"
    write_jsonl(path, records)
    logged = read_jsonl(path)
    assert replay(env, logged) == logged


def test_trajectory_survives_policy_edits_to_prior_observation_and_action(env) -> None:
    _, truth = generate_episode(7, ScenarioConfig.from_dict(DUP))

    class AnnotatingPolicy(OraclePolicy):
        def reset(self, observation: dict[str, Any]) -> None:
            super().reset(observation)
            self.request = {"tool": "list_records", "args": {"table": "invoices", "limit": 1}}

        def act(self, observation: dict[str, Any]) -> dict[str, Any]:
            if "result" not in observation:
                return self.request
            row = observation["result"]["rows"][0]
            row["line_items"][0]["description"] += " (display annotation)"
            self.request["args"]["limit"] = 2
            return super().act(observation)

    records = run_episode(env, AnnotatingPolicy(truth), 7, DUP)
    assert records[0]["action"]["args"]["limit"] == 1
    assert replay(env, records) == records


def test_agent_process_never_receives_truth(env):
    public, truth = generate_episode(7, ScenarioConfig.from_dict(DUP))
    obs, _ = env.reset(7, DUP)
    blob = json.dumps([obs, env._data])
    assert "truth" not in blob and "provenance" not in blob and "faulted" not in blob
    assert env._data == json.loads(json.dumps(public.to_dict()))


def test_generation_is_identical_across_processes():
    code = (
        "import json,hashlib;from ledgerforge.sim.episode import generate_episode as g;"
        "from ledgerforge.contracts.schemas import ScenarioConfig as C;"
        "p,t=g(5,C.from_dict({'faults':{'duplicate_invoice':1,'fx_rate':1}}));"
        "print(hashlib.sha256(json.dumps([p.to_dict(),t.truth_dict()],sort_keys=True)"
        ".encode()).hexdigest())"
    )
    outs = {
        subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONHASHSEED": str(h)},
        ).stdout
        for h in (1, 2)
    }
    assert len(outs) == 1
