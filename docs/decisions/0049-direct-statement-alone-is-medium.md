# 0049 A direct statement alone justifies MEDIUM in the simulator

- Status: Accepted
- Date: 2026-10-29 (session 34, simulator)
- Supersedes: decision 0045 item 2, the part "one source gives LOW", for a
  source that is a direct statement (description or annotation, retained
  creation comment, cited exported ticket). Names (address objects, policy
  names) and services keep the 0045 rule. Spec 6.1 item 4 is rewritten.
- Amends the reading of decision 0047 for `best_achievable_confidence` only;
  `best_achievable_intent` is unchanged (it already counts one source).
- No schema change: `max_justified_confidence` and
  `best_achievable_confidence` keep their enums; only their values move.
- Challenged by Nathan: yes (session 34 prompt, 1 challenge): a direct
  statement of purpose is not a name. The project lead's rule "one source
  is LOW" targeted names. A ticket, a commit comment or a description that
  says which application the rule is for is the strongest tier (T1), and
  session 30 counted it as one ordinary source, so the ground truth said
  LOW where MEDIUM is justified.

## Context

Decision 0045 item 2 counts the naming sources the generator wrote and gives
LOW to one source, whatever its kind. The project lead's model (decisions
0042 to 0044) caps one name at LOW because names are often wrong or partial
(site codes, server roles, people). A direct statement of purpose is a
different kind of evidence: the CLAUDE.md hierarchy puts it at T1, above
behavior and structure. Counting it like an object name made the ceiling
too low on rules whose only source is a description, a creation comment or
a ticket.

## Decision

1. **Medium and Hard** (`sources.confidence`, `truth.py`): when a rule has
   fewer than two counted sources and its one counted source is a direct
   statement (spec 6.1 sources d, e, f), `max_justified_confidence` is
   MEDIUM, unless the rule is disputed, then LOW.
2. **Disputed** (`sources.contradicted`): another artifact the generator
   emitted on the same rule names a different application:
   - the description or annotation, or the retained creation comment, names
     another application of the scenario (spec 6.1 item 1), including a
     batch comment naming another application and a description that names
     both ends of a flow (`BILL AS > FILESRV FS 445` on a `billing` rule);
   - an exported ticket the rule cites has a `related_ci` other than the
     application;
   - the rule carries a copied comment (TRAP-MISLEADING-COMMENT).
   The base of a regional instance (`erp` for `erp-de`) is not another
   application. The pseudo application `firewall` is never one.
3. **HIGH** is unchanged: two counted sources, one of them direct, and
   traffic seen. A direct statement alone with traffic stays MEDIUM.
4. **Two or more sources** keep the 0045 rule; a dispute does not lower
   them (the prompt targets the single statement case only).
5. **Hard `best_achievable_confidence`**: same rule on what the artifacts
   show (decision 0040): a hidden stale name checks the dispute against the
   replaced application, masked T2 evidence counts as traffic.
6. **Easy** keeps the tier rule of spec 6; its artifacts are byte-identical
   and its ground truth changes only by the version string (test
   `test_easy_changed_only_by_version`, 0.5.0 entry).
7. **Version** 0.5.1. Medium and Hard artifacts are byte-identical to 0.5.0
   (checked on seeds 0, 1, 7 of every level); only `ground_truth.json` and
   `manifest.json` change. Simulator 0.5.1 is the release basis; the next
   held-out run uses it.

Measured on Medium 0-99 (15662 application rules) and Hard 0-49 (20771):
every change is LOW to MEDIUM, on application rules only; 1406 Medium rules
(9.0%) and 1033 Hard rules (5.0%) for `max_justified_confidence`, 1037 Hard
rules for `best_achievable_confidence`. 118 Medium and 63 Hard rules stay
LOW because they are disputed. Per trap: HANDOFF.md and the session 34
report.

## Alternatives considered

- A direct statement plus traffic gives HIGH: the prompt says HIGH still
  needs traffic, not that traffic alone is a second source. Kept the 0045
  HIGH rule so calibration of HIGH (90%+) is not loosened without the
  project lead.
- Lower two-source rules when disputed: would move confidence on rules the
  mission does not target. Not done; can be a later decision.
- A description naming both ends of a flow is not a dispute: it does name
  the rule's application, but the reader cannot tell which end the rule is
  for. Counted as a dispute (literal reading of the prompt, conservative).
- A two-letter direct statement (`CI acess`) alone: direct statements are
  not names, so the 0044 two-letter limit does not apply; it gives MEDIUM
  like any other statement.

## Consequences

- Medium and Hard dev numbers on 0.5.1 are comparable with 0.5.0 on
  verdicts and intent (unchanged); confidence calibration moves:
  overconfidence should fall (C-T1-ONLY, session 33), underconfidence may
  rise on rules where palimp still says LOW.
- Analyzer sessions: no schema change, no new enum value (HANDOFF note).
- The stored Hard trap counts do not change (no trap tag moves).
