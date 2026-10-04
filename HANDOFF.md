# Handoff

## Last session: 3 (2026-10-04), decisions 0007 to 0009 and simulator milestone 1

### Done

- Session 2 metrics row finalized.
- Decision 0007: held-out evaluation only in GitHub Actions (`HOLDOUT_SALT`
  repository secret, `workflow_dispatch`, aggregate output only). Spec 8.2
  updated. Workflow not written yet.
- Decision 0008: v1 simulator scope is Easy and Medium with 8 traps; other
  traps, Hard and Adversarial are marked v2 in the spec. Medium knobs that only
  feed v2 traps are set to 0 for v1.
- Decision 0009: the simulator is the uv workspace member `palimp-sim`
  (`simulator/src/palimp_sim`), not in the palimp wheel (checked). Ruff TID251
  bans imports in both directions; `tests/test_independence.py` checks it with
  `ast`. CI runs `uv sync --locked --all-packages`.
- `metrics/pricing.json` lists only models whose id is on the official models
  page and whose prices are on the official pricing page (Fable 5.1, Opus 5.5,
  Sonnet 5.5, Haiku 4.5; retrieved 2026-10-04). Unknown models give `n/a` plus a
  warning. Decision 0006 amended.
- Spec: grounding rule plus section 12 "Behavioral grounding" with 12 verified
  sources. Unsourced behaviors and traps are marked UNGROUNDED.
- Simulator milestone 1 (Easy, no traps):
  `uv run palimp-sim generate --level easy --seed N --out scenarios`.
  It writes `artifacts/` (config.set, commits.txt, rollbacks/, logs/rt_flow.log,
  hitcount.txt, tickets.csv), `ground_truth.json` (validated against
  `simulator/src/palimp_sim/schema/ground_truth.schema.json`) and
  `manifest.json`. Determinism golden hashes pass on Windows and in CI (Linux).

### Next

- Finalize session 3's metrics row first (see "Measuring tokens" below).
- Simulator milestone 2: Medium level with the 8 v1 traps.
- Or start palimp itself: pydantic models and the "set" parser, tested on
  simulator output until vSRX fixtures exist.
- Held-out workflow (decision 0007) once palimp can produce a report.

### Open questions

- Easy produces about 19 policies (min 16, max 23 over seeds 0 to 99). The
  spec table says about 40. Should Easy get more apps, or should the spec
  number change?
- Easy has few dead rules (5 removal candidates over 100 seeds, because
  `cleanup_rate` is 0.9). Is that the intended Easy profile?
- Ground truth rule: a dead rule with hits since the last counter reset gets
  `best_achievable_verdict: verify`, not `removal_candidate` (58 cases over 100
  seeds). Confirm this is the scoring you want.
- Three v1 traps are UNGROUNDED (`TRAP-PREPROVISIONED`,
  `TRAP-MISLEADING-COMMENT`, `TRAP-BATCH-COMMIT`). Do you know public sources
  for them?
- CMDB export (spec 5.7) is not generated in milestone 1 (it was not in the
  session 3 list).

### Known issues

- Format details of every artifact are still VSRX assumptions (VSRX-1 to
  VSRX-12 in the spec), including the RT_FLOW SD-ID and attribute order.
- Session 3 metrics row is provisional (measured before the final commit).
- Git identity is set in the repository config only (`n-le-bourdiec`).
- Part C checks of session 2 (WSL, KVM, Docker) are still not done.

## Measuring tokens and cost

Claude Code stores each conversation as JSONL in
`~/.claude/projects/d--projet-code-Palimp/<session-id>.jsonl`. Sessions 1 to 3
share transcript `3a8f81f6-6569-476c-acc9-fee746e79b0b`. Boundaries are the
timestamps of the opening prompts:

- session 1: until `2026-09-28T14:58:54.152Z`
- session 2: `2026-09-28T14:58:54.152Z` to `2026-10-04T17:18:08.869Z`
- session 3: since `2026-10-04T17:18:08.869Z`

Finalize session 3 with:

    uv run python metrics/session_tokens.py 3a8f81f6-6569-476c-acc9-fee746e79b0b --since 2026-10-04T17:18:08.869Z --until <session 4 prompt timestamp>

If session 4 runs in a new conversation, omit `--until`. Find a prompt
timestamp by searching the transcript for `This is session N`. Cost is
API-equivalent (decision 0006), not a billed amount.
