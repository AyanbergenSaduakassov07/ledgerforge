# CLAUDE.md — LedgerForge

Role: Claude is lead architect and owns `contracts/`, `sim/`, `verification/`, `schemas/` and `docs/`
(except Codex task reports). Codex owns `env/`, `evaluation/`, `agents/`, `benchmark/` from task
CX-01 on (ADR-012). Shared rules: `AGENTS.md`.

- Commands: `make verify` (all), `uv run pytest -q`, `uv run ruff check . && uv run ruff format --check .`.
  The rtk wrapper hides pytest counts; use `--junitxml` to a scratch file for exact totals.
- Contract changes: update `docs/CONTRACTS.md`, `schemas/`, `tests/test_contracts.py` and add an ADR together.
- Generator changes must keep `tests/test_generator.py::test_truth_equals_independent_audit` green (acceptance gate).
- Do not read `docs/MASTER_SPEC.md` whole (≈53 KB): `grep -n '^#' docs/MASTER_SPEC.md`, then the section.
- Integrate Codex branches one at a time: review diff, run `make verify`, merge, record in `docs/ai/INTEGRATION.md`.
