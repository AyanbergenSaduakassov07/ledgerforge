# Security and isolation

An untrusted policy may try to read private truth, inflate its reward, or disrupt the host.

| Control | Where | Tested |
|---|---|---|
| Truth only in the evaluator OS process; env gets public data | `evaluation/service.py`, `env/env.py` | `test_agent_process_never_receives_truth` |
| `episode_id` derived from RNG, not seed | `sim/episode.py` | `test_episode_id_does_not_reveal_seed` |
| Strict submission schema, size caps (30 findings, 10 ids, 1000 chars) | `contracts/submission.py` | `test_contracts` |
| One scored submission per episode | evaluator + env | `test_cannot_submit_twice` |
| Eval mode withholds reward and report | env, evaluator | `test_env` |
| Calculator: AST whitelist, no names/calls/attrs, ≤256 chars, depth ≤32, Decimal | `env/calculator.py` | `test_env` |
| Step limit 100, 60 s limit, page ≤50 | `env/env.py` | `test_env` |
| Evaluator returns errors for invalid requests and keeps serving | `service.main` | `test_adversarial` |
| Offline execution and standard-library runtime | `pyproject.toml`; Docker `--network none` | Offline container verification |
| Private files git-ignored | `.gitignore` | — |

Known limits: the agent runs in the same OS user as the evaluator, so a malicious in-process agent
could read `/proc` or spawn its own generator with the same seed. Official grading must run the
agent in its own sandbox/container and the evaluator outside it; with released generator code,
security rests on unseen evaluation seeds. Scoring ignores submission explanations.
