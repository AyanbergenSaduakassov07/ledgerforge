# LedgerForge benchmark

Each metric is the mean across episodes. Runtime covers reset through termination.
Mirror policies ran in eval mode. The trusted runner collected scores after the split.
Paired oracle and reconciler runs were replayed in memory. Trajectories contain public-policy actions.

| Split | Policy | Episodes | Precision | Recall | F1 | Reward | Inspection steps | Runtime (s) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| train | random_explorer | 10 | 0.000 | 0.000 | 0.200 | -0.603 | 8.00 | 0.1293 |
| train | reconciler | 10 | 0.800 | 0.800 | 1.000 | 0.956 | 22.20 | 0.0722 |
| train | flag_all | 10 | 0.000 | 0.000 | 0.000 | -1.000 | 2.00 | 0.0560 |
| train | oracle | 10 | 0.800 | 0.800 | 1.000 | 1.000 | 0.00 | 0.0531 |
| dev | random_explorer | 10 | 0.000 | 0.000 | 0.200 | -0.603 | 8.00 | 0.1335 |
| dev | reconciler | 10 | 0.800 | 0.800 | 1.000 | 0.955 | 22.30 | 0.0622 |
| dev | flag_all | 10 | 0.000 | 0.000 | 0.000 | -1.000 | 2.00 | 0.0644 |
| dev | oracle | 10 | 0.800 | 0.800 | 1.000 | 1.000 | 0.00 | 0.0512 |
| mirror | random_explorer | 20 | 0.000 | 0.000 | 0.250 | -0.504 | 8.00 | 0.0999 |
| mirror | reconciler | 20 | 0.750 | 0.750 | 1.000 | 0.950 | 25.05 | 0.0832 |
| mirror | flag_all | 20 | 0.000 | 0.000 | 0.000 | -1.000 | 2.00 | 0.0685 |
| mirror | oracle | 20 | 0.750 | 0.750 | 1.000 | 1.000 | 0.00 | 0.0658 |

Replay, public record and oracle finding equivalence, and oracle reward invariance passed on 20/20 combined ID and order transformations.
