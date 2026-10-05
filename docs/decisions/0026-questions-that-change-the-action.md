# 0026 Questionnaires: only questions that can change the action, one email per person

- Status: Accepted
- Date: 2026-10-05
- Supersedes: the grouping part of decision 0025 ("one per candidate group
  when the owner is unsure", and the rejected alternative "one questionnaire
  per person, merging candidate groups").

## Context

On Medium dev seed 0, session 16 produced 18 questionnaires for 27 rules.
Nathan challenged three points:

1. Useless questions to owners: every removal candidate of seed 0 was
   deactivated. A deactivated rule allows nothing today, so the application
   owner's "yes, still needed" or "no" changes nothing: the flow already
   works (or not) without it. The only open point is whether the firewall
   team keeps it as a rollback switch.
2. One email per person: a person who appeared in several candidate groups
   got several emails, some with a single rule.
3. Questions on keep rules (open question of session 16): keep rules with
   LOW confidence or traffic on the counters only were not mentioned anywhere
   except the keep table.

## Decision

- A question is sent only if its answer can change the action.
- Deactivated rules that are not kept (in practice every deactivated rule,
  since it shows no traffic) are never sent to application owners. They go
  to a "firewall team cleanup list": a section of the report and its own
  file (`00-firewall-team-cleanup.txt` written by `palimp questions`), with
  the question "Is this deactivated rule kept on purpose, as a rollback
  switch?" ("yes" still means keep it). In the report their "Who to ask" is
  the firewall team and they are grouped under it in the verify section.
- One email per person. Section "Rules for your applications" holds the
  rules the person owns with certainty; section "Rules you may own, please
  forward if not" holds the rules the person is an owner candidate for
  (decision 0023). A rule with several candidates is in the second section
  of each candidate's email, with an "Also asked:" line naming the others.
  Rules with no name keep one email per application. Removal candidates come
  first in each section.
- `answers.csv` has one row per asked rule, listing every questionnaire and
  recipient that asks it.
- Keep rules with LOW confidence, or with traffic on the hit counters only,
  are listed in a "Worth a look" section of the report, with the reason and
  its citations. They are never in an email: nothing about them needs an
  owner's answer to decide the action.
- No verdict, confidence or owner changes: this is presentation and routing
  only.

## Alternatives considered

- Keep asking owners about deactivated rules, as context for the firewall
  team: rejected, the answer does not change the action and costs the
  owner's attention.
- Ask the firewall team about every removal candidate: rejected, a
  decommission or migration leftover that is still active is a real question
  for the application owner (yes would keep a live flow).
- Ask owners about counter-only keep rules: rejected, the rule stays in any
  case; a "no" would only start a removal discussion that the report can
  start without bothering the owner.
- One email per candidate group (decision 0025): replaced; the "you may own"
  section states the doubt without stating the rule as theirs, which was the
  reason 0025 rejected merging.

## Consequences

- Medium dev seed 0: 8 files instead of 18 (cleanup list with 20 deactivated
  rules, 6 personal emails, 1 email with no name), covering 27 rules. The
  largest personal email (Quentin Gallo) has 3 rules, all in "you may own".
- Rules with several candidates are asked several times: the answer CSV
  keeps one row per rule, so the tracker merges the answers.

## Challenged by Nathan

Yes, session 17 prompt (three challenges above). Outcome: all three
accepted as stated.
