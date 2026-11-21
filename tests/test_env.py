import pytest

from ledgerforge.contracts.schemas import MAX_STEPS
from ledgerforge.env.calculator import CalcError, calculate


def test_pagination_has_stable_cursors(env):
    env.reset(1)
    seen, cursor = [], None
    while True:
        obs, *_ = env.step({"tool": "list_records", "args": {"table": "ledger", "cursor": cursor}})
        seen += [r["row_id"] for r in obs["result"]["rows"]]
        cursor = obs["result"]["next_cursor"]
        if cursor is None:
            break
    assert seen == [r["row_id"] for r in env._data["ledger"]]


def test_lookups_and_bounded_errors_consume_steps(env):
    env.reset(1)
    fx = env._data["fx"][0]
    key = f"{fx['date']}:{fx['source_currency']}:{fx['target_currency']}"
    obs, *_ = env.step({"tool": "get_record", "args": {"table": "fx", "id": key}})
    assert obs["result"] == fx
    obs, *_ = env.step({"tool": "get_record", "args": {"table": "ledger", "id": "nope"}})
    assert obs["error"]["code"] == "not_found" and obs["steps_remaining"] == MAX_STEPS - 2
    obs, *_ = env.step({"tool": "rm -rf", "args": {}})
    assert obs["error"]["code"] == "unknown_tool"
    obs, *_ = env.step("garbage")
    assert "error" in obs and obs["steps_remaining"] == MAX_STEPS - 4


def test_step_limit_truncates_and_scores_empty_submission(env):
    env.reset(1)  # clean episode: empty submission is perfect, minus 100 inspection steps
    for _ in range(MAX_STEPS):
        obs, reward, terminated, truncated, info = env.step(
            {"tool": "calculator", "args": {"expression": "1+1"}}
        )
    assert truncated and not terminated and reward == pytest.approx(1 - 0.2)
    obs, reward, *_ = env.step({"tool": "calculator", "args": {"expression": "1"}})
    assert obs["error"]["code"] == "episode_over" and reward == 0.0


def test_eval_mode_withholds_reward():
    from ledgerforge.env.env import AuditEnv

    e = AuditEnv("eval")
    try:
        _, info = e.reset(1)
        sub = {"episode_id": info["episode_id"], "findings": []}
        _, reward, terminated, _, step_info = e.step({"tool": "submit", "args": sub})
        assert terminated and reward == 0.0 and step_info == {}
        assert e.evaluator.call({"cmd": "report"})["reports"][0]["reward"] == 0.0 + 1.0
    finally:
        e.close()


@pytest.mark.parametrize(
    "expr,value", [("1+2*3", "7"), ("(10-4)/4", "1.5"), ("-2.5*2", "-5"), ("0.1+0.2", "0.3")]
)
def test_calculator(expr, value):
    assert calculate(expr) == value


@pytest.mark.parametrize(
    "expr", ["__import__('os')", "2**10", "a+1", "1/0", "x" * 300, "", "[1]", "1 if 1 else 2"]
)
def test_calculator_rejects(expr):
    with pytest.raises(CalcError):
        calculate(expr)


def test_cannot_submit_twice(env):
    _, info = env.reset(7, {"faults": {"duplicate_invoice": 1}})
    sub = {"episode_id": info["episode_id"], "findings": []}
    _, first, *_ = env.step({"tool": "submit", "args": sub})
    obs, second, terminated, _, _ = env.step({"tool": "submit", "args": sub})
    assert first == -1.0 and second == 0.0 and obs["error"]["code"] == "episode_over"


def test_malformed_submit_terminates_with_minus_one(env):
    env.reset(1)
    _, reward, terminated, truncated, info = env.step({"tool": "submit", "args": {"x": 1}})
    assert terminated and not truncated and reward == -1.0 and not info["report"]["valid"]
