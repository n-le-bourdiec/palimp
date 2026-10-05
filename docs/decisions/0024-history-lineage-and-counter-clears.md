# 0024 History lineage, migration leftovers and counter clears

- Status: Accepted (amended 2026-10-05)
- Date: 2026-10-05

## Context

The rollbacks show more than which commit created a policy: they show the
policies a commit removed, deactivated or copied elsewhere. Session 14 left
183 dead rules at `verify` on Medium dev seeds 0 to 19 (best achievable
`removal_candidate`) and 117 not-live rules at `keep`. TRAP-EMERGENCY-
LOADBEARING was handled only through the "temporary" label in the name.

Decision 0020 allows `removal_candidate` only with a positive not-live
signal; absence of traffic alone is never one. Its list of examples already
named "the destination is never seen in any log while other logging rules
are seen" as a future signal.

## Decision

History lineage (`palimp.lineage`, T3):

- Takeover: a policy covers the whole match (same zone pair; every source and
  destination address inside its own, resolved to IP networks through the
  active address book and then the rollbacks; its applications a subset, or
  `any`) of policies that a commit removed or deactivated while this policy
  existed. Whatever traffic they carried now matches this policy. It is cited
  by `V-TEMPORARY-IN-USE`, and a new rule `V-TAKEOVER-IN-USE` (verify) covers a
  permit-any policy with traffic and a takeover but no "temporary" label. A
  takeover is never a removal signal.
- Migration leftover, a positive not-live signal: a later commit added at
  least two policies copying existing ones (same zones, sources and
  applications) to a new destination host that names the same application
  and does not overlap the old one. A policy still pointing only to old hosts
  is a leftover when it logs its sessions and no log line of any policy (allow
  or deny, source or destination) shows an address of the old hosts in the
  whole log window. Both facts are needed: the history says the host was
  replaced, the logs say the old host is silent while this policy would show
  its traffic. With hits on the counters it is a contradiction (`verify`).

Counters (`palimp.counters`):

- A policy whose log shows sessions but whose counter is 0 had its counter
  cleared after its last logged session. Every hit count line of that zone
  pair says so, and a blind T2 item `counter_clear` is added.
- Every policy of a zone pair (at least three) at 0 while other zone pairs
  show hits: the zone pair's counters were probably cleared, at an unknown
  date; the count line says that zero says nothing about older use.
- A clear only changes what a count means, never a verdict on its own.

Old hits and stopped flows (verify, never `removal_candidate`):

- `V-TRAFFIC-NOT-RECENT`: hits on the counters and no log line in the window
  although the policy logs: the hits are older than the window. If counters of
  the zone pair were cleared inside the window, the reason says that either
  this counter was not cleared or logging misses the traffic.
- `V-TRAFFIC-STOPPED`: logged traffic on at least 5 days, on half the days of
  its span or more, then no session in the last 14 days or more of the window,
  a silence longer than twice any earlier gap.

## Alternatives considered

- Takeover as a live signal giving `keep`: rejected, it is a fact about the
  configuration, not about traffic. The removed policies may have been dead.
- Migration leftover from naming alone (`-new` suffixes, "migration" in a
  comment): rejected, it encodes naming habits; the copied matches and the
  silent address are structural.
- Migration leftover without the log check, or with the policy's own
  absence only: absence alone is what decision 0020 forbids. A migration in
  progress keeps the old host in the logs, which blocks the signal.
- Old destination silent in the logs without a migration: that is the
  decision 0020 example; not done here, the migration is what makes it a
  positive signal.
- Treating a zero after an inferred clear as blind: no verdict changes with
  it (zero gives `verify` either way), so the count stays `absent` with the
  meaning stated.

## Consequences

- Medium dev seeds 0 to 19: verdict vs best 90.3% to 91.4%, dead rules at
  verify 182 to 171, not-live rules at keep 117 to 94, dangerous errors 0.
  Seeds 20 to 99 (checked, not tuned): 91.2% to 92.0%, dead rules at verify
  693 to 652, not-live rules at keep 400 to 342, dangerous errors 0. Every
  rule whose verdict changed on 20 to 99 is not live: 41 migration leftovers
  to `removal_candidate`, 71 old hits on a migration leftover to
  `V-CONTRADICTION` (still verify), 58 stopped flows from keep to verify.
- Takeover is found on 16 of the 35 TRAP-EMERGENCY-LOADBEARING rules of seeds
  0 to 19; the others' covered policies were removed before the retained
  history (TRAP-HISTORY-HORIZON), so the label stays their only signal.
- Counter clears inside the log window never occur on Medium dev seeds 0 to
  19 (the clear is always before the window), so that part is covered by unit
  tests only.

## Challenged by Nathan

Before session 16: not challenged. The mission asked for each signal that can
move a rule toward `removal_candidate` to be validated at zero dangerous
errors on seeds 0 to 99 (migration leftover: 0).

Session 16 (2026-10-05), challenged: "old destination silent in every log" is
not a removal signal on its own. Outcome: accepted, see the amendment below.

## Amendment (2026-10-05, session 16)

Records two outcomes of the project lead's review. The decision itself is
unchanged; this states its limits explicitly.

- `V-TRAFFIC-STOPPED` was an initiative outside the session 15 mission. It is
  recorded as an approved extension. It only moves rules from `keep` to
  `verify` (the safe direction), which is the kind of initiative CLAUDE.md
  now allows without prior approval, if flagged in the session report.
- An old destination silent in every log is not a removal signal on its own.
  A job that runs rarely (TRAP-RARE-JOB: yearly, quarterly, disaster recovery)
  is silent for a whole log window and still live. Silence counts toward
  `removal_candidate` only combined with an observed migration (the
  migration leftover above: a later commit copied the policies to a new
  host). The decision 0020 example "destination never seen in any log while
  other logging rules to neighboring hosts are seen" stays not implemented,
  and implementing it alone would need a new decision approved by the
  project lead.
