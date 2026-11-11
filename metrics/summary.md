# Metrics summary

Computed by `metrics/summary.py` from `metrics/sessions.csv`, sessions 1 to 35 (finalized rows only). Cost is the API-equivalent cost of the tokens at the prices in `metrics/pricing.json` (decision 0006), not a billed amount. Calls are model API calls as counted in each row's notes.

| scope | sessions | calls | minutes | input tokens | output tokens | cache read tokens | cache write tokens | API-equivalent cost (USD) |
|---|---|---|---|---|---|---|---|---|
| all | 35 | 3,435 | 1,904 | 6,866 | 2,948,395 | 629,440,934 | 7,159,291 | 242.15 |
| phase analyzer | 21 | 2,425 | 1,341 | 4,844 | 1,811,035 | 425,693,083 | 4,528,338 | 157.59 |
| phase simulator | 10 | 821 | 514 | 1,644 | 978,516 | 182,697,795 | 2,223,969 | 73.92 |
| phase bootstrap | 1 | 17 | 4 | 34 | 15,400 | 897,597 | 37,468 | 0.79 |
| phase eval | 1 | 60 | 22 | 120 | 39,559 | 6,168,379 | 108,457 | 2.89 |
| phase formats | 1 | 85 | 15 | 170 | 65,589 | 11,501,986 | 200,925 | 5.22 |
| phase spec | 1 | 27 | 8 | 54 | 38,296 | 2,482,094 | 60,134 | 1.74 |

Commits: 309. Lines added: 39,880, removed: 4,039 (metrics files excluded, as each row records them).

Not counted yet (provisional row, finalized at the start of the next session): session 36.

Not counted (tokens and cost unknown, never estimated): audit-1 (audit).
