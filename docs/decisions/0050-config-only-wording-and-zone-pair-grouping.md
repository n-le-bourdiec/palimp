# 0050 Config-only wording, and rules with no owner name grouped by zone pair

- Status: Accepted
- Date: 2026-10-30 (session 35, analyzer)
- Supersedes: decision 0026, the sentence "Rules with no name keep one email
  per application". The rest of decision 0026 stands.

## Context

A manual test by the project lead on a real configuration given alone (no
commit history, no hit counts, no session log, no tickets) found sentences
that did not match the artifacts provided:

- the report named `hitcount.txt` (counter clears, "only the hit counters
  can") when no hit counts were given;
- `explain` printed "created in: before the retained history" when no
  history was given at all;
- the no-visibility question said "(no logging, no counters)" on a policy
  that logs, when the real reason was that no log and no counters were
  provided;
- the initials note said "no ticket requester has them" with no ticket
  export;
- the questionnaire for unnamed rules said "the firewall does not record
  whether this rule is used", which is false when the files were simply not
  given.

And almost every questionnaire file was named
`no-name-found-owner-of-<application>`: on a real configuration the
application palimp guesses from names is often a fragment (a site code, a
server role), so a reader cannot route these emails.

## Decision

1. Every sentence that names an artifact or a traffic source names only
   what was provided. With no hit counts, the "Inferred counter clears"
   blind spot is not written and the no-logging blind spot says no hit
   counts were provided; the summary traffic line has four forms (log and
   counters, log only, counters only, neither). `explain` says "created in:
   unknown, no commit history was provided" when there is no history. The
   no-visibility question lists its actual reasons (the policy does not
   log, no hit counts were provided, no session log was provided, no hit
   count row). The initials note says no ticket export was provided. Empty
   removal candidate and worth-a-look sections print "None." only.
2. Rules with no owner name and no owner candidate are grouped by zone pair
   (`no owner name: trust to servers`, a global policy by its match zones),
   in the report and in the questionnaires (one email per zone pair, file
   `NN-no-owner-name-<from>-to-<to>.txt`). Inside a group, rules to the same
   destination are side by side, removal candidates first in the email.
   Each item of such an email carries a "Who may know:" line (the rule's
   `ask` text: the team running the destination, or the owner of the
   application palimp names).
3. Presentation only: no verdict, confidence, owner or evidence changes.

## Alternatives considered

- Group by destination address: a reader can route it (the server team),
  but a real configuration gives one email per server, dozens of one-rule
  emails, the problem decision 0026 fixed for people.
- Keep grouping by application when the intent is MEDIUM or HIGH, zone pair
  otherwise: two schemes in one folder, and MEDIUM on a real configuration
  often rests on a name fragment.
- Leave the generic sentences and add a note that some artifacts are
  missing: the sentences would still be false on their own, and a report is
  read sentence by sentence.

## Consequences

- Config-only tests (`tests/test_config_only.py`) cover each sentence above
  and the grouping.
- The application palimp believes in is still in each email's subject line
  and in each item ("What it is for").
- Evaluation numbers are unchanged (presentation only).

## Challenged by Nathan

Yes, in the session 35 prompt: the wording found in a manual test and the
request to group questionnaires by something a reader can use (zone pair or
destination). Zone pair chosen, destination order inside a group.
