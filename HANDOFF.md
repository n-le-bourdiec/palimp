# Handoff

## Last session: 7 (2026-10-04), analyzer: format readers G1 to G10

### Done

- Session 6 metrics row finalized (85 calls, 5.22 USD API-equivalent).
- Decision 0014: extra evidence items are not errors unless misleading. It
  supersedes the session 6 amendment of 0011, which is removed; 0011 is back
  to its original text with a status line pointing to 0014.
- Decision 0015: "practitioner capture" (real device output published by a
  third party) is a second fixture source type; supersedes in part 0013.
  Every fixture header now has a `Source type:` line.
- Fixture `show-system-commit-vmx-2023.txt` (networkcuriosity.com, real vMX,
  Junos 20.4R3-S2.6, December 2023): commit comments on the next line,
  indented 4 spaces. VSRX-4d is now CONFIRMED-OUTPUT.
- `docs/format-assumptions.md`: CONFIRMED split into CONFIRMED-OUTPUT and
  CONFIRMED-TEXT; reader results before and after; gaps section rewritten.
- Readers fixed for G1 to G10 (`src/palimp/formats/`, new `terminal.py`),
  plus syslog-server RT_FLOW (both formats), `session-id-32`, hit-count rows
  in any order. `Commit` gains `commit_type`, `rollback_minutes`, `revision`;
  `HitCount.action` may be empty (legacy layout). `rt_flow.parse_event`
  returns one normalized event (kind, policy, zones, session id, logical
  system, time).
- `tests/test_format_fixtures.py`: one test per gap on the fixtures (18
  tests). The black-box simulator test now also requires zero unknown lines
  in commits, hit counts and logs; simulator output parses identically
  (logs, hit counts, commits compared before and after on easy seed 3).
- `eval/format_fixtures.py`: 1 of 16 reader fixtures parsed before, 14 of 16
  after.

### Next

- Then the analyzer plan from session 5: T2 collectors (hit counts, logs) and
  T4, confidence scoring and verdicts, `report` and `questions`.
- Pass a year to `parse_rt_flow` from `ingest` for standard-format logs (CLI
  option or inference), and handle December to January rollover.
- Simulator session: S1 to S6, and mark `TRAP-PREPROVISIONED` as v2 in
  `docs/simulator-spec.md` (decision 0012). Consider emitting syslog-server
  shapes and the standard RT_FLOW format as knobs, now that the analyzer reads
  them.

### Open questions

- Decision count: the session 7 prompt says one decision changed; this
  session recorded two (0014, and 0015 because 0013 explicitly rejected blog
  sources). Confirm 0015 is wanted as a separate decision.
- `commit activate` is read as a commit type, not a comment, although
  `show system commit revision detail` printed `Comment : commit activate`.
  Fine for T1 (it carries no intent), but not proven.
- Is text evidence (documentation prose) acceptable to CONFIRM a behavioral
  assumption? Now explicit as CONFIRMED-TEXT, can be downgraded.
- Carried over: 100% recall on Easy says little (Medium or a stricter matcher
  next?); the harness does not yet classify extra items as misleading or
  neutral (decision 0014).

### Known issues

- Open format gaps (see `docs/format-assumptions.md`): `show system commit
  revision detail` lines stay unknown (other command); the wrapped RT_FLOW
  page sample needs its line wrapping undone; standard RT_FLOW lines have no
  year, so `ingest` leaves their first and last seen times unset; DENY and
  current-release standard lines are tested on lines built from the
  templates, not on published lines.
- Most documentation samples are old (12.x, 13.x) or state no release.
- `palimp explain` without `--no-llm` prints a note and the same output (no
  LLM yet).
- Session 7 metrics row is provisional (measured before the final commit).
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
`cd397e63-3f27-4583-ab2d-1855580dff63`. Finalize it at the start of session 8
with:

    uv run python metrics/session_tokens.py cd397e63-3f27-4583-ab2d-1855580dff63

Cost is API-equivalent (decision 0006), not a billed amount.
