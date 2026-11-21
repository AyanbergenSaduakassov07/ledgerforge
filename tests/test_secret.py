"""LEDGERFORGE_SECRET: closed episodes cannot be rebuilt from the seed with the open generator."""

import ast
import json
import random
import subprocess
import sys
from pathlib import Path

from ledgerforge.contracts.schemas import ScenarioConfig
from ledgerforge.sim import profiles
from ledgerforge.sim import world as W
from ledgerforge.sim.episode import generate_episode
from ledgerforge.sim.secret import SECRET_ENV

SRC = Path(__file__).resolve().parents[1] / "src" / "ledgerforge"
CONFIG = {"faults": {"duplicate_invoice": 1, "fx_rate": 1}}
SEED = 1234


def _episode(seed: int = SEED, config: dict | None = None) -> str:
    public, truth = generate_episode(seed, ScenarioConfig.from_dict(config or CONFIG))
    return json.dumps(
        [public.to_dict(), truth.truth_dict(), truth.provenance], sort_keys=True, default=list
    )


def _seed_search(episode_id: str, limit: int) -> int | None:
    """The public-generator attack: replay the open world stream until the episode id matches."""
    for s in range(limit):
        r = random.Random(f"ledgerforge:{s}:0:world")
        W._quarter(r), r.choice(profiles.TIMEZONES)
        if f"EP-{r.getrandbits(48):012x}" == episode_id:
            return s
    return None


def test_keyed_generation_is_byte_identical(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, "jury-key-1")
    assert _episode() == _episode()


def test_seed_search_finds_open_seed_but_not_keyed_seed(monkeypatch):
    open_id = json.loads(_episode())[0]["manifest"]["episode_id"]
    assert _seed_search(open_id, SEED + 1) == SEED  # the leak the key closes
    monkeypatch.setenv(SECRET_ENV, "jury-key-1")
    keyed_id = json.loads(_episode())[0]["manifest"]["episode_id"]
    assert keyed_id != open_id
    assert _seed_search(keyed_id, 20_000) is None


def test_different_keys_give_different_episodes(monkeypatch):
    episodes = set()
    for key in ("", "jury-key-1", "jury-key-2"):
        monkeypatch.setenv(SECRET_ENV, key)
        episodes.add(_episode())
    assert len(episodes) == 3


def test_key_also_changes_id_salt(monkeypatch):
    from ledgerforge.sim.salt import digit_table

    open_table = digit_table("mirror-1")
    monkeypatch.setenv(SECRET_ENV, "jury-key-1")
    assert digit_table("mirror-1") != open_table


def _imports(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names |= {f"{node.module}.{a.name}" for a in node.names}
    return names


def test_agent_side_never_touches_the_key():
    for package in ("env", "agents"):
        for path in sorted((SRC / package).glob("*.py")):
            assert not any("secret" in name for name in _imports(path)), path
            assert SECRET_ENV not in path.read_text(encoding="utf-8"), path
    modules = ["ledgerforge.env.env"] + [
        f"ledgerforge.agents.{p.stem}" for p in sorted((SRC / "agents").glob("*.py"))
    ]
    code = (
        "import importlib, sys\n"
        f"for m in {modules!r}: importlib.import_module(m)\n"
        "print('ledgerforge.sim.secret' in sys.modules)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


def test_eval_mode_warns_on_stderr_without_key(monkeypatch, capsys):
    from ledgerforge.evaluation.service import Evaluator

    Evaluator("eval")
    assert SECRET_ENV in capsys.readouterr().err
    monkeypatch.setenv(SECRET_ENV, "jury-key-1")
    Evaluator("eval")
    Evaluator("train")
    assert capsys.readouterr().err == ""
