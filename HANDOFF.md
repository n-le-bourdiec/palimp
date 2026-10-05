# Handoff

## Last session: 10 (2026-10-05), simulator: variable Medium trap counts

### Note for analyzer sessions

- Ground truth schema: event kind `access_request` was added in session 9
  (decision 0017, additive, `schema_version` stays 1). Accept it wherever event
  kinds are mapped. From now on every schema change gets a decision file and a
  note here (CLAUDE.md).
- Simulator 0.3.0 (decision 0018): a Medium scenario can contain none, one or
  several instances of TRAP-LIVE-NOLOG, TRAP-RARE-JOB,
  TRAP-EMERGENCY-LOADBEARING, TRAP-MISLEADING-COMMENT and TRAP-BATCH-COMMIT.
  The hit count clear (`hit_count_clears` in the manifest) can be on servers
  to internet, servers to management or management to servers. Per-trap
  metrics must be computed over the scenarios that contain the trap.

### Done

- Session 9 metrics row finalized (125 calls, 12.40 USD API-equivalent).
- Trap counts drawn per Medium scenario (sub-generator `trap_counts`, weights
  in `levels.TRAP_COUNT_WEIGHTS`); the knobs `emergency_per_year`,
  `rare_jobs` and `misleading_comment_rate` are gone (replaced by the
  weights). Several batch commits and several copied comments per scenario are
  possible.
- Hit count clear decoupled from rare jobs: pair drawn on its own
  (sub-generator `hit_count_clear`); weekly no-log jobs go in that pair (two new
  job shapes with the backup server, intent `backup`); rare jobs stay
  application to partner. A RARE-JOB rule sits in the cleared pair in 21 of
  100 scenarios, by chance.
- Cleanups are now one a year, independent of emergencies (each emergency is
  placed 90 to 150 days before one of them), so TRAP-DEACTIVATED stays in
  every scenario.
- Measured over Medium seeds 0 to 99 (rules tagged per scenario):
  LIVE-NOLOG 73% (0 to 2), RARE-JOB 68% (0 to 2), EMERGENCY-LOADBEARING 83%
  (0 to 3), MISLEADING-COMMENT 72% (0 to 15), BATCH-COMMIT 71% (0 to 25),
  HISTORY-HORIZON 100% (40 to 105), DEACTIVATED 100% (1 to 25). 156 policies
  on average (125 to 194), 20.5% dead rules (9.9 to 36.5%).
- Simulator 0.3.0. Easy output identical apart from the version string
  (checked by `test_easy_changed_only_by_version` against the 0.2.0 hashes);
  golden hashes updated.
- New pytest marker `full`: Medium seeds 10 to 99 (trap distribution test,
  leakage) run only with `--runslow`; CI runs Medium on seeds 0 to 9.
- CLAUDE.md: schema changes need a decision file and a HANDOFF note.
  Decisions 0017 (access_request) and 0018 (trap counts, clear placement).
- Spec 5.5, 7.1, 7.2, 7.4 updated.

### Next

- Analyzer session: run the readers on Medium scenarios (all format
  combinations, deactivate lines, `via netconf`, `match application any`,
  skewed syslog-server prefixes); the black-box test only covers Easy.
- Analyzer plan from session 5: T2 collectors, T4, confidence scoring and
  verdicts, `report` and `questions`; then a first Medium evaluation.
- Simulator: standard (unstructured) RT_FLOW format as a knob; DENY messages;
  stored rollback files (S2).

### Open questions

- Weights in `TRAP_COUNT_WEIGHTS` were set by hand to land in 60 to 90%;
  should Hard reuse the same mechanism with higher counts?
- A copied comment on an operator commit split per site tags up to 15 rules,
  and a batch commit up to 25: per-trap metrics counted per rule are weighted
  by these large instances. Count per instance (commit) instead?
- Medium is about 8 MB per scenario; 100 scenarios are 0.8 GB. Reduce
  `log_samples_per_policy_day` or keep?
- TRAP-HISTORY-HORIZON tags about 69 rules per scenario: per-trap metrics will
  be dominated by it. Tag it only on rules with no other trap?
- Emergency rules are committed by whichever human admin is on call; the
  `on_call` persona is not a separate admin at Medium.
- Carried over: decision 0015 as a separate decision; `commit activate` as a
  commit type; CONFIRMED-TEXT acceptance; Easy 100% recall says little;
  scenario directory names without overrides.

### Known issues

- VSRX-2b unverified: deactivated policies are left out of hit counts.
- When the clear lands on management to servers or servers to management,
  other live rules of that pair with sparse traffic may show zero hits too
  (not tagged as traps; their best verdict is `verify` through the generic
  hidden-live rule).
- Ticket assignee can be `svc-ansible` (automation deploys an application);
  realistic for a pipeline, but unusual in a ticket export.
- S2: stored rollback files not emitted. S5: no system commits besides the
  rescue line; `via netconf` unverified.
- Git identity is set in the repository config only (`n-le-bourdiec`).
- Session 2 Part C checks (WSL, KVM, Docker) are still not done.

## Measuring tokens and cost

From session 6 on, each session starts in a fresh Claude Code conversation,
so one session maps to one transcript and `--since`/`--until` are no longer
needed. Sessions 1 to 5 shared one conversation, which explains their high
cache-read counts: every call re-read the whole history of earlier sessions.

Claude Code stores each conversation as JSONL in
`~/.claude/projects/d--projet-code-Palimp/<session-id>.jsonl`. Sessions 1 to 5
share transcript `3a8f81f6-6569-476c-acc9-fee746e79b0b`. Boundaries are the
timestamps of the opening prompts:

- session 1: until `2026-09-28T14:58:54.152Z`
- session 2: `2026-09-28T14:58:54.152Z` to `2026-10-04T17:18:08.869Z`
- session 3: `2026-10-04T17:18:08.869Z` to `2026-10-04T17:41:05.995Z`
- session 4: `2026-10-04T17:41:05.995Z` to `2026-10-04T18:26:35.446Z`
- session 5: since `2026-10-04T18:26:35.446Z` (finalized in session 6)

Session 6 has its own transcript `72beb9ef-54f4-42f0-8f55-6f97aafd613c`
(finalized in session 7). Session 7 has transcript
`cd397e63-3f27-4583-ab2d-1855580dff63` (finalized in session 8). Session 8 has
transcript `f5449cc1-ac4a-4d11-aab3-d77d2bc207ee` (finalized in session 9).
Session 9 has transcript `60a6f3c8-c28b-457e-8a93-e9da7abb4439` (finalized in
session 10). Session 10 has transcript `3649919e-84f0-4cd3-8b8d-c49cc31eff22`.
Finalize it at the start of session 11 with:

    uv run python metrics/session_tokens.py 3649919e-84f0-4cd3-8b8d-c49cc31eff22

Cost is API-equivalent (decision 0006), not a billed amount.
