"""Rule ablation: replace one published rule at a time with a common shallow heuristic.

uv run python -m ledgerforge.benchmark.ablation [--splits episodes/splits.json] [--out PATH]
Shows that each look-alike family punishes a specific shortcut (ADR-017). Measured only.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from statistics import fmean
from typing import Any

from ledgerforge.agents.reconciler import NAIVE_RULES, ReconcilerPolicy
from ledgerforge.benchmark.run import mirror_cases
from ledgerforge.benchmark.trajectory import run_episode
from ledgerforge.env.env import AuditEnv

log = logging.getLogger(__name__)
VARIANTS: tuple[frozenset[str], ...] = (
    frozenset(),
    *(frozenset({rule}) for rule in NAIVE_RULES),
    frozenset(NAIVE_RULES),
)
_FIELDS = ("tp", "fp", "fn")


def run_ablation(cases: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    env = AuditEnv("train")
    results: dict[str, dict[str, float]] = {}
    try:
        for naive in VARIANTS:
            policy = ReconcilerPolicy(naive)
            reports = [
                run_episode(env, policy, c["seed"], c["config"])[-1]["report"] for c in cases
            ]  # noqa: E501
            if any(r is None for r in reports):
                raise RuntimeError(f"{policy.name}: an episode ended without a score report")
            row = {f: float(sum(r[f] for r in reports)) for f in _FIELDS}
            row.update({m: fmean(r[m] for r in reports) for m in ("f1", "reward")})
            results[policy.name] = row
    finally:
        env.close()
    return results


def to_markdown(results: dict[str, dict[str, float]], n_cases: int) -> str:
    lines = [
        "# Rule ablation",
        "",
        f"Reconciler on train + dev + mirror ({n_cases} episodes). Each row swaps the named",
        "published rule for a shallow heuristic (see `agents/reconciler.py`). Measured by",
        "`uv run python -m ledgerforge.benchmark.ablation`.",
        "",
        "| Variant | TP | FP | FN | mean F1 | mean reward |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, row in results.items():
        lines.append(
            f"| {name} | {row['tp']:.0f} | {row['fp']:.0f} | {row['fn']:.0f} "
            f"| {row['f1']:.3f} | {row['reward']:.3f} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--splits", type=Path, default=Path("episodes/splits.json"))
    parser.add_argument("--out", type=Path, default=Path("outputs/reports/ablation.md"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    plan = json.loads(args.splits.read_text(encoding="utf-8"))
    cases = [*plan["train"], *plan["dev"], *mirror_cases()]
    text = to_markdown(run_ablation(cases), len(cases))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    log.info("%s", text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
