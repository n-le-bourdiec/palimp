# 0051 Not-live signals after the audit: no removal from a doubtful text, a lineage or a silence

- Status: Accepted
- Date: 2026-11-11 (session 36, analyzer)
- Supersedes:
  - decision 0020, the example "a commit comment or a ticket decommissions or
    retires the application that the policy's address objects belong to":
    naming the application is no longer enough (item 1 below);
  - decision 0024, "Migration leftover, a positive not-live signal": a
    migration leftover is now a question, never a not-live signal (item 2);
  - decision 0039 item 5, "its hits stop counting as traffic seen (verdict
    and confidence)" and "With a positive not-live signal, V-NOTLIVE applies
    as written": the probe reading now lowers the intent confidence only
    (item 4).
  The rest of those decisions stands.

## Context

An independent audit of the 0.1.0 release candidate (`../palimp-audit.md`,
2026-11-11, audited commit `e212a2d`) found that the core safety rule was
broken: rules that are live or still needed became `removal_candidate` with
ordinary histories.

- B1. Any commit comment or ticket matching a decommission word and naming an
  application retired every older policy whose objects all named that
  application, as long as it shared one object with a policy deleted by the
  linked commit. The text "retire one web server, replaced by another" retired
  the new server's rule, the backup rule and a feed rule to the same
  database. A negated text ("do NOT decommission ... yet") and a ticket about
  a test environment, linked by its closing day to an unrelated commit, did
  the same. With no hit counts, counters at 0 or a non-logging policy, the
  verdict was `removal_candidate`.
- B2. Adding a second database node (two policies copied to it) read as a
  migration; the old node, kept as a standby, was silent in a two-day or
  one-hour log, and its policies became `removal_candidate`. Its silence was
  the not-live sign, which decision 0020 forbids.
- M1. A server sending syslog to three collectors (one-way UDP, no packet
  from the server) was read as a scanner. Its policies lost their hit
  counters as evidence of use; with any not-live text, 50,000 hits a policy
  gave `removal_candidate`.
- M5. The only black-box safety test used `status.live` only (decision 0038
  added `still_needed`), on Medium seeds 0 to 9, and no Hard seed.

The audit reproduced each case with probes (`../palimp-audit/probe.py`).
Session 36 rebuilt each scenario with invented names as failing tests
(`tests/test_safety_regressions.py`, commit `9df2212`) before any fix.

## Decision

Every change moves rules toward `verify` or `keep`, never toward
`removal_candidate`.

1. **Decommission text** (`palimp.notlive`). A commit comment or a ticket
   summary that retires something (a policy description is never read as a
   not-live signal, before or after this decision) is a not-live signal
   (`decommission`) only when, on top of the existing links (every
   application the rule's objects name is the retired one, the linked commit
   deleted policies sharing an object with this older rule), it:
   - names an address, host or object of this rule that the deleted policies
     referenced too (an object name, a member of a set, an address or a DNS
     name of it), not only an application word shared with other rules. An
     object of the rule that the deleted policies did not reference may be
     the replacement ("retire app-03, replaced by app-04");
   - is neither negated nor conditional: no `not`, `never`, `n't`, `yet`,
     `once`, `after`, `until`, `unless`, `if`, `when`, `pending`, `planned`,
     `plan`, `scheduled`, `will`, `later`, `before`, `maybe`, `possibly`,
     `candidate`;
   - matches the rule's scope: an environment word in the text (test,
     staging, dev, QA, UAT, preprod, sandbox, lab, PoC, demo, by family)
     applies only to a rule whose objects carry a word of the same family;
   - is linked to the commit by a citation (the commit comment itself, or a
     ticket that a commit comment cites). A ticket linked by its closing day
     alone is a question. This last condition was not in the session prompt:
     it is an initiative in the safe direction (it moves rules toward
     `verify` only), flagged in the session report.
   Otherwise the item is `decommission_question` and the verdict is
   `V-NOTLIVE-QUESTION` (verify): "A change record mentions a retirement
   that may concern this policy, without clearly saying its servers are
   gone. Is this policy still needed?" The claim says which conditions
   failed.
2. **Lineage** (`palimp.lineage`). A migration leftover is never a not-live
   signal. Verdict `V-MIGRATION-LEFTOVER` (verify), question "Is the old node
   still kept as a standby?". The leftover item is still produced (it is
   true history); its log check only decides whether the question is asked.
