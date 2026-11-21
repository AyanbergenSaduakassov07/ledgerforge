import subprocess
import sys

import pytest

from ledgerforge.contracts.schemas import MAX_STEPS
from ledgerforge.env import env as env_module
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


def test_evaluator_crash_raises_a_clean_error(env):
    env.reset(1)
    proc = env.evaluator._proc
    proc.kill()
    proc.wait(timeout=5)

    with pytest.raises(RuntimeError, match="evaluator connection lost"):
        env.step({"tool": "submit", "args": {}})
    obs, *_ = env.step({"tool": "submit", "args": {}})
    assert obs["error"]["code"] == "episode_over"


def test_evaluator_times_out_on_incomplete_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    popen = subprocess.Popen

    def start_slow_child(_command: list[str], **kwargs) -> subprocess.Popen:
        return popen(
            [
                sys.executable,
                "-c",
                "import sys, time; sys.stdin.readline(); "
                "sys.stdout.write('{'); sys.stdout.flush(); time.sleep(2)",
            ],
            **kwargs,
        )

    monkeypatch.setattr(subprocess, "Popen", start_slow_child)
    monkeypatch.setattr(env_module, "_EVALUATOR_TIMEOUT_S", 0.25, raising=False)
    client = env_module.EvaluatorClient()
    try:
        with pytest.raises(RuntimeError, match="evaluator request timed out"):
            client.call({"cmd": "report"})
        assert client._proc.poll() is not None
    finally:
        client.close()


def test_close_releases_the_evaluator_pipes_and_is_idempotent(env):
    env.reset(1)
    proc = env.evaluator._proc
    env.close()
    env.close()
    assert proc.poll() is not None
    assert proc.stdin.closed and proc.stdout.closed


def test_submit_at_the_clock_limit_truncates_with_an_empty_submission() -> None:
    now = 0.0
    env = env_module.AuditEnv(clock=lambda: now)
    try:
        _, info = env.reset(1)
        now = 59.0
        _, _, terminated, truncated, _ = env.step(
            {"tool": "calculator", "args": {"expression": "1"}}
        )
        assert not terminated and not truncated

        now = 60.0
        _, reward, terminated, truncated, info = env.step(
            {"tool": "submit", "args": {"episode_id": info["episode_id"], "findings": [{}]}}
        )
        assert truncated and not terminated and reward == pytest.approx(0.998)
        assert info["report"]["inspection_steps"] == 1
    finally:
        env.close()


@pytest.mark.parametrize("args", [{}, {"doc_id": 12}, {"doc_id": " "}])
def test_get_document_requires_a_nonempty_string(env, args: dict) -> None:
    env.reset(1)
    obs, *_ = env.step({"tool": "get_document", "args": args})
    assert obs["error"] == {"code": "bad_args", "message": "doc_id must be a non-empty string"}
    assert obs["steps_remaining"] == MAX_STEPS - 1


def test_get_document_distinguishes_known_and_unknown_ids(env):
    initial, _ = env.reset(1)
    obs, *_ = env.step({"tool": "get_document", "args": {"doc_id": "manifest"}})
    assert obs["result"] == initial["manifest"]
    obs, *_ = env.step({"tool": "get_document", "args": {"doc_id": "nope"}})
    assert obs["error"]["code"] == "not_found"


def test_wrong_config_type_is_an_error_not_a_dead_evaluator(env):
    with pytest.raises(RuntimeError, match="evaluator: .*interaction"):
        env.reset(1, {"interactions": ["fx_with_period"]})
    obs, _ = env.reset(1)  # the same evaluator process still serves episodes
    assert obs["steps_remaining"] == MAX_STEPS
