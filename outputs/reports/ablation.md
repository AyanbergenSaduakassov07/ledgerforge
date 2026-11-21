# Rule ablation

Reconciler on train + dev + mirror (40 episodes). Each row swaps the named
published rule for a shallow heuristic (see `agents/reconciler.py`). Measured by
`uv run python -m ledgerforge.benchmark.ablation`.

| Variant | TP | FP | FN | mean F1 | mean reward |
|---|---:|---:|---:|---:|---:|
| reconciler | 71 | 0 | 0 | 1.000 | 0.953 |
| naive_duplicates | 71 | 120 | 0 | 0.418 | -0.201 |
| naive_period | 71 | 81 | 0 | 0.487 | -0.064 |
| naive_fx | 40 | 888 | 31 | 0.083 | -0.866 |
| naive_allocation | 64 | 469 | 7 | 0.199 | -0.640 |
| naive_allocation+duplicates+fx+period | 27 | 1101 | 44 | 0.045 | -0.939 |
