# 0018 Medium trap counts drawn per scenario, hit count clear placed independently

- Status: Accepted
- Date: 2026-10-05
- Supersedes: no decision file. It replaces the coverage rule of spec 7.2
  ("every v1 trap appears at least once in every Medium scenario") and the
  fixed trap counts of session 9 (spec 7.1 and 7.4: four emergencies, one
  weekly job, two rare jobs, one batch commit, one forced copied comment).

## Context

Session 9 built every v1 trap into every Medium scenario, with a constant
number of instances for most of them (for example exactly four
TRAP-EMERGENCY-LOADBEARING rules in every scenario). An analyzer could learn
"there is always one batch commit and four emergency rules" and score well by
counting instead of reading the evidence.

Session 9 also placed the hit count clear (`clear security policies hit-count
from-zone A to-zone B`, used by TRAP-LIVE-NOLOG) on the servers to internet
pair, the same pair as every rare job (application to partner). Quarterly job
rules then lost their hits to the clear rather than to their schedule, so the
"rare job" and the "recent clear" situations were always mixed.

## Decision

1. For Medium, the number of instances of five traps is drawn per scenario
   from the seed (sub-generator `trap_counts`), with the weights of
   `levels.TRAP_COUNT_WEIGHTS` (0, 1, 2, ... instances):
   weekly jobs without logging 0.25 / 0.5 / 0.25, yearly jobs
   0.3 / 0.45 / 0.25, emergencies 0.2 / 0.35 / 0.3 / 0.15, copied comments
   0.25 / 0.4 / 0.25 / 0.1, batch commits 0.25 / 0.55 / 0.2. Quarterly jobs
   (0.5 / 0.5) are drawn too but are not a trap by themselves. Target over
   seeds 0 to 99: each of these traps in 60 to 90% of scenarios, never a
   constant count. The drawn counts are not written to the manifest (they
   would hint at the answer).
2. TRAP-HISTORY-HORIZON and TRAP-DEACTIVATED keep following from the
   timeline. Cleanups (which make deactivated rules) are now one a year,
   placed independently; each emergency happens 90 to 150 days before one of
   them (or gets its own cleanup if none fits), so the cleanup count no longer
   follows the emergency count.
3. The hit count clear lands on one zone pair drawn on its own (sub-generator
   `hit_count_clear`) among the pairs a weekly job can use: servers to
   internet, servers to management, management to servers. Weekly jobs
   without logging are placed in that pair (partner transfer, dump to the
   backup server, or backup server pulling an export). Rare jobs stay
   application to partner, so a rare job and the clear share a zone pair only
   by chance (about one scenario in three).
4. The simulator version goes to 0.3.0. Easy output is unchanged except the
   version string, which changes every Easy hash; this is accepted (no
   per-level output versions). `test_determinism.py` documents it and checks
   that Easy with the version string set back to 0.2.0 still gives the 0.2.0
   hashes.
5. CI runs the Medium checks on seeds 0 to 9. Seeds 10 to 99 (trap
   distribution, leakage) carry the `full` marker and run with `--runslow`
   only.

## Alternatives considered

- Keep every trap in every scenario with variable counts (1 to N): still lets
  an analyzer assume presence; a scenario without a given trap is a useful
  negative case.
- Draw a presence flag, then a count: two draws for the same effect as one
  weighted count.
- Keep the clear on servers to internet and move rare jobs elsewhere: the two
  would still be tied by construction, just on another pair.
- Draw the clear among every zone pair: a weekly job in users to servers or
  users to internet is not a plausible scheduled job, and TRAP-LIVE-NOLOG
  needs a weekly job in the cleared pair.
- Per-level output versions, so Easy hashes do not move: more machinery for a
  version string change.

## Consequences

- Per-trap metrics are computed over the scenarios that contain the trap;
  some Medium scenarios have none of a given trap.
- Measured over seeds 0 to 99 (session 10): see the spec 7.4 table and the
  session 10 report for the per-trap share and min/max counts.
- An analyzer can no longer rely on the hit count clear being on servers to
  internet; the manifest still records it (`hit_count_clears`).

## Challenged by Nathan

Yes, twice, in the session 10 prompt: constant trap counts per scenario, and
the hit count reset coupled to rare jobs. Outcome: both adopted as stated
above.
