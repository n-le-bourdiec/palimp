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

## Hard tuning, session 24 (2026-10-13, dev seeds, not a held-out run)

Decision 0039, tuned on Hard seeds 0 to 19 only, checked on 20 to 49.
Dangerous errors use decision 0038 (live or still needed); the old count
(live only) is next to it.

- palimp commit: `93df3f6` (session 24), baseline `a9e0ef0`
- Simulator: 0.3.0, level Hard
- Command: `uv run python eval/verdicts.py --level hard --seeds 0-19` (and `20-49`)

| Metric | Hard 0-19 before | Hard 0-19 after | Hard 20-49 before | Hard 20-49 after |
|---|---|---|---|---|
| Rules | 8260 | 8260 | 12490 | 12490 |
| Verdict vs best achievable | 98.1% | 97.3% | 98.2% | 97.4% |
| Dangerous errors (decision 0038) | 0 | 0 | 0 | 0 |
| Dangerous errors (old, live only) | 0 | 0 | 0 | 0 |
| Overconfidence | 1.8% (146) | 1.6% (136) | 1.4% (177) | 1.3% (163) |
| HIGH: intent application right | 56.9% (923 HIGH) | 94.3% (942 HIGH) | 56.6% (1218 HIGH) | 95.5% (1257 HIGH) |

Per trap, verdict vs best (overconfident share), before -> after:

| Trap | Hard 0-19 | Hard 20-49 |
|---|---|---|
| (none) | 99.4% (0.0%) -> 97.6% (0.0%) (1866) | 98.6% (0.0%) -> 97.5% (0.0%) (2579) |
| TRAP-BATCH-COMMIT | 100.0% (1.1%) -> 99.3% (0.0%) (280) | 99.8% (0.0%) -> 98.5% (0.0%) (472) |
| TRAP-DEACTIVATED | 100.0% (0.0%) -> 100.0% (0.0%) (1368) | 100.0% (0.0%) -> 100.0% (0.0%) (2201) |
| TRAP-EMERGENCY-LOADBEARING | 100.0% (0.0%) -> 100.0% (0.0%) (36) | 100.0% (0.0%) -> 100.0% (0.0%) (81) |
| TRAP-HISTORY-HORIZON | 97.9% (1.8%) -> 97.4% (1.8%) (5650) | 98.3% (1.4%) -> 97.5% (1.4%) (8709) |
| TRAP-IP-REUSE | 0.0% (6.9%) -> 100.0% (0.0%) (72) | 0.0% (7.7%) -> 100.0% (0.0%) (65) |
| TRAP-LIVE-NOLOG | 100.0% (0.0%) -> 100.0% (0.0%) (36) | 100.0% (0.0%) -> 100.0% (0.0%) (44) |
| TRAP-MISLEADING-COMMENT | 100.0% (0.0%) -> 88.6% (0.0%) (35) | 97.5% (1.2%) -> 96.3% (0.0%) (81) |
| TRAP-RARE-JOB | 100.0% (0.0%) -> 100.0% (0.0%) (50) | 100.0% (0.0%) -> 100.0% (0.0%) (61) |
| TRAP-RENAME-CHAIN | 96.8% (0.0%) -> 95.7% (0.0%) (93) | 98.8% (0.0%) -> 97.7% (0.0%) (172) |
| TRAP-SCANNER-HITS | 0.0% (28.6%) -> 45.2% (7.1%) (42) | 0.0% (26.7%) -> 36.7% (8.3%) (60) |
| TRAP-STALE-NAME | 100.0% (80.3%) -> 61.8% (84.7%) (157) | 100.0% (90.6%) -> 52.6% (92.4%) (171) |

Reading:

- HIGH confidence names the right application 94 to 96% of the time
  (target 90%), from 57%: regional instances are read exactly, and a bare
  name with instances is capped at MEDIUM with its candidates.
