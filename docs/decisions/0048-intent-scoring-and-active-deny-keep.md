# 0048 Intent scored against what the artifacts allow; every active deny is keep

- Status: Accepted
- Date: 2026-10-29 (session 33, analyzer)
- Supersedes: decision 0044 item 9, the part "an active deny with a not-live
  signal is verify (V-DENY-NOTLIVE)"; decision 0046 item 7, the part "rules
  with no visibility at all stay verify".
- Extends: decision 0047 (best achievable intent and rule kind in the ground
  truth), decision 0036 (Hard table in the held-out workflow).
- Challenged by Nathan: yes (session 33 prompt, 1 challenge): a hidden stale
  name is scored against the name the artifacts show (the replaced
  application of decision 0047), not against null. The session 32 open
  question is closed that way.

## Context

Simulator 0.5.0 (decision 0047) gives every rule `expected.rule_kind` and
`expected.best_achievable_intent`. The evaluation scored intent only against
the true application (`intent.app_id`), so "purpose unknown" on a rule
nothing names was counted wrong, and firewall team rules carried the pseudo
application `firewall`.

Session 31 asked the project lead whether an active deny with no visibility
at all should be keep too (decision 0046 kept it verify).

## Decision

1. **Intent scoring (`eval/verdicts.py`).**
   - Application rules (`rule_kind` application): right when palimp's first
     named application is `best_achievable_intent`. When it is null, palimp
     is right when it names no application ("Purpose unknown", or a flow
     description with no application). palimp must also read the rule as an
     application rule (not as a cleanup, block, broad permit or factory
     default).
   - Firewall team rules: `rule_kind` against palimp's own reading of the
     rule, in the order of the report's intent sentence: catch-all deny
     evidence gives cleanup, then factory default, then broad permit, then a
     deny or reject action gives block.
   - Hidden stale names (85 Hard rules): `best_achievable_intent` is the
     name the artifacts show; confidence stays scored against
     `best_achievable_confidence`. No special case in the script.
   - The old number stays in the output, labeled "vs true application".
   - A summary table gives, for all rules, each rule kind,
     TRAP-SHADOWED-BY-DENY and rules with an `ANY` source (a source object
     named `ANY` or `Any-Hosts`, never the `any` keyword): verdict vs best,
     intent vs best achievable, intent vs true application, overconfidence,
     underconfidence, dangerous errors of palimp and of the naive baseline.
2. **Every active deny or reject rule is keep**, with or without visibility,
   whatever its signals (project lead's answer to the session 31 question).
   Removing a block opens the traffic it blocks; keeping it opens nothing.
   The verdict rule says what the artifacts show: `V-DENY-NOTLIVE` (a
   not-live signal, was verify), `V-DENY-TRAFFIC` (traffic reaches it, was
   `V-TRAFFIC` or a traffic verify rule), `V-DENY-QUIET` (no traffic seen,
   unchanged), `V-DENY-BLIND` (no visibility, was `V-NO-VISIBILITY` verify).
   The rule comes right after `V-CLEANUP-RULE`, before every other verdict
   rule. A deactivated deny follows the usual rules. A deny placed after a
   catch-all deny stays keep (`V-SHADOWED` applies to other rules only).
3. **The question stays, at low priority.** `V-DENY-NOTLIVE` and
   `V-DENY-BLIND` rules stay in the firewall team list ("Is this block still
   wanted?"), in its last section, titled "Rules that block traffic (low
   priority)". The report entry carries the question; the assessment's
   question stays empty (a keep is never asked of an owner).

## Alternatives considered

- Keep `V-NO-VISIBILITY` verify on deny rules (decision 0046): the project
  lead answered keep.
- Drop the deny question entirely: the project lead asked to keep it at low
  priority.
- List every active deny in the firewall team list: rules with traffic on
  them or no traffic seen give no reason to ask; the list would grow with
  every block.
- Score intent with the evaluation's own reading of "purpose unknown" when
  `best_achievable_intent` is absent (ground truth before 0.5.0): the script
  falls back to `intent.app_id` there, as before.

## Consequences

- Verdicts move only toward keep: verify to keep on active deny rules.
- Intent numbers are not comparable with those recorded before session 33;
  the old number is still printed next to the new one.
