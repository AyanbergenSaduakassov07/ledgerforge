import json
from pathlib import Path

import pytest

from ledgerforge import cli
from ledgerforge.benchmark import run

PUBLISHED = {
    "trajectories.jsonl": b'{"previous":"trajectory"}\n',
    "metrics.json": b'{"previous":"metrics"}\n',
    "summary.md": b"# Previous benchmark\n",
}


@pytest.fixture
def benchmark_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    output = tmp_path / "output"
    output.mkdir()
    for name, content in PUBLISHED.items():
        (output / name).write_bytes(content)
    splits = tmp_path / "splits.json"
    splits.write_text(
        json.dumps({"train": [{"seed": 1, "config": {}}], "dev": [{"seed": 2, "config": {}}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(run, "mirror_cases", lambda: [{"seed": 3, "config": {}}])
    return splits, output


def _outputs(path: Path) -> dict[str, bytes]:
    return {file.name: file.read_bytes() for file in path.iterdir()}


def test_invalid_recipe_preserves_published_benchmark(benchmark_paths: tuple[Path, Path]) -> None:
    splits, output = benchmark_paths
    plan = json.loads(splits.read_text(encoding="utf-8"))
    plan["dev"][0]["config"] = {"n_invoices": 19}
    splits.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError, match="n_invoices"):
        run.run_benchmark(splits, output)

    assert _outputs(output) == PUBLISHED


def test_failed_pair_preserves_published_benchmark(
    benchmark_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    splits, output = benchmark_paths
    monkeypatch.setattr(run, "_check_pair", lambda _env, _case: {"checks": {"replay": False}})

    assert cli.main(["bench", "--splits", str(splits), "--out", str(output)]) == 1
    assert _outputs(output) == PUBLISHED
    assert "paired checks failed" in caplog.text


def test_successful_benchmark_replaces_all_outputs(benchmark_paths: tuple[Path, Path]) -> None:
    splits, output = benchmark_paths
    assert run.run_benchmark(splits, output)
    artifacts = _outputs(output)
    assert artifacts.keys() == PUBLISHED.keys()
    assert set(json.loads(artifacts["metrics.json"])["splits"]) == {"train", "dev", "mirror"}
    assert json.loads(artifacts["trajectories.jsonl"].splitlines()[0])["split"] == "train"
    assert b"passed on 1/1" in artifacts["summary.md"]
