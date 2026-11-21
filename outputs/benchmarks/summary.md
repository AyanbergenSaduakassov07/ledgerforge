# LedgerForge benchmark

Each metric is the mean across episodes. Runtime covers reset through termination.
Mirror policies ran in eval mode. The trusted runner collected scores after the split.
Paired oracle and reconciler runs were replayed in memory. Trajectories contain public-policy actions.

| Split | Policy | Episodes | Precision | Recall | F1 | Reward | Inspection steps | Runtime (s) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| train | random_explorer | 10 | 0.200 | 0.200 | 0.200 | -0.603 | 8.00 | 0.0078 |
| train | reconciler | 10 | 1.000 | 1.000 | 1.000 | 0.968 | 16.00 | 0.0066 |
| train | flag_all | 10 | 0.000 | 0.200 | 0.000 | -1.000 | 2.00 | 0.0065 |
| train | oracle | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 0.00 | 0.0064 |
| dev | random_explorer | 10 | 0.200 | 0.200 | 0.200 | -0.603 | 8.00 | 0.0080 |
| dev | reconciler | 10 | 1.000 | 1.000 | 1.000 | 0.967 | 16.30 | 0.0068 |
| dev | flag_all | 10 | 0.000 | 0.200 | 0.000 | -1.000 | 2.00 | 0.0066 |
| dev | oracle | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 0.00 | 0.0066 |
| mirror | random_explorer | 20 | 0.250 | 0.250 | 0.250 | -0.504 | 8.00 | 0.0079 |
| mirror | reconciler | 20 | 1.000 | 1.000 | 1.000 | 0.968 | 16.20 | 0.0073 |
| mirror | flag_all | 20 | 0.000 | 0.250 | 0.000 | -1.000 | 2.00 | 0.0071 |
| mirror | oracle | 20 | 1.000 | 1.000 | 1.000 | 1.000 | 0.00 | 0.0070 |

Replay, public record and oracle finding equivalence, and oracle reward invariance passed on 20/20 combined ID and order transformations.
