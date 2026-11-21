"""Published matcher and reward. Deterministic; the same code scores every policy.

A finding matches a truth issue when ALL hold:
  type equal; affected_ids equal as sets (business ids normalised to doc ids);
  |claimed - expected| <= AMOUNT_TOLERANCE_MINOR (claimed by absolute value); currency equal;
  evidence_ids contain at least one allowed evidence set completely.
Matching is one-to-one maximum bipartite matching (Kuhn), visiting findings in submission order
and truth in issue_id order, so ties resolve deterministically. Unmatched findings (including
repeats of an already matched issue) are FP; unmatched truth issues are FN.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ledgerforge.contracts.schemas import AMOUNT_TOLERANCE_MINOR, TruthIssue
from ledgerforge.contracts.submission import (
    MalformedSubmission,
    normalize_finding,
    validate_submission,
)

STEP_PENALTY = 0.002


@dataclass(frozen=True)
class ScoreReport:
    episode_id: str
    valid: bool
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    inspection_steps: int
    reward: float
    matched: tuple[tuple[int, str], ...]  # (finding index, issue_id)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compatible(f: dict[str, Any], t: TruthIssue) -> bool:
    return (
        f["type"] == t.type
        and f["affected_ids"] == frozenset(t.affected_ids)
        and abs(f["claimed_amount_minor"] - t.expected_amount_minor) <= AMOUNT_TOLERANCE_MINOR
        and f["currency"] == t.currency
        and any(set(s) <= f["evidence_ids"] for s in t.allowed_evidence_sets)
    )


def match(findings: list[dict[str, Any]], truth: list[TruthIssue]) -> list[tuple[int, str]]:
    edges = [[j for j, t in enumerate(truth) if compatible(f, t)] for f in findings]
    owner: dict[int, int] = {}  # truth index -> finding index

    def augment(i: int, seen: set[int]) -> bool:
        for j in edges[i]:
            if j not in seen:
                seen.add(j)
                if j not in owner or augment(owner[j], seen):
                    owner[j] = i
                    return True
        return False

    for i in range(len(findings)):
        augment(i, set())
    return sorted((i, truth[j].issue_id) for j, i in owner.items())


def reward_from(f1: float, inspection_steps: int) -> float:
    return max(-1.0, min(1.0, 2 * f1 - 1 - STEP_PENALTY * inspection_steps))


def score(
    payload: Any,
    episode_id: str,
    truth: list[TruthIssue],
    aliases: dict[str, str],
    inspection_steps: int,
) -> ScoreReport:
    try:
        raw = validate_submission(payload, episode_id)
    except MalformedSubmission as e:
        return ScoreReport(
            episode_id, False, 0, 0, len(truth), 0.0, 0.0, 0.0, inspection_steps, -1.0, (), str(e)
        )
    findings = [normalize_finding(f, aliases) for f in raw]
    truth = sorted(truth, key=lambda t: t.issue_id)
    matched = match(findings, truth)
    tp = len(matched)
    fp, fn = len(findings) - tp, len(truth) - tp
    f1 = 1.0 if not findings and not truth else 2 * tp / (2 * tp + fp + fn)
    precision = tp / len(findings) if findings else float(not truth)
    recall = tp / len(truth) if truth else 1.0
    return ScoreReport(
        episode_id,
        True,
        tp,
        fp,
        fn,
        precision,
        recall,
        f1,
        inspection_steps,
        reward_from(f1, inspection_steps),
        tuple(matched),
    )
