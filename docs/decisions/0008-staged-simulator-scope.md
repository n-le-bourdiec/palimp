# 0008 Staged simulator scope: v1 is Easy and Medium with 8 traps

- Status: Accepted
- Date: 2026-10-04

## Context

The simulator spec defines four difficulty levels and sixteen traps. Building
all of them before palimp exists would delay the first end to end evaluation by
many sessions, and most of the harder traps only matter once the basic analyzer
works.

## Decision

v1 of the simulator implements:

- difficulty levels Easy and Medium only;
- eight priority traps: `TRAP-LIVE-NOLOG`, `TRAP-RARE-JOB`,
  `TRAP-PREPROVISIONED`, `TRAP-EMERGENCY-LOADBEARING`,
  `TRAP-MISLEADING-COMMENT`, `TRAP-BATCH-COMMIT`, `TRAP-HISTORY-HORIZON`,
  `TRAP-DEACTIVATED`.

Hard, Adversarial and the eight other traps stay in the spec, marked v2. In v1,
Medium knobs that would only produce v2 traps (IP reuse, renames, cleanup
mistakes, contractor periods with shared logins, repoint migrations) are set
to zero.

## Alternatives considered

- All four levels and all traps in v1: complete, but long before any score.
- Easy only in v1: fastest, but without traps the scores say little about the
  failure modes that matter (removal candidate on a live rule).

## Consequences

- The first evaluation covers the most dangerous error modes (live rules that
  look dead: `TRAP-LIVE-NOLOG`, `TRAP-RARE-JOB`, `TRAP-PREPROVISIONED`,
  `TRAP-EMERGENCY-LOADBEARING`) early.
- v1 scores are not comparable with v2 scores; the simulator version in each
  manifest makes that explicit.
- The spec marks v2 items so later sessions do not build them by accident.

## Challenged by Nathan

Yes. Nathan challenged the v1 scope (all levels and traps). Outcome: decision
taken to stage the scope.
