# Handoff

## Last session: 9 (2026-10-05), simulator: Medium level and the 7 v1 traps

### Done

- Session 8 metrics row finalized (52 calls, 3.48 USD API-equivalent).
- Medium level (`simulator/src/palimp_sim/medium.py`, `levels.MEDIUM`), spec
  7.1 values: 4 years, 25 applications (7 Medium-only templates in
  `catalog.EXTRA_APPS`), 5 zones (management zone `mgmt`/`admin` with
  monitoring, backup, jump hosts), personas senior x2, hurried operator,
  automation (`svc-ansible via netconf`). Volume comes from integrations
  between applications and ad hoc access requests (spec 4.9).
- Seven v1 traps built by the timeline and checked on the final state in
  `truth.py` (spec 7.4): LIVE-NOLOG, RARE-JOB, EMERGENCY-LOADBEARING,
  MISLEADING-COMMENT, BATCH-COMMIT, HISTORY-HORIZON, DEACTIVATED. Each sets
  `expected.verdict`, `best_achievable_verdict`, `max_justified_confidence`
  and misleading evidence items.
- Format knobs drawn per Medium scenario from the seed, recorded in
  `manifest.json` (`format_draw`); 22.2 never drawn; overrides win
  (decision 0016). Medium syslog-server lines carry a constant clock skew of
  1 to 6 seconds (`syslog_clock_skew_seconds`).
- Easy outputs byte-identical: all files of seeds 0 to 99 (plus legacy and
  12.x variants every tenth seed) hashed before and after; golden hashes
  unchanged. Medium-only knobs are left out of the manifest at their
  defaults; simulator version stays 0.2.0 (decision 0016).
- Tests: `simulator/tests/test_medium.py` (coverage of the 7 traps in every
  scenario, seeds 0 to 99 in slow mode; format draw; skew; one "naive reading
  is wrong" test per trap); existing tests extended to Medium seeds; Medium
  golden hash (seed 0).
- Measured over Medium seeds 0 to 99: 148 policies on average (124 to 169),
  19.1% dead rules (10.4 to 32.7%), every v1 trap in 100 of 100 scenarios,
  no shadowed dead rule (a v2 trap) left, 2.6 s and 8.0 MB per scenario.
- Schema: event kind `access_request` added (additive change to the shared
  contract).
- Spec: 4.9, 5.4, 5.5, 7.1, 7.4, VSRX-2b. Decision 0016.

### Next

- Analyzer session: run the readers on Medium scenarios (all format
  combinations, deactivate lines, `via netconf`, `match application any`,
  skewed syslog-server prefixes); the black-box test only covers Easy.
- Analyzer plan from session 5: T2 collectors, T4, confidence scoring and
  verdicts, `report` and `questions`; then a first Medium evaluation.
- Simulator: standard (unstructured) RT_FLOW format as a knob; DENY messages;
  stored rollback files (S2).

### Open questions

- Version: Medium is new in 0.2.0 and Easy did not change, so no bump. The
  next Medium change needs a bump, which changes every Easy file (version
  string). Per-level output versions, or accept the Easy hash change then?
- Schema change `access_request` (event kind) made in a simulator session;
  analyzer sessions read the schema. Acceptable as an additive change?
- Medium is about 8 MB per scenario (logs 60 days, rollbacks 49 x 150
  policies); 100 scenarios are 0.8 GB. Reduce `log_samples_per_policy_day`
  or keep?
- TRAP-HISTORY-HORIZON tags about 62 rules per scenario (40% of rules) and
  TRAP-DEACTIVATED about 15: per-trap metrics will be dominated by them.
  Fine, or tag HISTORY-HORIZON only on rules with no other trap?
- Emergency rules are committed by whichever human admin is on call (senior
  or operator), with on-call voice; the `on_call` persona is not a separate
  admin at Medium (spec lists senior, operator, automation).
- Carried over: decision 0015 as a separate decision; `commit activate` as a
  commit type; CONFIRMED-TEXT acceptance; Easy 100% recall says little;
  scenario directory names without overrides.

### Known issues

- VSRX-2b unverified: deactivated policies are left out of hit counts.
- The LIVE-NOLOG zone pair clear is also on the rare jobs' zone pair
  (servers to internet), so a quarterly job can lose its hits to the clear
  rather than to its schedule.
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
Session 9 has transcript `60a6f3c8-c28b-457e-8a93-e9da7abb4439`. Finalize it at
the start of session 10 with:

    uv run python metrics/session_tokens.py 60a6f3c8-c28b-457e-8a93-e9da7abb4439

Cost is API-equivalent (decision 0006), not a billed amount.