- TRAP-IP-REUSE is judged `verify` everywhere. The cost: every policy on a
  shared destination address gets `verify`, including the current
  application's side and renamed applications (TRAP-STALE-NAME drops to
  53-62% verdict = best), which is why verdict = best falls about 1 point.
  No artifact tells the retired side from the current one reliably.
- TRAP-SCANNER-HITS: logged probe traffic is recognized (all such rules
  move to `verify`); scanner rules with no logging show only hit counts and
  stay `keep`.
- TRAP-STALE-NAME stays overconfident: most renamed applications leave no
  trace (no object or ticket links the old name to the new one).
- Dangerous errors: 0 on both sets, both definitions. Medium dev seeds 20 to
  99 with the same commit: unchanged (12553 rules, 92.0% vs best, 0
  dangerous errors, HIGH 98.2% intent right).

## Name filters and corroboration, session 27 (2026-10-13, dev seeds, not a held-out run)

Decision 0042 (name filters, server roles, zone name words, corroboration
rule, policy name and `dynamic-application` as naming evidence). Not tuned
against the simulator: the word lists come from the project lead's review of
real configurations. Underconfidence is confidence below
`best_achievable_confidence` (else `max_justified_confidence`), computed from
the `--json` rows.

- palimp commit: `19e3746` (session 27), baseline `33d2602`
- Command: `uv run python eval/verdicts.py --level medium --seeds 20-99` and
  `--level hard --seeds 20-49`, with `--json` for the per-rule comparison

| Metric | Medium 20-99 before | Medium 20-99 after | Hard 20-49 before | Hard 20-49 after |
|---|---|---|---|---|
| Rules | 12553 | 12553 | 12490 | 12490 |
| Verdict vs best achievable | 92.0% | 92.0% | 97.6% | 97.7% |
| Dangerous errors (decision 0038) | 0 | 0 | 0 | 0 |
| Intent application right (first named) | 97.4% | 93.9% | 94.7% | 91.2% |
| Overconfidence | 0.0% (0) | 0.0% (0) | 0.9% (116) | 0.5% (64) |
| Underconfidence | 15.3% (1921) | 48.1% (6032) | 12.5% (1557) | 57.1% (7127) |
| HIGH / MEDIUM / LOW | 3426 / 8641 / 486 | 3307 / 3886 / 5360 | 1257 / 11032 / 201 | 1214 / 4926 / 6350 |
| HIGH: intent application right | 98.2% | 98.4% | 95.5% | 95.9% |

Reading:

- Intent accuracy drops 3.5 points on both sets, more than the 1 point the
  session prompt set as the reporting threshold. The cause is the name
  filters, not the corroboration rule (which changes confidence only):
  simulated applications with 2-letter names (`bi`, `ci`) or role names
  (`dns`, `ntp`, `bkp`) are no longer read from object names when no ticket
  backs them. Kept as decided (correct on real data); session 29 makes
  simulated names realistic.
- Underconfidence rises sharply: simulated object names always start with
  the application name, on one side only, so most rules have a single name
  source and fall to LOW (C-T3-SINGLE). Expected from the rule.
- Verdicts (filters only, through shared addresses and not-live markers),
  every move toward `keep` or `verify`: Hard 18 V-SHARED-ADDRESS rules move
  to keep (now = best), 5 move to keep (best was verify), 2 V-NOTLIVE
  removal candidates move to verify (now = best); Medium 2 V-CONTRADICTION
  rules move to keep (best was verify). No rule moves toward
  `removal_candidate`.

## Naming sources and services, session 28 (2026-10-20, dev seeds, not a held-out run)

Decision 0043 (a conflict never sets the intent, products and application
names, address objects counted once, dynamic application MEDIUM, predefined
applications, product ports, server roles matching the service, two-letter
names only when confirmed, flows, `term` applications, name/service
contradiction) and two safe fixes for shared addresses. Not tuned against
the simulator: every rule comes from the project lead's review of real
configurations. Two bugs the dev sets showed were fixed before this run (a
server role naming `mssql` ahead of the application, intent 93.9% to 80.6%
on Medium; a two-letter name read twice, which moved one Hard rule to keep).

