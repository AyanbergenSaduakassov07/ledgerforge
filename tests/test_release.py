"""Committed open episodes regenerate byte-identically and carry no private files."""

import json
from pathlib import Path

from ledgerforge.contracts.schemas import ScenarioConfig
from ledgerforge.sim.episode import generate_episode
from ledgerforge.sim.export import write_public

EPISODES = Path(__file__).resolve().parents[1] / "episodes"
PLAN = json.loads((EPISODES / "splits.json").read_text())


def test_splits_are_disjoint_and_cover_required_mix():
    train = {i["seed"] for i in PLAN["train"]}
    dev = {i["seed"] for i in PLAN["dev"]}
    assert len(train) == len(dev) == 10 and not train & dev
    for split in ("train", "dev"):
        cfgs = [i["config"] for i in PLAN[split]]
        assert sum(not c.get("faults") and not c.get("interactions") for c in cfgs) >= 2
        assert sum(bool(c.get("interactions")) for c in cfgs) >= 2


def test_committed_episodes_regenerate_identically(tmp_path):
    for split in ("train", "dev"):
        committed = sorted(p.name for p in (EPISODES / split).iterdir() if p.is_dir())
        names = []
        for item in PLAN[split]:
            public, _ = generate_episode(item["seed"], ScenarioConfig.from_dict(item["config"]))
            name = public.manifest["episode_id"]
            names.append(name)
            write_public(public, tmp_path / name)
            for f in (tmp_path / name).iterdir():
                assert f.read_bytes() == (EPISODES / split / name / f.name).read_bytes(), f
        assert sorted(names) == committed


def test_no_private_files_in_episodes():
    leaked = [p for p in EPISODES.rglob("*") if p.name in ("truth.json", "provenance.json")]
    assert leaked == []
