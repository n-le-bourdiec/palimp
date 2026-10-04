# Handoff

## Last session: 4 (2026-10-04), simulator corrections (Easy)

### Done

- Session 3 metrics row finalized.
- Ground truth leakage fixed: descriptions, commit comments and ticket
  summaries come from `simulator/src/palimp_sim/voice.py` (persona voice built
  from facts: app code, tier abbreviation, port, ticket, requester initials).
  `simulator/tests/test_leakage.py` checks seeds 0 to 99: no visible text
  contains `intent.summary`, none shares more than 60% of its tokens with it
  (worst observed 50%).
- Log consistency: no violation found in the session 3 output. One quote in
  the session 3 report was my extraction error (`grep -m1` printed the first
  CREATE line again). I found and fixed a latent timing bug (a commit's config
  applied from the start of its commit day). `simulator/tests/test_logs.py`
  rebuilds the config in force from commits.txt and rollbacks and checks every
  CREATE/CLOSE line against `session-init` / `session-close`.
- Easy tuned: 20 app templates, 18 apps, 2 decommissions and 1 migration per
  year, `cleanup_rate` 0.35. Seeds 0 to 99: 35 to 45 policies (mean 39.9),
  dead rate mean 17.6% (p10 12.5%, p90 23.3%). Spec knob table updated.
- Decommission and cleanup comments are neutral ("retire X", "X decom"),
  because most rules of a retired app stay.
- CLAUDE.md: amend for facts, supersede for decision changes. The 0006 pricing
  change moved to decision 0010.
- Spec grounding: BATCH-COMMIT (Herzig and Zeller 2013) and MISLEADING-COMMENT
  (CodeFuse-CommitEval 2025) grounded by analogy; vague comments by analogy
  (Tian et al. 2022). PREPROVISIONED stays UNGROUNDED (only indirect leads).
- Golden hashes updated five times (see the session 4 report for the reasons).

### Next

- Finalize session 4's metrics row first.
- Simulator milestone 2: Medium with the 8 v1 traps (TRAP-PREPROVISIONED needs
  a direct source first, or an explicit decision to build it anyway).
- Or start palimp: pydantic models and the "set" parser.

### Open questions

- Dead rules: 621 of 708 get `best_achievable_verdict: verify`, because they
  still have hits since the last counter reset (the app was retired less than
  a year ago). Only 87 can be called removal candidates from the artifacts.
  Is that the profile you want for Easy?
- Test suite time went from 4 s to about 60 s (leakage test on 100 seeds).
  Acceptable, or reduce to fewer seeds in CI?
- Are analogy sources (software engineering commits) acceptable grounding for
  firewall commit behavior, or should those traps count as UNGROUNDED too?

### Known issues

- Artifact formats are still VSRX assumptions (VSRX-1 to VSRX-12).
- Session 4 metrics row is provisional.
- Push 64e22d3 had a failing test (CI red). A shell chain hid the exit code;
  fixed in abe8d5b. Commands now use `set -o pipefail`.
- Git identity is set in the repository config only (`n-le-bourdiec`).
- Session 2 Part C checks (WSL, KVM, Docker) are still not done.

## Measuring tokens and cost

Claude Code stores each conversation as JSONL in
`~/.claude/projects/d--projet-code-Palimp/<session-id>.jsonl`. Sessions 1 to 4
share transcript `3a8f81f6-6569-476c-acc9-fee746e79b0b`. Boundaries are the
timestamps of the opening prompts:

- session 1: until `2026-09-28T14:58:54.152Z`
- session 2: `2026-09-28T14:58:54.152Z` to `2026-10-04T17:18:08.869Z`
- session 3: `2026-10-04T17:18:08.869Z` to `2026-10-04T17:41:05.995Z`
- session 4: since `2026-10-04T17:41:05.995Z`

Finalize session 4 with:

    uv run python metrics/session_tokens.py 3a8f81f6-6569-476c-acc9-fee746e79b0b --since 2026-10-04T17:41:05.995Z --until <session 5 prompt timestamp>

If session 5 runs in a new conversation, omit `--until`. Find a prompt
timestamp by searching the transcript for `This is session N`. Cost is
API-equivalent (decision 0006), not a billed amount.
