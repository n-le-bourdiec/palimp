# 0040 Ground truth states what the artifacts allow: `best_achievable_confidence`

- Status: Accepted
- Date: 2026-10-13 (session 25, simulator)
- Supersedes: part of decision 0035 (TRAP-SCANNER-HITS "best `verify`"):
  a scanner or probe rule with hit counts only and no visible end of its
  application now has best `keep`. Schema change under decision 0017.

## Context

`expected.max_justified_confidence` is computed from the evidence that is
not misleading. It answers "how sure may one be of the true intent", with
knowledge of which evidence lies. Calibration scoring (`eval/verdicts.py`)
counts a rule as overconfident when palimp's confidence is above it.

The project lead challenged this (session 25 prompt): overconfidence is
measured on traps that no artifact reveals. On such a rule, a perfect
analyzer sees misleading evidence that looks exactly like sound evidence,
and the confidence it can justify from the artifacts is the one that
evidence supports. `best_achievable_verdict` already makes this distinction
for verdicts; nothing did it for confidence.

Session 25 audited the two traps where it matters on Hard dev seeds 0 to 49
(text checks on the generated artifacts, simulator 0.3.0):

TRAP-STALE-NAME, 328 rules (38 scenarios, 69 replaced applications):

| Trace in the artifacts | Rules |
|---|---|
| commits.txt names the new application | 24 |
| tickets.csv names the new application | 136 |
| config.set names the new application anywhere | 214 |
| an address object named for the new application on the rule's address | 126 |
| rollback files name the new application | 214 |
| rt_flow.log names the new application | 48 |
| ... on a line to or from the rule's address | 32 |
| repoint visible in the rollbacks (changed address values) | 30 |
| exported decommission ticket for the old application | 53 |
| any trace of the new application | 246 |
| no trace of the new application | 82 |
| no trace at all (new application or replacement) | 60 |

Most mentions of the new application are not tied to the rule: its other
tiers get new objects (`ecm-db-01`) while the rule's web object is
repointed. A link exists when the trace is on the rule's own address or
history. With links only: 226 rules traced, 102 unobservable (31%).

TRAP-SCANNER-HITS, 102 rules: 45 log their sessions (the probe shows in the
log lines, observable). 57 have hit counts only; 21 of them have a visible
end of their application (exported decommission or migration ticket, or a
retained decommission or migration commit). 36 have nothing (25 scanner, 11
monitoring): their hits read as business use.

## Decision

1. Hard rules gain `expected.best_achievable_confidence` (`LOW`, `MEDIUM`,
   `HIGH`): the highest confidence a perfect analyzer can justify from the
   artifacts alone. It is computed like `max_justified_confidence`, except
   that misleading evidence of an unobservable trap counts as sound (it is
   indistinguishable from sound evidence). It equals
   `max_justified_confidence` on every other rule, and is never below it.
   `max_justified_confidence` keeps its meaning.
2. A TRAP-STALE-NAME rule is unobservable when no artifact links it to the
   replacement: the repoint commit is not in the rollback diffs and its
   comment is not retained; no exported decommission ticket for the old
   application; no address object named for the new application on one of
   the rule's addresses; no other policy that shares the rule's objects or
   addresses and names the new application (name, description, annotation
   in hierarchical output, address objects); no log line of a policy naming
   the new application to or from the rule's host addresses. A bare mention
   of the new application elsewhere is not a link. Its masked evidence:
   description, annotation, creation comment (unless it is misleading for
   another trap), address objects, policy name.
3. A TRAP-SCANNER-HITS rule is unobservable when it does not log and no
   artifact shows the end of its application: no exported decommission
   ticket for it, and no decommission, migration or migration cleanup event
   of it after the rule's creation with an exported ticket or a commit
   visible in the rollback diffs (or retained with a comment). Its masked
   evidence: the hit count. Its `best_achievable_verdict` becomes `keep`
   (was `verify`): nothing visible tells the probe hits from business use.
4. Hard only. Easy and Medium documents do not carry the field and stay
   byte-identical (checked on seeds 0 to 9 of each). The field is optional
   in the schema; `schema_version` stays 1 (decision 0017 point 2). No
   simulator version bump: the version string is written into every
   document, so a bump would change Easy and Medium bytes too. Hard seed 0's
   golden hash changes.
5. Results on Hard seeds 0 to 49: 102 stale-name rules unobservable (best
   above the ceiling on 97 of them: 75 LOW to MEDIUM, 22 LOW to HIGH), 36
   scanner rules unobservable (best verdict `keep`, confidence above the
   ceiling on 5, MEDIUM to HIGH). The text audit agrees: every rule the
   simulator calls traced has a trace in the artifacts, and the 36 scanner
   rules are the same.

## Alternatives considered

- Lower `max_justified_confidence` to what the artifacts allow: one field,
  but it would erase the "knowing what lies" ceiling, and Easy and Medium
  would change. Rejected.
- A per-rule `observable: false` flag, letting the evaluation drop those
  rules from calibration: simpler, but it hides them from the HIGH-must-be-
  right metric too, and gives no ceiling for rules with a partial trace.
- Count any mention of the new application as a trace (60 unobservable
  instead of 102): the analyzer cannot tie a bare mention to the rule.
  Rejected; the audit numbers keep both readings.
- For scanner rules, keep best `verify`: it asks for a judgment no artifact
  supports. Rejected by the mission (set best values from observability).
- Add the links as evidence items (T1 decommission ticket, T3 twin object):
  would improve evidence recall scoring, but changes `max_justified` on
  traced rules. Left for a later session.

## Consequences

- Analyzer sessions: read `best_achievable_confidence` when present
  (Hard), fall back to `max_justified_confidence` otherwise. The
  evaluation (`eval/verdicts.py`) still scores overconfidence against
  `max_justified_confidence`; reporting it against the new field is an
  analyzer-side change, not made here.
- A rule can now be best `keep` while its truth verdict is
  `removal_candidate` (36 scanner rules on 0 to 49): `keep` is the safe
  direction, and the dangerous-error count (decision 0038) is unaffected.
- Previously generated Hard scenarios are stale: regenerate them.
- Calibration on HIGH ("HIGH must be right 90%+") still counts these rules:
  HIGH on a stale-name rule names the wrong application.

## Challenged by Nathan

Yes: this decision answers the challenge "overconfidence measured on
unobservable traps" (session 25 prompt). The scope (Hard only, Easy and
Medium byte-identical, best values for scanner rules with hit counts only)
comes from the prompt.