- palimp commit: `8bccb19` (session 28), baseline `a5f4b8c` (session 27,
  same analyzer code as `19e3746`)
- Command: `uv run python eval/verdicts.py --level medium --seeds 20-99` and
  `--level hard --seeds 20-49`, with `--json` for the per-rule comparison

| Metric | Medium 20-99 before | Medium 20-99 after | Hard 20-49 before | Hard 20-49 after |
|---|---|---|---|---|
| Rules | 12553 | 12553 | 12490 | 12490 |
| Verdict vs best achievable | 92.0% (11551) | 92.0% (11544) | 97.7% (12207) | 97.7% (12199) |
| Dangerous errors (decision 0038) | 0 | 0 | 0 | 0 |
| Intent application right (first named) | 93.9% | 95.3% | 91.2% | 92.1% |
| Overconfidence | 0.0% (0) | 0.0% (0) | 0.5% (64) | 0.4% (47) |
| Underconfidence | 48.1% (6032) | 56.9% (7138) | 57.1% (7127) | 67.6% (8440) |
| HIGH / MEDIUM / LOW | 3307 / 3886 / 5360 | 3300 / 2718 / 6535 | 1214 / 4926 / 6350 | 1208 / 3593 / 7689 |
| HIGH: intent application right | 98.4% | 98.4% | 95.9% | 95.9% |

Reading:

- Intent: 177 Medium and 110 Hard rules gain a right intent (server roles
  matching the service, `dns` or `ntp` objects on their port; two-letter
  names confirmed by the policy name), none loses it.
- Underconfidence rises: address objects on both sides now count once
  (1503 Medium and 1601 Hard rules move from C-T3 to C-T3-SINGLE), as the
  project lead decided. Simulated objects name the application on both
  sides of most rules.