3. **Logs and counters** are evidence of use only. Their silence, a zero or a
   short log window never counts toward not-live. After items 1 and 2 the
   only not-live signals are a deactivated rule and a decommission text that
   names an object of the rule; neither reads a log or a counter.
4. **Scanner heuristic** (`palimp.formats.rt_flow`, `palimp.assess`). The
   probe reading may lower the intent confidence (hits on a probe-only
   policy still do not confirm the intent), but never cancels hits or logs
   for the verdict: hits and probe sessions next to a not-live signal give
   `V-CONTRADICTION` (verify). `V-PROBE-ONLY` (verify) stays for a policy
   whose only logged traffic is probe traffic and that has no not-live
   signal. One-way UDP to a service port (syslog 514, SNMP 161 and traps
   162, NetFlow 2055, 9995 and 9996, IPFIX 4739, sFlow 6343, NTP 123) is
   never an unanswered session: it does not make a source a probe source
   and does not count as a probe session.
5. **Every removal_candidate names its signal.** `Assessment.removal_signal`
   holds the ID of the one positive signal it rests on (deactivated first,
   then decommission), the verdict reason names it ("the rule is
   deactivated", "a decommission record names an object of this rule"), and
   the report refuses a removal_candidate without it. A black-box test
   checks it on every dev scenario (item 6).
6. **Safety test** (`tests/test_safety_verdicts.py`, replaces
   `tests/test_medium_verdicts.py`). Dangerous means `removal_candidate` on a
   rule whose `status.live` or `status.still_needed` is true. Fast tier in CI
   on Medium 0 to 19 and Hard 0 to 19; slow tier with `--runslow` on Medium
   20 to 99 and Hard 20 to 49 (both together: Medium 0 to 99, Hard 0 to 49).

## Alternatives considered

- **The audit's 0.1.0 fix: a decommission text gives `verify` unless the
  rule is also deactivated.** Simplest and safest, but it throws away the one
  text signal that is right when the text names the rule's own server. The
  session prompt asked for the narrower reading above. Measured below: what
  removal candidates remain rest on a named object.
- **Keep lineage as a not-live signal with a minimum log window and traffic
  to the new host from the same sources** (audit suggestion for later). A
  standby node fails every such check: it is silent by design whatever the
  window. Rejected for v1.
- **Count only TCP sessions as probes** (audit suggestion). Scanners also
  send UDP; the service port list keeps UDP scans of other ports readable.
  Kept to the ports the prompt names and their close relatives.
- **Drop `V-PROBE-ONLY` and give `keep` to any policy with hits or probe
  sessions.** "Never cancels hits for the verdict" could be read that way.
  Kept at `verify`: it never leads to `removal_candidate`, and a policy only
  scanners use is a fair question.

## Consequences

Measured on Medium dev seeds 20 to 99 and Hard dev seeds 20 to 49, before
(`e212a2d` code) and after; see `docs/evaluation-history.md`, session 36.

- Medium: removal candidates 1121 to 1085, verdict vs best 91.7% to 91.5%:
  36 rules move to verify (24 lineage, 12 decommission), all neither live
  nor still needed, best achievable removal_candidate.
- Hard: removal candidates 2239 to 2217, verdict vs best 98.1% to 98.2%:
  22 rules move to verify (15 lineage, 7 decommission), all neither live nor
  still needed, best achievable verify.
- Intent, confidence and calibration unchanged (0 confidence changes),
  dangerous errors 0 before and after on both levels: the simulator never
  produced the audit histories (audit B3). The regression tests are what
  protect against them.
- After the fix every simulated removal candidate is a deactivated rule:
  no simulated decommission text names a server object.
- Real public configurations: no change rule by rule (configuration alone).
- New verdict rules V-MIGRATION-LEFTOVER and V-NOTLIVE-QUESTION (verify);
  V-CONTRADICTION now only joins a deactivated rule or a decommission
  naming an object with traffic.
- The report sentence on removal candidates now says each rests on one
  positive sign, deactivated or a decommission record naming an object of
  the rule, and never on missing traffic, a zero counter or a migration.

## Challenged by Nathan

Prompted by the independent audit (findings B1, B2, M1, M5), which the
project lead passed on as the session 36 mission. The prompt fixed the rules
of items 1 to 6; the closing-day ticket condition is this session's
initiative and awaits the project lead's review.
