# 0022 Application owners and name abbreviations learned from the artifacts

- Status: Accepted
- Date: 2026-10-05

## Context

Session 13 found that every T1-T3 conflict on an untrapped rule of Medium dev
seeds 0 to 19 was false: `mon-01` and `servers-net` were read as applications
`mon` and `servers`, while the description and the ticket name `monitoring`.
The `ask` line named the right owner on 18.5% of the rules: it was only
filled for non-keep verdicts, used the latest requester of an application as
a contact, and fell back to the commit user, an administrator.

Ground truth `owner_to_ask` is the owner of the rule's application. palimp
must find it from the artifacts only (independence rule), and must never
state a wrong owner with certainty: a confident wrong name sends the engineer
to the wrong person and hides the doubt.

## Decision

Vocabulary (`palimp.apps`):

- Role words that say what kind of host or network, not which application
  (`servers`, `server`, `srv`, `mgmt`, `lan`, `subnet`, `network`, plus the
  existing `users`, `net`, `all`, ...), never name an application.
- Ticket summary aliases are learned before object name segments, so a
  segment that is a ticket alias names that application (`bkp` with tickets
  `BKP ...` for `shared-backup`).
- An object name segment of at least 3 letters that is the start of exactly
  one related CI is an abbreviation of it (`mon` for `shared-monitoring`).
  Shorter segments are never expanded (`bi` must not become `billing`).
  Free text gets no prefix matching (`web` must not name `webshop`).

Owners (`palimp.owners`):

- Candidates come from the requester of a ticket the policy references, the
  requesters of the tickets whose related CI is an application the policy
  involves (new T3 evidence kind `app_requesters`, so the ask line cites an
  evidence ID), and initials after `req` in the description or commit comment
  resolved to the one ticket requester with those initials.
- Commit users and ticket assignees are administrators. They are never owner
  candidates; the ask line names the administrator who created the policy
  apart, as such.
- One owner is stated (field `owner`) only when every source points to the
  same person, no initials stay unresolved, the policy involves one
  application only (the intent and the address objects name one), the intent
  has no T1-T3 conflict, and either that application has at least two
  tickets all requested by that person, or two different sources agree.
- Otherwise the ask line starts with "Not sure who owns it", says why, and
  lists the candidates (field `owner_candidates`, most supported first).
- Every policy gets an ask line, also `keep` ones: who owns a rule is useful
  whatever the verdict. The question stays for non-keep verdicts only.

## Alternatives considered

- A hand-written abbreviation list (`mon`, `bkp`, `dms`...): rejected, it
  would encode the simulator's naming, not learn from the input.
- Subsequence matching for abbreviations (`bkp` in `backup`): rejected, too
  loose; ticket aliases already cover it.
- Owner = top requester of the intent application, stated always: gave 1.7%
  of rules a wrong owner stated with certainty on dev seeds 0 to 19, nearly
  all flows between two applications where the ground truth owner is on the
  other side.
- Aggregating `req` initials over every policy that names an application, to
  name owners of applications with no ticket: measured on dev seeds 0 to 19,
  it would add 10 applications. Left for later.

## Consequences

- Dev seeds 0 to 19: false conflicts on untrapped rules 5 to 0, conflicts on
  MISLEADING-COMMENT rules kept (44 of 44), owner named 18.5% to 85.9%, owner
  stated with certainty and wrong 0. Full before and after numbers are in the
  session 14 report and `HANDOFF.md`.
- Owners of two-application flows are never stated, only listed: the right
  owner is among the candidates but the engineer must pick.
- A real company whose ticket requesters are not application owners (a
  service desk opening tickets for others) would get confident wrong owners
  when one requester files every ticket of an application. The ask line shows
  the ticket count and IDs so the reader can judge.

## Challenged by Nathan

Not challenged.
