# Evaluation

Scoring rules: CONTRACTS §5–6. Reward `clip(2·F1 − 1 − 0.002·inspection_steps, −1, 1)` — fixed, do
not change. Inspection steps = non-submit steps; on truncation all steps.

| Situation | Reward |
|---|---|
| Perfect findings, k inspection steps | 1 − 0.002k |
| Empty submission on clean books | 1 − 0.002k |
| Empty submission on flawed books | −1 |
| Any findings on clean books | −1 − 0.002k → −1 |
| Malformed submission | −1 |
| Truncated at 100 steps, clean / flawed | 0.8 / −1 |

## Adversarial checks (spec §11.4)

| Check | Test | Status |
|---|---|---|
| Perfect beats silence on flawed books | `test_slice` oracle 1.0 vs empty −1 | done |
| Silence beats false accusations on clean books | `test_matcher` empty/clean cases | done |
| Repeats don't add reward | `test_matcher` repeat = FP | done |
| Flag-all scores poorly | `test_adversarial::test_flagging_everything_has_negative_mean_reward` | done |
| Invalid evidence / wrong ids / currency / amount never TP | `test_matcher` each criterion | done |
| Malformed → −1 | `test_contracts`, `test_env` | done |
| Inspection cost small between equal results | `test_inspection_steps_are_penalised` | done |
| No second submit | `test_cannot_submit_twice` | done |
| Order invariance of equivalent submissions | `test_adversarial::test_reward_is_invariant_across_twenty_finding_permutations` | done |
| Persuasive explanation can't rescue a wrong amount | `test_adversarial::test_persuasive_explanation_does_not_rescue_a_wrong_amount` | done |

## Benchmark (planned, Codex)

Policies: random explorer, simple reconciler, flag-all attacker, evaluator-side oracle. Data: 10
train, 10 dev, local closed-eval mirror of 20 (≥5 clean, ≥5 interacting) + 20 paired id/order
transforms. Per policy report precision, recall, F1, reward, steps, runtime, failure categories —
measured only, from committed raw outputs in `outputs/benchmarks/`.
