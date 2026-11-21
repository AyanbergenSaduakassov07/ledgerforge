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

## 2026-11-21 — CX-04 (Codex, agent/cx-04)

- `uv run ledgerforge bench --out /private/tmp/ledgerforge-codex.ELz8P7/red` initially exited 2 because the command was absent.
- `uv run ledgerforge bench --out /private/tmp/ledgerforge-codex.ELz8P7/run-d` completed 160 policy runs on 10 train, 10 dev, and 20 mirror cases. All 20 combined ID and order transformations passed. The committed outputs are from this run.
- `uv run python /private/tmp/ledgerforge-codex.ELz8P7/check_benchmark.py /private/tmp/ledgerforge-codex.ELz8P7/run-b /private/tmp/ledgerforge-codex.ELz8P7/run-d` verified 120 public trajectories, zero agent-visible rewards in mirror mode, 20 passing paired checks, identical trajectory bytes, and identical metrics excluding runtime.
- Claude Opus approved the runner and raw-output accounting. The Markdown table reports inspection steps as specified. Oracle actions stayed in memory and out of the public trajectory file.
- `make lint test && uv run pytest -o addopts='' -q` passed after rebasing onto main and applying the review note. Ruff was clean and all 159 tests passed.

## 2026-11-21 — merged agent/cx-04 into main (Claude)
- Reviewed `benchmark/run.py`: truth only reaches OraclePolicy on the trusted runner side; mirror policies run in eval mode.
- `make verify` exit 0. `uv run ledgerforge bench` exit 0. Rerun gives identical precision, recall, F1, reward and steps (runtime differs), and `trajectories.jsonl` is byte-identical.
- Finding: the reconciler reaches F1 1.000 on train, dev and mirror. This is documented in the README as rule saturation, not general ability.
## 2026-11-21 — CX-05 (Codex, agent/cx-05)

- `uv run python -m ledgerforge.benchmark.analyze --benchmark /private/tmp/ledgerforge-codex.ELz8P7/run-a --out /private/tmp/ledgerforge-codex.ELz8P7/failure-analysis-red.md` initially failed because the analyzer module was absent.
- `uv run python -m ledgerforge.benchmark.analyze` reproduced all 40 scores from the committed benchmark. The report recorded 71 true positives, zero false positives, and zero false negatives.
- `uv run python -m doctest -v src/ledgerforge/benchmark/analyze.py` passed seven checks for a finding outside the amount tolerance.
- `uv run python /private/tmp/ledgerforge-codex.ELz8P7/check_analysis.py outputs/benchmarks outputs/reports/failure_analysis.md /private/tmp/ledgerforge-codex.ELz8P7` confirmed a byte-identical report, the controlled false positive and false negative, and rejection of inconsistent metrics and missing terminals. The missing-terminal diagnostic check failed before its fix.
- Claude Opus approved the analyzer. The review follow-ups added the persistent regression example and the missing-terminal diagnostic.
- `uv run ledgerforge demo --count 3 --out /private/tmp/ledgerforge-codex.ELz8P7/final-demo.jsonl` returned reward 1.000 and identical replay for all three episodes.
- After `git rebase main`, `make lint test && uv run pytest -o addopts='' -q` passed with clean Ruff checks and 160 passing tests.

## cl-07 generator 0.2.0 (ADR-015)
- Allocation faults now target foreign-currency payments too; fixed the latent units bug (moved amount drawn from the base-currency AP row).
- Episodes regenerated; benchmark: reconciler dev F1 1.000, train 0.980, mirror 0.983 (3 FN, 0 FP). Reconciler test now asserts 0 FP and tolerates FN only on allocation faults.
