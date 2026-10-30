# Metrics summary

Computed by `metrics/summary.py` from `metrics/sessions.csv`, sessions 1 to 34 (finalized rows only). Cost is the API-equivalent cost of the tokens at the prices in `metrics/pricing.json` (decision 0006), not a billed amount. Calls are model API calls as counted in each row's notes.

| scope | sessions | calls | minutes | input tokens | output tokens | cache read tokens | cache write tokens | API-equivalent cost (USD) |
|---|---|---|---|---|---|---|---|---|
| all | 34 | 3,313 | 1,868 | 6,622 | 2,872,419 | 610,310,979 | 6,946,350 | 235.10 |
| phase analyzer | 20 | 2,303 | 1,305 | 4,600 | 1,735,059 | 406,563,128 | 4,315,397 | 150.54 |
| phase simulator | 10 | 821 | 514 | 1,644 | 978,516 | 182,697,795 | 2,223,969 | 73.92 |
| phase bootstrap | 1 | 17 | 4 | 34 | 15,400 | 897,597 | 37,468 | 0.79 |
| phase eval | 1 | 60 | 22 | 120 | 39,559 | 6,168,379 | 108,457 | 2.89 |
| phase formats | 1 | 85 | 15 | 170 | 65,589 | 11,501,986 | 200,925 | 5.22 |
| phase spec | 1 | 27 | 8 | 54 | 38,296 | 2,482,094 | 60,134 | 1.74 |

Commits: 294. Lines added: 38,707, removed: 3,884 (metrics files excluded, as each row records them).
