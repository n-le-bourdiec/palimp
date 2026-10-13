# 0041 Strict observability reading, shared address questions, overconfidence scoring

- Status: Accepted
- Date: 2026-10-13 (session 26, analyzer)
- Confirms: decision 0040 item 2 (strict reading of a TRAP-STALE-NAME link).
- Extends: decision 0026 (questionnaire grouping) for V-SHARED-ADDRESS rules
  (decision 0039 item 4).

## Context

Decision 0040 left one open question for the project lead: a TRAP-STALE-NAME
rule counts as observable only when a trace of the replacement is tied to the
rule (its address, objects or history): 102 unobservable rules on Hard 0 to
49. Counting any mention of the new application anywhere in the artifacts
would leave 60. Decision 0040 also proposed, as an alternative, adding those
links as evidence items in the ground truth, so that evidence recall could
see them.

Decision 0039 item 4 puts every policy on an address shared by several
objects named after different applications in verify (V-SHARED-ADDRESS),
with both applications as candidates. The questionnaires (decision 0026)
then sent one question per rule to every owner candidate: many emails for
one fact (which application now runs on this address), which the firewall
team knows better than any application owner.

## Decision

1. **Strict observability reading confirmed** (challenge by the project lead,
   session 26 prompt). A trace makes a trap observable only when it is tied
   to the rule: on its own addresses, objects or history. A bare mention of
   the new application elsewhere is not a link. `best_achievable_confidence`
   stays as decision 0040 computes it.
2. **Trace links as ground truth evidence: postponed to after release.**
   The ground truth does not list the links as evidence items for v1;
   evidence recall does not score them.
3. **Shared addresses are asked of the firewall team.** A V-SHARED-ADDRESS
   rule keeps its verify verdict. Its report group is the firewall team, its
   question "These objects share this address: which application runs on it
   today?", asked once per address shared by several objects (all the rules
   it puts in verify listed under it), in the firewall team list
   (`00-firewall-team-cleanup`), with the deactivated rules. No owner email
   asks these rules. The report gets a "Shared addresses" section.
4. **Overconfidence scoring** (`eval/verdicts.py`): against
   `expected.best_achievable_confidence` when present (Hard rules), else
   `max_justified_confidence`; the count against `max_justified_confidence`
   alone is printed next to it.

## Alternatives considered

- Loose reading (any mention of the new application): 60 unobservable stale
  rules instead of 102. Rejected by the project lead: a mention that nothing
  ties to the rule does not let an analyzer suspect that rule.
- Keep shared address rules in owner emails, grouped per address: owners of
  either application would still answer for a fact they may not know, and
  the same address would appear in several emails.
- Move shared address rules to keep, or drop the question: rejected, the
  verify verdict is the safe one (working rule 2).

## Consequences

- Hard dev seeds, overconfidence (session 26, no analyzer change):

  | seeds | rules | vs best achievable | vs max justified |
  |---|---|---|---|
  | 0 to 19 | 8260 | 1.0% (85) | 1.6% (136) |
  | 20 to 49 | 12490 | 0.9% (116) | 1.3% (163) |

  HIGH at or below best achievable: 98.9% (0 to 19), 99.0% (20 to 49).
  TRAP-STALE-NAME stays the most overconfident trap (52.9% and 65.5% of its
  rules above best achievable, 84.7% and 92.4% above max justified).
- Verdicts and confidence are unchanged by item 3: only the report grouping,
  the questions and the questionnaires change.
- Evidence recall cannot credit palimp for finding a stale name link until
  item 2 is revisited.

## Challenged by Nathan

Item 1 answers the open question of decision 0040 (challenge 1 of 1 in the
session 26 prompt): strict reading confirmed. Items 2 to 4 were asked in the
same prompt.
