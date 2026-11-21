import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from ledgerforge.benchmark.figures import parse_ablation, render


def test_charts_render_as_valid_svg_from_committed_outputs(tmp_path: Path) -> None:
    paths = render(tmp_path)

    assert {p.name for p in paths} == {"baselines.svg", "ablation.svg", "reward.svg"}
    for path in paths:
        assert ET.parse(path).getroot().tag.endswith("svg")  # noqa: S314 (our own output)


def test_ablation_chart_reads_every_committed_variant() -> None:
    rows = parse_ablation(Path("outputs/reports/ablation.md").read_text(encoding="utf-8"))

    assert rows[0] == {"variant": "reconciler", "tp": 71, "fp": 0, "fn": 0, "f1": 1.0,
                       "reward": 0.953}  # fmt: skip
    assert len(rows) == 6


def test_ablation_parser_rejects_a_table_without_rows() -> None:
    with pytest.raises(ValueError, match="no ablation rows"):
        parse_ablation("| Variant | TP |\n|---|---|\n")
