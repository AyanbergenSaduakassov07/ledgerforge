import pytest

from ledgerforge.contracts.schemas import TruthIssue
from ledgerforge.evaluation.matcher import reward_from, score

T1 = TruthIssue(
    "ISS-01", "duplicate_invoice", ("DOC-A", "DOC-B"), 1000, "KZT", (("DOC-A", "DOC-B", "R1"),)
)
FX_ID = "2025-01-02:USD:KZT"
T2 = TruthIssue("ISS-02", "fx_rate", ("DOC-C",), 55, "KZT", (("DOC-C", "R2", FX_ID),))
ALIASES = {"INV-1": "DOC-A"}


def finding(t, **kw):
    f = {
        "type": t.type,
        "affected_ids": list(t.affected_ids),
        "claimed_amount_minor": t.expected_amount_minor,
        "currency": t.currency,
        "evidence_ids": list(t.allowed_evidence_sets[0]),
        "explanation": "",
    }
    return {**f, **kw}


def run(findings, truth=(T1, T2), steps=0):
    return score({"episode_id": "EP", "findings": findings}, "EP", list(truth), ALIASES, steps)


def test_perfect_submission():
    r = run([finding(T1), finding(T2)])
    assert (r.tp, r.fp, r.fn, r.f1, r.reward) == (2, 0, 0, 1.0, 1.0)


def test_repeat_is_false_positive():
    r = run([finding(T1), finding(T1)], truth=(T1,))
    assert (r.tp, r.fp, r.fn) == (1, 1, 0)
    assert r.f1 == pytest.approx(2 / 3)


@pytest.mark.parametrize(
    "change",
    [
        {"type": "fx_rate"},
        {"affected_ids": ["DOC-A"]},
        {"claimed_amount_minor": 1002},
        {"currency": "USD"},
        {"evidence_ids": ["DOC-A", "DOC-B"]},
    ],
)
def test_each_criterion_is_required(change):
    assert run([finding(T1, **change)], truth=(T1,)).tp == 0


def test_tolerance_alias_case_order_and_sign_normalisation():
    f = finding(
        T1,
        type=" Duplicate_Invoice ",
        affected_ids=["DOC-B", "INV-1"],
        claimed_amount_minor=-1001,
        currency="kzt",
        evidence_ids=["R1", "INV-1", "DOC-B", "extra"],
    )
    assert run([f], truth=(T1,)).tp == 1


def test_empty_truth_and_empty_findings_is_one():
    assert run([], truth=()).f1 == 1.0


@pytest.mark.parametrize(
    "findings,truth,expected",
    [
        ([], (), (0.0, 0.0, 1.0)),  # clean books, silent: only F1 is defined as 1
        ([], (T1,), (0.0, 0.0, 0.0)),  # no findings: P has a zero denominator
        ([finding(T1)], (), (0.0, 0.0, 0.0)),  # no truth: R has a zero denominator
        ([finding(T1)], (T1,), (1.0, 1.0, 1.0)),
    ],
)
def test_precision_recall_with_zero_denominators(findings, truth, expected):
    r = run(findings, truth=truth)
    assert (r.precision, r.recall, r.f1) == expected


def test_findings_on_clean_episode_is_zero_f1():
    r = run([finding(T1)], truth=())
    assert r.f1 == 0.0 and r.reward == -1.0


def test_malformed_submission_is_minus_one():
    r = score({"episode_id": "EP"}, "EP", [T1], ALIASES, 0)
    assert not r.valid and r.reward == -1.0
    r = score({"episode_id": "OTHER", "findings": []}, "EP", [T1], ALIASES, 0)
    assert r.reward == -1.0


def test_reward_clips_and_penalises_steps():
    assert reward_from(1.0, 0) == 1.0
    assert reward_from(1.0, 50) == pytest.approx(0.9)
    assert reward_from(0.0, 99) == -1.0
