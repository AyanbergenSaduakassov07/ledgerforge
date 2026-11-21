"""Replay recorded reconciler submissions and classify measured scoring failures."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from ledgerforge.contracts.schemas import (
    AMOUNT_TOLERANCE_MINOR,
    ERROR_TYPES,
    ScenarioConfig,
    TruthIssue,
)
from ledgerforge.contracts.submission import normalize_finding, validate_submission
from ledgerforge.evaluation.matcher import score
from ledgerforge.sim.episode import generate_episode


def _terminals(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    rows = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["policy"] != "reconciler" or not (row["terminated"] or row["truncated"]):
                continue
            key = row["split"], row["episode_id"]
            if key in rows:
                raise ValueError("multiple reconciler terminals for one episode")
            rows[key] = row
    return rows


def _mismatch(finding: dict[str, Any], issue: TruthIssue) -> tuple[int, str] | None:
    affected = frozenset(issue.affected_ids)
    if finding["affected_ids"] == affected:
        if finding["type"] != issue.type:
            return 4, "Wrong fault type"
        if finding["currency"] != issue.currency:
            return 1, "Wrong currency"
        if (
            abs(finding["claimed_amount_minor"] - issue.expected_amount_minor)
            > AMOUNT_TOLERANCE_MINOR
        ):
            return 2, "Amount outside tolerance"
        if not any(set(ids) <= finding["evidence_ids"] for ids in issue.allowed_evidence_sets):
            return 3, "Missing required evidence"
        return 0, "Competing claim for the same issue"
    if finding["type"] == issue.type and finding["affected_ids"] & affected:
        return 5, "Wrong affected records"
    return None


def _causes(
    findings: list[dict[str, Any]],
    issues: tuple[TruthIssue, ...],
    matched: tuple[tuple[int, str], ...],
) -> Counter[tuple[str, str, str]]:
    """Label unmatched claims and issues using the scorer's actual matches.

    >>> issue = TruthIssue("I1", "fx_rate", ("D1",), 100, "KZT", (("D1", "FX1"),))
    >>> finding = {
    ...     "type": "fx_rate", "affected_ids": ["D1"], "claimed_amount_minor": 102,
    ...     "currency": "KZT", "evidence_ids": ["D1", "FX1"], "explanation": "",
    ... }
    >>> payload = {"episode_id": "EP", "findings": [finding]}
    >>> report = score(payload, "EP", [issue], {}, 0)
    >>> counts = _causes([normalize_finding(finding, {})], (issue,), report.matched)
    >>> counts["FP", "fx_rate", "Amount outside tolerance"]
    1
    >>> counts["FN", "fx_rate", "Amount outside tolerance"]
    1
    """
    counts: Counter[tuple[str, str, str]] = Counter()
    used_findings = {index for index, _ in matched}
    used_issues = {issue_id for _, issue_id in matched}
    for index, finding in enumerate(findings):
        if index not in used_findings:
            candidates = [cause for issue in issues if (cause := _mismatch(finding, issue))]
            _, reason = min(candidates, default=(6, "No corresponding issue"))
            counts["FP", finding["type"], reason] += 1
    for issue in issues:
        if issue.issue_id not in used_issues:
            candidates = [cause for finding in findings if (cause := _mismatch(finding, issue))]
            _, reason = min(candidates, default=(6, "No corresponding submission"))
            counts["FN", issue.type, reason] += 1
    return counts


def _check_case(
    run: dict[str, Any], config: dict[str, Any], terminal: dict[str, Any]
) -> tuple[Counter[str], Counter[tuple[str, str, str]]]:
    public, truth = generate_episode(run["seed"], ScenarioConfig.from_dict(config))
    episode_id = truth.episode_id
    if episode_id != run["episode_id"]:
        raise ValueError(f"regenerated episode differs for seed {run['seed']}")
    aliases = {row["invoice_id"]: row["doc_id"] for row in public.invoices}
    aliases.update({row["payment_id"]: row["doc_id"] for row in public.payments})
    if terminal["truncated"]:
        payload = {"episode_id": episode_id, "findings": []}
        inspection_steps = terminal["step"]
    else:
        if terminal["action"]["tool"] != "submit":
            raise ValueError("episode terminated without a reconciler submission")
        payload = terminal["action"]["args"]
        inspection_steps = terminal["step"] - 1
    report = score(payload, episode_id, list(truth.issues), aliases, inspection_steps)
    compared = (
        "valid",
        "tp",
        "fp",
        "fn",
        "precision",
        "recall",
        "f1",
        "inspection_steps",
        "reward",
    )
    if terminal["step"] != run["steps"] or any(
        getattr(report, name) != run[name] for name in compared
    ):
        raise ValueError(f"recorded and replayed scores differ for seed {run['seed']}")
    issues = Counter(issue.type for issue in truth.issues)
    if not report.valid:
        return issues, Counter(
            {("FN", kind, "Malformed submission"): n for kind, n in issues.items()}
        )
    findings = [
        normalize_finding(finding, aliases) for finding in validate_submission(payload, episode_id)
    ]
    failures = _causes(findings, truth.issues, report.matched)
    return issues, failures


def _report(benchmark: Path) -> str:
    metrics = json.loads((benchmark / "metrics.json").read_text(encoding="utf-8"))
    terminals = _terminals(benchmark / "trajectories.jsonl")
    by_split = {}
    by_type: Counter[str] = Counter()
    causes: Counter[tuple[str, str, str]] = Counter()
    for split, group in metrics["splits"].items():
        configs = {case["seed"]: case["config"] for case in metrics["cases"][split]}
        runs = group["reconciler"]["runs"]
        by_split[split] = len(runs), *(sum(run[key] for run in runs) for key in ("tp", "fp", "fn"))
        for run in runs:
            terminal = terminals.pop((split, run["episode_id"]), None)
            if terminal is None:
                raise ValueError(f"missing reconciler terminal for {split} seed {run['seed']}")
            issues, failures = _check_case(run, configs[run["seed"]], terminal)
            by_type.update(issues)
            causes.update(failures)
    if terminals:
        raise ValueError(
            "reconciler trajectories include episodes absent from the benchmark metrics"
        )
    return _markdown(by_split, by_type, causes)


def _markdown(
    by_split: dict[str, tuple[int, ...]],
    by_type: Counter[str],
    causes: Counter[tuple[str, str, str]],
) -> str:
    lines = [
        "# Reconciler failure analysis",
        "",
        "Scored the recorded reconciler submissions again against truth regenerated from the "
        "benchmark case recipes. The replayed scores matched the recorded metrics for every case.",
        "",
        "| Split | Episodes | True positives | False positives | False negatives |",
        "|---|---:|---:|---:|---:|",
    ]
    for split, (episodes, tp, fp, fn) in by_split.items():
        lines.append(f"| {split} | {episodes} | {tp} | {fp} | {fn} |")
    lines += [
        "",
        "| Fault type | Expected issues | False positives | False negatives |",
        "|---|---:|---:|---:|",
    ]
    for kind in ERROR_TYPES:
        fp = sum(n for (label, fault, _), n in causes.items() if label == "FP" and fault == kind)
        fn = sum(n for (label, fault, _), n in causes.items() if label == "FN" and fault == kind)
        lines.append(f"| {kind} | {by_type[kind]} | {fp} | {fn} |")
    if causes:
        lines += ["", "| Outcome | Fault type | Measured cause | Count |", "|---|---|---|---:|"]
        for (label, kind, reason), n in sorted(causes.items()):
            lines.append(f"| {label} | {kind} | {reason} | {n} |")
    else:
        lines += ["", "No false positives or false negatives were observed on these cases."]
    return "\n".join([*lines, ""])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=Path("outputs/benchmarks"))
    parser.add_argument("--out", type=Path, default=Path("outputs/reports/failure_analysis.md"))
    args = parser.parse_args()
    report = _report(args.benchmark)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
