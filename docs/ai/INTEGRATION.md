# Integration log

Merge procedure (Claude): `git diff main...agent/<task>`, check ownership, `make verify` on the
branch, merge one branch at a time with `--no-ff`, record here.

## 2026-11-21 — slice (Claude, main)
Commands: `make verify` → ruff clean, pytest all passed (count in commit message), demo 3/3
`reward=1.000 replay=identical`. Docker: see entry below once built.

## 2026-11-21 — CX-01 (Codex, agent/cx-01)

- `uv sync --frozen && make lint test` passed on the 104-test baseline.
- `uv run pytest -o addopts='' -q tests/test_env.py -k 'evaluator_crash or evaluator_times_out or close_releases or clock_limit or get_document'` reproduced seven failures and one pass before the fix.
- `uv run pytest -o addopts='' -q tests/test_env.py` passed all 26 environment tests after the fix.
- `make lint test && uv run pytest -o addopts='' -q` passed after review feedback with clean Ruff checks and 112 passing tests.
- Claude Opus code review approved the change. The deadline test now uses a manually advanced clock. The 10-second IPC deadline also covers episode generation.
