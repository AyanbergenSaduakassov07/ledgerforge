# Ownership

| Path | Owner | Notes |
|---|---|---|
| `src/ledgerforge/contracts/`, `schemas/` | Claude | frozen; changes need ADR |
| `src/ledgerforge/sim/`, `src/ledgerforge/verification/` | Claude | generation + acceptance gate |
| `src/ledgerforge/env/`, `src/ledgerforge/evaluation/` | Codex (from CX-01) | slice written by Claude (ADR-012) |
| `src/ledgerforge/agents/`, `src/ledgerforge/benchmark/` | Codex | oracle stays evaluator-side |
| `src/ledgerforge/cli.py` | shared | add subcommands, don't rename existing ones |
| `tests/test_generator.py`, `tests/test_contracts.py` | Claude | |
| `tests/test_env.py`, `tests/test_matcher.py`, `tests/test_slice.py`, new benchmark/security tests | Codex | may add, never weaken assertions |
| `docs/` except `docs/ai/INTEGRATION.md` task reports | Claude | |
| `Makefile`, `pyproject.toml`, `uv.lock`, `Dockerfile` | Claude; Codex may propose in PR | runtime deps stay `[]` |
