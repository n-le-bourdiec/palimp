# 0039 Hard level quality: instances, renames, reused addresses, probes

- Status: Accepted
- Date: 2026-10-13
- Extends: decision 0020 (verdict and confidence rules: two new verdict
  rules, two new confidence caps), decision 0036 (Hard tuning on seeds 0 to
  19, check on 20 to 49).

## Context

The Hard dev baseline (session 23) showed HIGH confidence naming the right
application only 57% of the time (target 90%), and four Hard traps judged
poorly: TRAP-IP-REUSE and TRAP-SCANNER-HITS at 0% verdict = best,
TRAP-STALE-NAME overconfident on 80 to 90% of its rules, TRAP-RENAME-CHAIN
reading the rename commit as the creation. The session 24 prompt set five
items, tuned on Hard seeds 0 to 19 only and checked on 20 to 49, with zero
dangerous errors (decision 0038) on Hard 0 to 49 and Medium 20 to 99 after
each.

## Decision

1. **Regional instances** (`palimp.apps`). Two-letter suffixes of related
   CIs (`payroll-uk`, `hr-de`) are learned. A name followed by a learned
   suffix names that instance, even without a ticket (`payroll-pl-app-01`
   gives `payroll-pl`): an exact match. A bare name is never expanded to an
   instance. A bare name that is not itself a related CI while instances
   exist is ambiguous: an `ambiguous_app` T3 item lists the candidates,
   confidence is at most MEDIUM (`C-AMBIGUOUS-INSTANCE`), and a bare name
   is compatible with one of its instances (no conflict).
2. **Not-live signals keep the old reading.** Decommission links and
   migrations use the vocabulary without instances (the reading before this
   session). With the new reading, 3 rules of Hard 0 to 19 moved from
   `verify` to `removal_candidate` (correct application, best verdict
   `verify`); a move toward `removal_candidate` needs the project lead's
   approval (working rule 2), so it is not made. Open question.
3. **Renames** (`palimp.ingest.history`). A policy deleted and re-added
   under a new name with the same match (zones, addresses, applications,
   action, deactivation) in one commit is the same rule, when that match is
   unique among the commit's deleted and added policies. Its creation
   commit, comment and siblings are those of its first name; the rename is
   a `renamed` T3 item, neither a creation nor a removal; log lines under
   an old name are merged. Not-live signals still date the policy from its
   current name (a rename is a deliberate touch).
4. **Reused destination addresses.** A destination object whose address is
   also an object named after another application gives a `shared_address`
   T3 item, a conflict finding, both applications as candidates (and their
   requesters as owner candidates), confidence at most MEDIUM
   (`C-SHARED-ADDRESS`), and verdict `V-SHARED-ADDRESS` (verify) when
   traffic is seen or a not-live signal exists: never keep, never
   removal_candidate. Deactivated policies get no item. Which side is the
   retired application is not decided: no artifact tells it reliably (object
   creation predates the retained history, ticket dates point both ways, a
   renamed application looks the same), so both sides are flagged.
5. **Probe traffic** (`palimp.formats.rt_flow`). Close lines keep
   `packets-from-server` (both formats). A source reaching at least 3
   policies and 3 destinations with unanswered sessions is a probe source;
   its unanswered sessions are probe sessions, counted apart. A policy whose
   only logged traffic is probe traffic gets a `probe_only` T2 item, its
   hits stop counting as traffic seen (verdict and confidence), and verdict
   `V-PROBE-ONLY` (verify). With a positive not-live signal, V-NOTLIVE
   applies as written in decision 0020 (as the prompt states).
6. **Stale names.** A source object whose address is also another
   application's gives a `shared_source` item: conflict finding, confidence
   at most MEDIUM, verdict unchanged. Most stale names leave no trace of the
   new application in the artifacts (no object, no ticket naming the link),
   so they stay undetected.

## Alternatives considered

- Reused addresses: flag only the side whose application has the older
  latest ticket, or whose partner has no policy of its own. Measured on
  seeds 0 to 19: they catch 16 to 34 of 72 trap rules and still flag 35 to
  70 rules best judged `keep`. Flagging both sides catches all 72 and flags
  155 `keep` rules. Rejected in favor of the literal rule of the prompt
  (never keep); the cost is stated in the session report.
- Probe threshold 5 policies and destinations: no false positive, 9 of 21
  logged probe rules caught on 0 to 19; 3 catches 19 with one rule best
  judged `verify` anyway. 3 chosen.
- Read the instance for not-live signals too: moves verdicts toward
  removal_candidate, needs approval (item 2).

## Consequences

- Hard 0 to 19 and 20 to 49: HIGH intent right from 57% to about 95%;
  TRAP-IP-REUSE 0% to 100% verdict = best, TRAP-SCANNER-HITS 0% to 37-45%;
  verdict = best overall down about 1 point (the `keep` rules on reused
  addresses that now get `verify`). Zero dangerous errors.
- Medium 20 to 99 unchanged (no regional CIs, no shared addresses, no
  probe sources).
- Probe and rename detection are heuristics on synthetic logs and
  configurations; real captures may differ (the simulator's assumptions
  VSRX-13 and VSRX-15 are unverified).

## Challenged by Nathan

Asked by the project lead in the session 24 prompt (challenge 2 of 3:
HIGH calibration on Hard). Item 2 and the reused address cost are open
questions for the lead.
