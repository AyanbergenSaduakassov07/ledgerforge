"""Render the README charts as standalone SVG from committed benchmark outputs. Stdlib only.

    uv run python -m ledgerforge.benchmark.figures [--out docs/assets]

Inputs: outputs/benchmarks/metrics.json and outputs/reports/ablation.md. Nothing is re-measured,
so the charts always show exactly the numbers in the committed reports.
"""

from __future__ import annotations

import argparse
import json
import logging
from html import escape
from pathlib import Path
from typing import Any

from ledgerforge.evaluation.matcher import reward_from

log = logging.getLogger(__name__)

METRICS = Path("outputs/benchmarks/metrics.json")
ABLATION = Path("outputs/reports/ablation.md")

POLICIES = (("oracle", "Oracle"), ("reconciler", "Reconciler"), ("random_explorer", "Random"),
            ("flag_all", "Flag-all"))  # fmt: skip
SPLITS = (("train", "#3b82f6"), ("dev", "#8b5cf6"), ("mirror", "#10b981"))
VARIANT_LABELS = {
    "reconciler": "All published rules",
    "naive_duplicates": "Naive duplicates",
    "naive_period": "Naive period",
    "naive_fx": "Naive FX",
    "naive_allocation": "Naive allocation",
    "naive_allocation+duplicates+fx+period": "All four shortcuts",
}

_STYLE = """<style>
.card{fill:#f6f8fa;stroke:#d0d7de}.fg{fill:#1f2328}.mu{fill:#59636e}.gr{stroke:#d0d7de}
@media (prefers-color-scheme:dark){.card{fill:#161b22;stroke:#30363d}.fg{fill:#e6edf3}
.mu{fill:#9198a1}.gr{stroke:#30363d}}
text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.t{font-size:18px;font-weight:600}.s{font-size:12px}.v{font-size:11px;font-weight:600}
</style>"""


def _svg(width: int, height: int, title: str, subtitle: str, body: list[str]) -> str:
    head = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">',
        f"<title>{escape(title)}</title>",
        _STYLE,
        f'<rect class="card" x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="12"/>',
        f'<text class="fg t" x="24" y="36">{escape(title)}</text>',
        f'<text class="mu s" x="24" y="56">{escape(subtitle)}</text>',
    ]
    return "\n".join([*head, *body, "</svg>"]) + "\n"


def _text(x: float, y: float, s: str, cls: str = "mu s", anchor: str = "start") -> str:
    return f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}">{escape(s)}</text>'


def baselines_svg(metrics: dict[str, Any]) -> str:
    """Grouped bars: mean reward per policy on each split, on a −1..1 axis."""
    left, top, plot_w, plot_h = 64, 84, 640, 240
    zero = top + plot_h / 2
    body: list[str] = []
    for tick in (-1.0, -0.5, 0.0, 0.5, 1.0):
        y = zero - tick * plot_h / 2
        body.append(f'<line class="gr" x1="{left}" x2="{left + plot_w}" y1="{y}" y2="{y}"/>')
        body.append(_text(left - 8, y + 4, f"{tick:+.1f}", anchor="end"))
    group_w = plot_w / len(POLICIES)
    bar_w = 34
    for g, (key, label) in enumerate(POLICIES):
        x0 = left + g * group_w + (group_w - bar_w * len(SPLITS)) / 2
        for i, (split, colour) in enumerate(SPLITS):
            value = metrics["splits"][split][key]["means"]["reward"]
            h = abs(value) * plot_h / 2
            y = zero - h if value >= 0 else zero
            x = x0 + i * bar_w
            body.append(
                f'<rect x="{x + 3:.1f}" y="{y:.1f}" width="{bar_w - 6}" height="{max(h, 1):.1f}" '
                f'rx="3" fill="{colour}"/>'
            )
            ty = y - 5 if value >= 0 else y + h + 13
            body.append(_text(x + bar_w / 2, ty, f"{value:+.2f}", "fg v", "middle"))
        body.append(_text(left + (g + 0.5) * group_w, top + plot_h + 44, label, "fg s", "middle"))
    for i, (split, colour) in enumerate(SPLITS):
        x = left + plot_w - 230 + i * 80
        body.append(f'<rect x="{x}" y="47" width="10" height="10" rx="2" fill="{colour}"/>')
        body.append(_text(x + 15, 56, split))
    return _svg(728, 380, "Mean reward by baseline", "10 train · 10 dev · 20 mirror episodes", body)


def parse_ablation(markdown: str) -> list[dict[str, Any]]:
    """Rows of the committed ablation table: variant, tp, fp, fn, f1, reward."""
    rows = []
    for line in markdown.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 6 and cells[0] in VARIANT_LABELS:
            tp, fp, fn = (int(c) for c in cells[1:4])
            rows.append(
                {
                    "variant": cells[0],
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                    "f1": float(cells[4]),
                    "reward": float(cells[5]),
                }  # fmt: skip
            )
    if not rows:
        raise ValueError("no ablation rows found")
    return rows


