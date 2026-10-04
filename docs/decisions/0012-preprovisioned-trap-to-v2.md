# 0012 TRAP-PREPROVISIONED moves to v2; v1 has 7 traps

- Status: Accepted
- Date: 2026-10-04
- Supersedes: the trap list of decision 0008 (only `TRAP-PREPROVISIONED`)

## Context

Decision 0008 put eight traps in v1 of the simulator, including
`TRAP-PREPROVISIONED` (a rule created ahead of a service that is not live yet,
so it has no traffic but must be kept). Session 4 tried to ground each trap in
a public source. `TRAP-PREPROVISIONED` stayed ungrounded: no source was found,
and the project lead has not observed it in practice.

## Decision

`TRAP-PREPROVISIONED` moves to v2. v1 of the simulator has seven traps:
`TRAP-LIVE-NOLOG`, `TRAP-RARE-JOB`, `TRAP-EMERGENCY-LOADBEARING`,
`TRAP-MISLEADING-COMMENT`, `TRAP-BATCH-COMMIT`, `TRAP-HISTORY-HORIZON`,
`TRAP-DEACTIVATED`.

The rest of decision 0008 (Easy and Medium only, v2 knobs set to zero) is
unchanged.

## Alternatives considered

- Keep it in v1 as an invented trap: it would tune palimp against a pattern
  with no evidence that it exists in real firewalls.
- Drop it entirely: it remains plausible, so v2 keeps it until a source or a
  field observation grounds it.

## Consequences

- The simulator spec must mark `TRAP-PREPROVISIONED` as v2 (simulator session,
  not done here, since the spec is out of reach of analyzer sessions).
- Fewer "live but looks dead" cases in v1 evaluation: `TRAP-LIVE-NOLOG`,
  `TRAP-RARE-JOB` and `TRAP-EMERGENCY-LOADBEARING` still cover that error mode.

## Challenged by Nathan

Decision made by Nathan (project lead), session 6.