- Verdicts, every move toward verify: Medium 7 rules `*-to-bank-sftp` on
  junos-https go from keep to verify (V-NAME-SERVICE, best keep: the name
  names the destination host's protocol, the simulator says keep); Hard 24
  rules go to verify through shared addresses (8 now = best, the
  TRAP-IP-REUSE rules of session 27 included; 16 with best keep). No rule
  moves toward keep or `removal_candidate`.
- Session 27 left 2 Medium V-CONTRADICTION rules at keep (`medium-000053`
  `rule-258` and `allow-new-11`): the commit comment "CI decom" names `ci`,
  a two-letter name filtered since decision 0042, so the decommission marker
  no longer reaches `ci-app-servers`. Not changed: reading a two-letter name
  in a not-live signal would move rules toward removal (needs approval).

## Rule semantics and review-3 fixes, session 29 (2026-10-20, dev seeds, not a held-out run)

Decision 0044: confirmed names only, two-letter names never confirmed by the
policy name, `dc` out of the roles and `ad` conditional, name/service flag
only when no object carries the service word, Ask line, conflicts in one
clause; deny and reject rules, catch-all deny, factory defaults, broad
permits, stated purpose, ticket look-up. Not tuned against the simulator:
every rule comes from the project lead's review of real configurations.

- palimp commit: `855c813` (session 29; the dev runs used `10c9bd4` plus the
  deny wording change of `855c813`, which touches no verdict, confidence or
  intent application), baseline `65acdfe` (session 28 code, `8bccb19`)
- Command: `uv run python eval/verdicts.py --level medium --seeds 20-99` and
  `--level hard --seeds 20-49`, with `--json` for the per-rule comparison

| Metric | Medium 20-99 before | Medium 20-99 after | Hard 20-49 before | Hard 20-49 after |
|---|---|---|---|---|
| Rules | 12553 | 12553 | 12490 | 12490 |
| Verdict vs best achievable | 92.0% (11544) | 92.0% (11551) | 97.7% (12199) | 97.7% (12199) |
| Dangerous errors (decision 0038) | 0 | 0 | 0 | 0 |
| Intent application right (first named) | 95.3% | 95.3% | 92.1% | 92.0% |
| Overconfidence | 0.0% (0) | 0.0% (0) | 0.4% (47) | 0.4% (47) |
| Underconfidence | 56.9% (7138) | 56.8% (7135) | 67.6% (8440) | 67.7% (8458) |
| HIGH / MEDIUM / LOW | 3300 / 2718 / 6535 | 3307 / 2713 / 6533 | 1208 / 3593 / 7689 | 1208 / 3577 / 7705 |
| HIGH: intent application right | 98.4% | 98.4% | 95.9% | 95.9% |

Reading:

- Verdicts: Medium 7 rules `*-to-bank-sftp` on junos-https go from verify
  back to keep (= best): the object `bank-sftp` carries the service word, so
  the name/service flag no longer fires (decision 0044 item 4, the project
  lead's rule). Hard: no verdict change.
- Intent: Medium 16 rules gain a right intent and 10 lose it, Hard 4 and 11:
  the losses are two-letter names (`ci`, `bi`, `hr`) that only the policy name
  confirmed (`allow-bi`, `hr-access`), now LOW without an application, as the
  project lead decided.
- The simulator generates no deny or reject rule, no catch-all deny, no broad
  permit and no factory default policy: V-CLEANUP-RULE, V-DENY-NOTLIVE,
  V-FACTORY-DEFAULT and V-BROAD-PERMIT never fire on the dev sets. Part B is
  checked by unit tests and the real configurations only (simulator backlog).

## Simulator 0.4.0, session 30 (2026-10-20, no evaluation run)

Simulator 0.4.0 (decision 0045) changes Medium and Hard scenarios:
realistic object, policy and description names (spec 2.5),
`max_justified_confidence` computed from naming sources (spec 6.1), and
firewall team rules: deny, catch-all deny, broad permit and factory default
(spec 4.11), with new intent kinds in the ground truth. Easy artifacts are
byte-identical.

Medium and Hard numbers measured with simulator 0.3.0 (every run and dev
seed table above, including held-out run 1) are not comparable with numbers
measured with 0.4.0 or later: the scenarios, their rule counts, the expected
verdicts of the new rules and the confidence ceilings all changed. Compare
analyzer versions only on the same simulator version. The next analyzer
session measures palimp on 0.4.0 dev seeds; the second held-out run uses
0.4.0.

## Simulator 0.4.0 baseline, session 31 (2026-10-20, dev seeds, not a held-out run)

palimp at `487de86` (anonymize fix only, no analyzer tuning), simulator
0.4.0. Not comparable with earlier Medium and Hard numbers (realistic names,
naming-source confidence, firewall team rules, decision 0045).

| metric | Medium 20-99 | Hard 20-49 |
|---|---|---|
| rules | 12836 | 12659 |
| verdict vs expected | 86.7% | 82.4% |
| verdict vs best achievable | 91.5% | 97.8% |
| dangerous errors (old definition) | 0 (0) | 0 (0) |
| naive baseline dangerous errors | 187 | 139 |
| overconfidence (vs best achievable) | 9.5% | 7.6% |
| underconfidence (vs best achievable) | 12.2% | 10.1% |
| intent application right | 44.3% | 39.9% |
| HIGH: intent right / verdict = best | 96.1% / 97.7% | 94.1% / 99.0% |

New rule kinds (verdict vs best; all recognized by palimp, 0 dangerous):

| kind | Medium rules | Medium vs best | Hard rules | Hard vs best |
|---|---|---|---|---|
| block | 141 | 80.9% | 87 | 64.4% |
| cleanup_deny | 72 | 100.0% | 42 | 100.0% |
| broad_permit | 49 | 100.0% | 30 | 100.0% |
| factory_default | 21 | 100.0% | 10 | 100.0% |

Every `block` miss is keep -> verify (V-NO-TRAFFIC-SEEN: 27 Medium, 31
Hard), the safe direction; block confidence is LOW where the ground truth
says MEDIUM (99% underconfident). Intent application right is low on all
kinds because firewall team rules have `app_id` `firewall` and 33% to 37% of
application rules have no naming source (decision 0045).

## Session 31 changes (2026-10-20, dev seeds, not a held-out run)

Decision 0046 (two-letter names confirmed by commit comments and tickets,
review-4 fixes, shadowed rules, deny tuning). Tuning on Medium 0-19 and
Hard 0-19 only; the table reports Medium 20-99 and Hard 20-49 before
(`487de86`, the baseline above) and after (`2b31281`).

| metric | Medium before | Medium after | Hard before | Hard after |
|---|---|---|---|---|
| verdict vs expected | 86.7% | 86.9% | 82.4% | 82.7% |
| verdict vs best achievable | 91.5% | 91.7% | 97.8% | 98.1% |
| dangerous errors | 0 | 0 | 0 | 0 |
| overconfidence | 9.5% | 9.5% | 7.6% | 7.6% |
| underconfidence | 12.2% | 11.3% | 10.1% | 9.5% |
| intent application right | 44.3% | 44.3% | 39.9% | 39.9% |
| block vs best | 80.9% | 100.0% | 64.4% | 100.0% |
| HIGH intent right / verdict = best | 96.1% / 97.7% | unchanged | 94.1% / 99.0% | unchanged |

Verdict moves, all verify to keep on active deny rules that see no traffic
(`V-DENY-QUIET`), all equal to the best achievable verdict: Medium 27, Hard
31. MEDIUM intent right falls (Medium 71.6% to 68.7%) only because deny
rules now reach MEDIUM by their block while their ground truth `app_id` is
the pseudo application `firewall`. No simulator rule is shadowed (the
simulator always places the catch-all deny last); one real configuration
rule is.

## Simulator 0.5.0, session 32 (2026-10-20, no evaluation run)

Simulator session; the analyzer was not run. Decision 0047 adds
`expected.rule_kind` and `expected.best_achievable_intent` to every rule,
shadowed rules (`TRAP-SHADOWED-BY-DENY`) and `ANY` address sets in Medium
and Hard. The 0.4.0 numbers above (sessions 30 and 31) were never
published: no release and no held-out run used simulator 0.4.0. Simulator
0.5.0 is the release basis; the next held-out run uses it.

Intent application right on 0.4.0 (44.3% Medium, 39.9% Hard) scored every
"purpose unknown" as wrong. On 0.5.0, 33.4% of Medium and 36.5% of Hard
application rules have a null `best_achievable_intent` (nothing in the
artifacts names their application), and the 337 Medium and 279 Hard
firewall team rules are scored on `rule_kind`. Easy artifacts are
byte-identical; every 0.4.0 rule of Medium 0-99 and Hard 0-49 keeps its
expected values, so verdict numbers stay comparable except on the 10
Medium and 21 Hard shadowed rules (spec 7.7).

## Simulator 0.5.0 release basis, session 33 (2026-10-29, dev seeds, not a held-out run)

Decision 0048. Intent is now scored against what the artifacts allow
(`best_achievable_intent` for application rules, null meaning palimp should
name no application; `rule_kind` for firewall team rules); the old number
stays as "vs true application". Changes: every active deny or reject rule is
keep; endpoints and site prefixes name no application; a database engine or
a file, backup or mail protocol on a matching server role is no longer the
intent. Tuning on Medium 0-19 and Hard 0-19 only, in the safe direction (no
verdict moves there). Before: `61b4d91` (session start, new scoring). After:
`1c672ae`. These are the 0.5.0 release basis numbers.

- Simulator: 0.5.0
- Command: `uv run python eval/verdicts.py --level medium --seeds 20-99` and
  `--level hard --seeds 20-49`, with `--json` for the per-rule comparison

| metric | Medium 20-99 before | Medium 20-99 after | Hard 20-49 before | Hard 20-49 after |
|---|---|---|---|---|
| rules | 12840 | 12840 | 12671 | 12671 |
| verdict vs best achievable | 91.7% | 91.7% | 98.1% | 98.1% |
| verdict vs expected | 86.9% | 86.9% | 82.7% | 82.7% |
| intent vs best achievable | 52.7% | 82.1% | 51.2% | 78.6% |
| intent vs true application | 44.3% | 59.2% | 39.9% | 51.3% |
| overconfidence (vs best achievable) | 9.5% | 10.1% | 7.6% | 5.3% |
| underconfidence (vs best achievable) | 11.3% | 11.1% | 9.5% | 9.5% |
| dangerous errors | 0 | 0 | 0 | 0 |
| naive baseline dangerous errors | 191 | 191 | 148 | 148 |
| HIGH: intent vs best / verdict = best | 96.1% / 97.7% | 96.7% / 97.7% | 94.3% / 99.0% | 95.6% / 99.0% |

Per scope, after (verdict vs best, intent vs best achievable, intent vs true
application, overconfident, underconfident, dangerous palimp / naive):

| scope | Medium rules | Medium | Hard rules | Hard |
|---|---|---|---|---|
| application | 12557 | 91.6%, 81.7%, 60.6%, 10.4%, 11.2%, 0 / 164 | 12502 | 98.0%, 78.3%, 52.0%, 5.4%, 9.5%, 0 / 117 |
| block | 141 | 100%, 100%, 0%, 0.7%, 17.7%, 0 / 27 | 87 | 100%, 100%, 0%, 1.1%, 18.4%, 0 / 31 |
| cleanup_deny | 72 | 100%, 100%, 0%, 0%, 0%, 0 / 0 | 42 | 100%, 100%, 0%, 0%, 0%, 0 / 0 |
| broad_permit | 49 | 100%, 100%, 0%, 0%, 0%, 0 / 0 | 30 | 100%, 100%, 0%, 0%, 0%, 0 / 0 |
| factory_default | 21 | 100%, 100%, 0%, 0%, 0%, 0 / 0 | 10 | 100%, 100%, 0%, 0%, 0%, 0 / 0 |
| TRAP-SHADOWED-BY-DENY | 4 | 100%, 75.0%, 50.0%, 0%, 25.0%, 0 / 4 | 12 | 100%, 100%, 58.3%, 16.7%, 8.3%, 0 / 9 |
| ANY source | 19 | 94.7%, 73.7%, 68.4%, 5.3%, 15.8%, 0 / 0 | 19 | 100%, 89.5%, 73.7%, 0%, 15.8%, 0 / 0 |

Firewall team rules read 0% "vs true application" by construction (their
`app_id` is the pseudo application `firewall`). Verdict moves rule by rule:
none on Medium 20-99 and Hard 20-49 (the deny change moves no simulated
rule: simulated deny rules all have counters, so they were already
`V-DENY-QUIET` keep). Tuning seeds, before and after: Medium 0-19 intent
51.8% to 80.8%, overconfidence 7.2% to 9.7%; Hard 0-19 intent 48.7% to
79.1%, overconfidence 7.4% to 5.3%; verdicts unchanged. Medium
overconfidence rises because rules whose T1 names the application no longer
conflict with a person's name in their objects and get MEDIUM (C-T1-ONLY)
where the ground truth often says LOW (decision 0048, alternatives).

Held-out: the workflow now runs Medium 50 (headline) and Hard 30 next to
it. Not run in this session; the project lead triggers it after rotating
the salt.
