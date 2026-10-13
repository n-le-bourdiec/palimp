# Evaluation history

Every held-out evaluation run is recorded here, one section per run, newest
last. The held-out workflow (`.github/workflows/holdout.yml`, decisions 0007
and 0021) is run only by the project lead, at most once per release. Dev seed
numbers are listed next to each run for comparison only.

Metric definitions (from `eval/verdicts.py`):

- verdict vs best achievable: share of rules whose verdict equals the ground
  truth `best_achievable_verdict` (what the artifacts can support).
- verdict vs expected: share of rules whose verdict equals the ground truth
  expected verdict (what full knowledge would give).
- dangerous errors: `removal_candidate` on a rule that is live.
- overconfidence: share of rules whose confidence is above the ground truth
  `max_justified_confidence`.
- HIGH: verdict = best: among HIGH confidence rules, share whose verdict is
  the best achievable one.
- owner named: share of rules whose `ask` text contains the name of the
  ground truth `owner_to_ask`.

## Run 1: v0.1.0-baseline (2026-10-05)

- Date: 2026-10-05T18:23:57Z
- palimp commit: `15c9086` (tag `v0.1.0-baseline`)
- Simulator: 0.3.0
- Level: Medium, 50 held-out scenarios, 7748 rules

| Metric | palimp | Naive baseline |
|---|---|---|
| Verdict vs best achievable | 91.5% | 90.3% |
| Verdict vs expected | 86.6% | n/a |
| Dangerous errors | 0 | 109 |
| Overconfidence | 0.0% | n/a |
| HIGH: verdict = best | 97.5% | n/a |
| Owner named | 18.4% | n/a |

Dev seeds, same commit, for comparison:

| Set | Verdict vs best achievable |
|---|---|
| Medium dev seeds 0-19 (tuning set) | 90.0% |
| Medium dev seeds 20-99 (check set) | 91.1% |
| Held-out (this run) | 91.5% |

Reading: the held-out score sits at the level of the dev scores, so there is
no sign of overfitting to the tuning seeds. The naive baseline is close on
verdict accuracy but makes 109 dangerous errors; palimp makes none.

Limit: these are synthetic scenarios from the palimp simulator only. There is
no real-world validation yet, so these numbers say how palimp does on the
simulator's model of a firewall history, not on real firewalls.

Note (2026-10-13, decision 0038): this run counted a dangerous error as
`removal_candidate` on a rule whose `status.live` is true (the old
definition). From decision 0038 on, a rule whose `status.still_needed` is
true also counts. The run is not repeated; its "0 dangerous errors" holds
for the old definition only.

## Hard dev baseline (2026-10-13, dev seeds, not a held-out run)

Recorded before any Hard tuning (decision 0036): seeds 0 to 19 tune, seeds
20 to 49 check. Dev seeds only, so this is not a held-out run; it is the
reference the first Hard tuning session compares against.

- palimp commit: `a9e0ef0` (session 23)
- Simulator: 0.3.0, level Hard
- Command: `uv run python eval/verdicts.py --level hard --seeds 0-19` (and `20-49`)

| Metric | Hard 0-19 (tune) | Hard 20-49 (check) |
|---|---|---|
| Rules | 8260 | 12490 |
| Verdict vs best achievable | 98.1% | 98.2% |
| Verdict vs expected | 82.0% | 83.3% |
| Dangerous errors | 0 | 0 |
| Naive baseline dangerous errors | 87 | 108 |
| Overconfidence | 1.8% (146) | 1.4% (177) |
| HIGH: verdict = best | 98.0% | 97.9% |
| HIGH: intent application right | 56.9% | 56.6% |
| Intent application right (all rules) | 46.6% | 45.3% |
| Owner named | 44.2% | 44.5% |

Per trap, verdict vs best achievable (rules; overconfident share):

| Trap | Hard 0-19 | Hard 20-49 |
|---|---|---|
| (none) | 99.4% (1866; 0.0%) | 98.6% (2579; 0.0%) |
| TRAP-BATCH-COMMIT | 100.0% (280; 1.1%) | 99.8% (472; 0.0%) |
| TRAP-DEACTIVATED | 100.0% (1368; 0.0%) | 100.0% (2201; 0.0%) |
| TRAP-EMERGENCY-LOADBEARING | 100.0% (36; 0.0%) | 100.0% (81; 0.0%) |
| TRAP-HISTORY-HORIZON | 97.9% (5650; 1.8%) | 98.3% (8709; 1.4%) |
| TRAP-IP-REUSE | 0.0% (72; 6.9%) | 0.0% (65; 7.7%) |
| TRAP-LIVE-NOLOG | 100.0% (36; 0.0%) | 100.0% (44; 0.0%) |
| TRAP-MISLEADING-COMMENT | 100.0% (35; 0.0%) | 97.5% (81; 1.2%) |
| TRAP-RARE-JOB | 100.0% (50; 0.0%) | 100.0% (61; 0.0%) |
| TRAP-RENAME-CHAIN | 96.8% (93; 0.0%) | 98.8% (172; 0.0%) |
| TRAP-SCANNER-HITS | 0.0% (42; 28.6%) | 0.0% (60; 26.7%) |
| TRAP-STALE-NAME | 100.0% (157; 80.3%) | 100.0% (171; 90.6%) |

Reading (seeds 0 to 19 only, the tuning set):

- No dangerous error. Rules best judged `verify` but given
  `removal_candidate` (none live): 13 on 0-19, 30 on 20-49, all
  `V-NOTLIVE`.
- TRAP-IP-REUSE and TRAP-SCANNER-HITS: palimp says `keep` (`V-TRAFFIC`)
  where `verify` is the best achievable verdict; hits from a reused address
  or a scanner are read as business traffic.
- TRAP-STALE-NAME: verdict right, but confidence above the justified level
  (the old name and the objects agree on the old application).
- HIGH confidence names the right application in only 57% of cases, far
  under the 90% target (Medium: 98.2%). On seed 0 the misses are regional
  instances: `payroll-pl` read as `payroll-uk`, `hr-de` as `hr`.

Medium dev seeds 20 to 99 with the same commit: 12553 rules, 92.0% vs best,
87.1% vs expected, 0 dangerous errors, HIGH 98.2% intent right, unchanged
from session 21.
