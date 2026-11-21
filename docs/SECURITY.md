# Security and isolation

An untrusted policy may try to read private truth, inflate its reward, or disrupt the host.

| Control | Where | Tested |
|---|---|---|
| Truth only in the evaluator OS process; env gets public data | `evaluation/service.py`, `env/env.py` | `test_agent_process_never_receives_truth` |
| `episode_id` derived from RNG, not seed | `sim/episode.py` | `test_episode_id_does_not_reveal_seed` |
| `LEDGERFORGE_SECRET` keys every RNG stream, id salt and `episode_id` (HMAC-SHA256); seed search fails | `sim/secret.py`, `sim/world.py`, `sim/salt.py` | `test_secret` |
| `env/` and `agents/` never import the key module | static + fresh-interpreter check | `test_agent_side_never_touches_the_key` |
| Strict submission schema, size caps (30 findings, 10 ids, 1000 chars) | `contracts/submission.py` | `test_contracts` |
| One scored submission per episode | evaluator + env | `test_cannot_submit_twice` |
| Eval mode withholds reward and report until `finalize`; `reset`/`score` rejected after it | env, evaluator | `test_eval_mode_report_requires_finalize` |
| Calculator: AST whitelist, no names/calls/attrs, ≤256 chars, depth ≤32, Decimal | `env/calculator.py` | `test_env` |
| Step limit 100, 60 s limit, page ≤50 | `env/env.py` | `test_env` |
| Evaluator returns errors for invalid requests and keeps serving | `service.main` | `test_adversarial` |
| Offline execution and standard-library runtime | `pyproject.toml`; Docker `--network none` | Offline container verification |
| Private files git-ignored | `.gitignore` | — |

## Closed evaluation key

Without a key, every random stream is `Random("ledgerforge:{seed}:{attempt}:{phase}")`. An agent
that sees `episode_id` in the manifest can search seeds with the open generator until the id
matches, then rebuild the private truth. For closed grading the jury sets `LEDGERFORGE_SECRET`
in the evaluator's environment. Every seed string then becomes
`HMAC-SHA256(key, "ledgerforge:{seed}:{attempt}:{phase}")`, which covers the world, fault and
order streams, the stream that draws `episode_id`, and the `id_salt` digit permutation. Without
the key, neither the seed nor the episode can be recovered. An empty key leaves the generator
byte-identical, so the committed open episodes do not change.

```bash
docker run --rm --network none -e LEDGERFORGE_SECRET="<jury-only key>" ledgerforge
```

Only `sim/` and `evaluation/` read the key. An evaluator started in eval mode without it prints a
warning to stderr, which never reaches agent observations.

Known limits: the agent runs in the same OS user as the evaluator, so a malicious in-process agent
could read `/proc` or the evaluator's environment. Official grading must run the agent in its own
sandbox/container and the evaluator, with `LEDGERFORGE_SECRET`, outside it. Scoring ignores
submission explanations.