def ablation_svg(rows: list[dict[str, Any]]) -> str:
    """Horizontal bars: mean F1 when one published rule is replaced by a shortcut."""
    left, top, plot_w, row_h = 180, 80, 380, 38
    body: list[str] = []
    for tick in (0.0, 0.25, 0.5, 0.75, 1.0):
        x = left + tick * plot_w
        y2 = top + row_h * len(rows)
        body.append(f'<line class="gr" x1="{x}" x2="{x}" y1="{top - 6}" y2="{y2}"/>')
        body.append(_text(x, y2 + 16, f"{tick:.2f}", anchor="middle"))
    for i, row in enumerate(rows):
        y = top + i * row_h
        colour = "#10b981" if row["fp"] == 0 else "#ef4444" if row["f1"] < 0.2 else "#f59e0b"
        w = max(row["f1"] * plot_w, 2)
        body.append(_text(left - 12, y + 21, VARIANT_LABELS[row["variant"]], "fg s", "end"))
        body.append(f'<rect x="{left}" y="{y + 7}" width="{w:.1f}" height="22" rx="4" '
                    f'fill="{colour}"/>')  # fmt: skip
        note = f"F1 {row['f1']:.3f} · {row['fp']} FP · reward {row['reward']:+.2f}"
        body.append(_text(left + w + 8, y + 22, note, "fg v"))
    height = top + row_h * len(rows) + 36
    return _svg(
        780, height, "Skipping one published rule breaks the benchmark",
        "Reconciler F1 on 40 episodes when a rule is swapped for a shallow heuristic", body,
    )  # fmt: skip


def reward_svg() -> str:
    """The official reward as a function of F1 for three inspection budgets."""
    left, top, plot_w, plot_h = 64, 80, 560, 240
    body: list[str] = []

    def px(f1: float, r: float) -> tuple[float, float]:
        return left + f1 * plot_w, top + (1 - r) / 2 * plot_h

    for tick in (-1.0, -0.5, 0.0, 0.5, 1.0):
        y = px(0, tick)[1]
        body.append(f'<line class="gr" x1="{left}" x2="{left + plot_w}" y1="{y}" y2="{y}"/>')
        body.append(_text(left - 8, y + 4, f"{tick:+.1f}", anchor="end"))
    for f1 in (0.0, 0.25, 0.5, 0.75, 1.0):
        body.append(_text(px(f1, 0)[0], top + plot_h + 18, f"{f1:.2f}", anchor="middle"))
    body.append(_text(left + plot_w / 2, top + plot_h + 38, "F1", "fg s", "middle"))
    for steps, colour in ((0, "#10b981"), (25, "#3b82f6"), (100, "#f59e0b")):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in
                       (px(f / 100, reward_from(f / 100, steps)) for f in range(101)))  # fmt: skip
        body.append(f'<polyline points="{pts}" fill="none" stroke="{colour}" stroke-width="2.5"/>')
        ly = top + plot_h - 70 + [0, 25, 100].index(steps) * 20
        lx = left + plot_w - 130
        body.append(f'<rect x="{lx}" y="{ly}" width="14" height="4" rx="2" fill="{colour}"/>')
        body.append(_text(left + plot_w - 110, ly + 6, f"{steps} inspection steps"))
    x, y = px(1, reward_from(1, 25))
    body.append(
        f'<circle cx="{x}" cy="{y}" r="5" fill="#3b82f6" stroke="#fff" stroke-width="1.5"/>'
    )
    body.append(_text(x - 16, y - 16, "reconciler: F1 1.0, ≈25 steps → ≈0.95", "fg v", "end"))
    return _svg(
        720, 380, "reward = clip(2·F1 − 1 − 0.002·steps, −1, 1)",
        "Silence on faulty books and false accusations on clean books both score −1", body,
    )  # fmt: skip


def render(out: Path, metrics_path: Path = METRICS, ablation_path: Path = ABLATION) -> list[Path]:
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    rows = parse_ablation(ablation_path.read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    charts = {
        "baselines.svg": baselines_svg(metrics),
        "ablation.svg": ablation_svg(rows),
        "reward.svg": reward_svg(),
    }
    paths = []
    for name, svg in charts.items():
        (out / name).write_text(svg, encoding="utf-8")
        paths.append(out / name)
    return paths


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Render README charts from committed outputs.")
    parser.add_argument("--out", default="docs/assets")
    for path in render(Path(parser.parse_args(argv).out)):
        log.info("wrote %s", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
