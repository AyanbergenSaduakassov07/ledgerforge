# Reconciler failure analysis

Scored the recorded reconciler submissions again against truth regenerated from the benchmark case recipes. The replayed scores matched the recorded metrics for every case.

| Split | Episodes | True positives | False positives | False negatives |
|---|---:|---:|---:|---:|
| train | 10 | 21 | 0 | 2 |
| dev | 10 | 23 | 0 | 0 |
| mirror | 20 | 24 | 0 | 1 |

| Fault type | Expected issues | False positives | False negatives |
|---|---:|---:|---:|
| duplicate_invoice | 16 | 0 | 0 |
| payment_allocation | 20 | 0 | 3 |
| fx_rate | 16 | 0 | 0 |
| reporting_period | 19 | 0 | 0 |

| Outcome | Fault type | Measured cause | Count |
|---|---|---|---:|
| FN | payment_allocation | No corresponding submission | 3 |
