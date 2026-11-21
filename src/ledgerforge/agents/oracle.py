"""Oracle policy (trusted runner side only): submits the private truth at its first action.

It is constructed with the PrivateTruthBundle by the benchmark runner, never by the environment,
so the agent-facing process still never holds truth. Expected reward: 1.0 (zero inspections).
"""

from __future__ import annotations

from typing import Any

from ledgerforge.contracts.schemas import PrivateTruthBundle


class OraclePolicy:
    name = "oracle"

    def __init__(self, truth: PrivateTruthBundle) -> None:
        self.truth = truth

    def reset(self, observation: dict[str, Any]) -> None:
        if observation["manifest"]["episode_id"] != self.truth.episode_id:
            raise ValueError("oracle truth belongs to a different episode")

    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        findings = [
            {
                "type": t.type,
                "affected_ids": list(t.affected_ids),
                "claimed_amount_minor": t.expected_amount_minor,
                "currency": t.currency,
                "evidence_ids": list(t.allowed_evidence_sets[0]),
                "explanation": f"oracle: {t.type}",
            }
            for t in self.truth.issues
        ]
        submission = {"episode_id": self.truth.episode_id, "findings": findings}
        return {"tool": "submit", "args": submission}
