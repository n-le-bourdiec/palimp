# 0021 Held-out seed space, held-out scenario ids and the held-out run record

- Status: Accepted
- Date: 2026-10-05

## Context

Decision 0007 puts held-out evaluation in a GitHub Actions workflow started by
the project lead, with the salt in the `HOLDOUT_SALT` repository secret. Spec
section 8.2 derives held-out seeds from `SHA-256("<salt>:<level>:<index>")`.
Session 13 implements it and has to settle three points the earlier texts left
open: how held-out seeds are kept apart from dev seeds, what the held-out
scenario id is (the ground truth schema requires `^[a-z]+-[0-9]{6}$`, and a
64-bit seed does not fit), and what each run leaves behind.

## Decision

- Held-out seed = `2**63` + first 8 bytes of the digest (big endian). Dev
  seeds must be in `[0, 2**63)`; `generate` rejects anything else. The two
  sets cannot collide.
- `palimp-sim generate --holdout INDEX` reads the salt from the environment
  only, and fails with exit code 2 and a message naming `HOLDOUT_SALT` when it
  is missing or empty.
- No generated file carries the salt or the derived seed. The held-out
  `scenario_id` is `<level>-<index>` (6 digits), which fits the ground truth
  schema unchanged. The manifest carries `split: held-out` and
  `holdout_index` instead of `seed`. The output directory is
  `scenario-holdout-<level>-<index>`, so it is never mistaken for a dev one.
- The workflow prints aggregate tables only: headline, calibration, per trap
  and per format variant (decision 0007 named per level and per trap; per
  format variant is aggregate too and is added). No per-rule line, no
  dangerous-error list, no scenario file, no uploaded artifact.
- Every run writes a run record as the job summary: date, palimp commit,
  simulator version, number of scenarios, the aggregate tables. Generated
  scenarios are deleted at the end of the job, even on failure.
- Dev output is unchanged (golden hashes), so the simulator version stays
  0.3.0.

## Alternatives considered

- Held-out seed = the raw 256-bit digest: as safe, but a 77-digit seed is
  awkward; 64 bits above a floor is enough.
- No floor, rely on hash spread: a collision with a small dev seed is
  improbable but not impossible; the floor makes it impossible.
- Held-out `scenario_id` built from the seed: would break the schema pattern
  and print a derived value in every error message.
- A new schema field or pattern for held-out ids: a schema change needs its
  own decision and analyzer note (decision 0017) for no gain.
- Held-out ids in a disjoint 6-digit range (for example 900000 and up): only
  delays a collision with dev ids; the manifest `split` already tells them
  apart.

## Consequences

- A held-out `scenario_id` can equal a dev one (`medium-000003`). Tools must
  look at the manifest `split`, as `eval/verdicts.py` does.
- The agent still cannot generate held-out scenarios: it has no salt.
- Each held-out run is visible in the Actions history and in its job summary.

## Challenged by Nathan

Not challenged. The session prompt (session 13) asked for the mechanism, the
clear failure without the variable and the run record.
