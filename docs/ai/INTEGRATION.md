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

## 2026-11-21 — merged agent/cl-01 and agent/cx-01 into main (Claude)
- cl-01: id_salt digit derangement + size gate (CL-01, CL-03); 10 train + 10 dev open episodes (CL-02).
- cx-01: reviewed diff (env.py evaluator timeouts/EOF handling, injectable clock, deadline check
  before each step, get_document arg validation); within owned files, no contract change.
- On main after both merges: `uv run ruff check . && uv run ruff format --check .` clean;
  `uv run pytest` 131 passed, 0 failed; `uv run ledgerforge demo --count 3` 3/3 reward=1.000 replay=identical.
- Codex: rebase agent/cx-02 on main before review (`git rebase main`); CX-04 can now use episodes/splits.json.

## 2026-11-21 — CX-02 (Codex, agent/cx-02)

- `uv sync --frozen --offline && make lint test` passed on the original baseline.
- `uv run pytest -o addopts='' -q tests/test_baselines.py::test_baseline_imports_stay_on_the_agent_side` initially failed because the policy modules were absent.
- `uv run pytest -o addopts='' -q tests/test_baselines.py` passed all 25 checks. All three policies terminated within budget and repeated identically on five seeds. The import guard also ran their policies in a fresh interpreter.
- Claude Opus approved the policy diff. Allocation checks cover base-currency remittances, the generator's current allocation-fault scope.
- `git rebase main` incorporated CL-01/02/03 and CX-01. `make lint test && uv run pytest -o addopts='' -q` then passed with clean Ruff checks and 156 passing tests.

## 2026-11-21 — CX-03 (Codex, agent/cx-03)

- `uv run pytest -o addopts='' -q tests/test_adversarial.py` passed all three tests. They cover 10 faulted and five clean episodes, 20 distinct finding permutations, and a persuasive claim outside the one-minor-unit tolerance.
- `git rebase agent/cx-02` incorporated the baseline policies. `make lint test && uv run pytest -o addopts='' -q` passed with clean Ruff checks and 159 passing tests.
- Claude Opus approved the test suite. The test now labels the frozen amount tolerance explicitly.

## 2026-11-21 — merged agent/cx-03 (contains cx-02) into main (Claude)
- Reviewed: baselines (flag_all, random_explorer, reconciler) import only `contracts.*`; no truth, evaluator or auditor imports.
- On main: ruff clean; `uv run pytest` 159 passed, 0 failed (3.3 s).
