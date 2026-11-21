# Scenarios

Config = `ScenarioConfig` (`contracts/schemas.py`); unknown keys are rejected.

| Key | Values | Default |
|---|---|---|
| `industry` | industrial_procurement, construction, manufacturing, retail_services | industrial_procurement |
| `difficulty` | basic 30 / intermediate 50 / advanced 70 / expert 100 invoices | intermediate |
| `base_currency` | any supported (KZT, USD, EUR, RUB, CNY, JPY, KWD) | KZT |
| `n_invoices` | 20..150 overrides difficulty | null |
| `faults` | `{type: count}` for the four types | `{}` (clean) |
| `interactions` | `{duplicate_with_allocation \| fx_with_period: count}`; each yields 2 issues | `{}` |
| `distractors` | bool | true |
| `order_salt` | string: reshuffle public table order | null |
| `id_salt` | string: rename every id | null, **planned** |

Total issues = Σ faults + 2·Σ interactions ≤ 12.

## Faults

| Id | Mutation | Precondition |
|---|---|---|
| F1 duplicate_invoice | copy an unpaid invoice under a variant number (`-1`, `A`, separator removed), post it | target unpaid, not a credit-note set or recurring item |
| F2 payment_allocation | missing/partial: move x of the AP debit to 2190; misapplied: debit AP of another invoice of the same vendor | base-currency payment without legitimate advance |
| F3 fx_rate | post a foreign unpaid invoice at the rate of a wrong date | foreign currency, rate differs |
| F4 reporting_period | invoice issued 1–5 days after period end, posted 0–3 days before end | unpaid |
| Interaction A | duplicate of a fully paid base invoice; part of the payment misapplied to the duplicate | → duplicate + allocation |
| Interaction B | foreign cutoff invoice posted at the posting-date rate | → fx_rate + reporting_period |

## Legitimate look-alikes (hard negatives)

Recurring monthly services (same amount, different service month), credit note + reissue,
instalment and split payments, advances (overpayment to 2190), invoices at timezone boundaries on both
period ends, unposted next-period invoices.
