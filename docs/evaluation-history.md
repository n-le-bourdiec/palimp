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
