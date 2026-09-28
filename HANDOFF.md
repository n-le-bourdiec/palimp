# Handoff

## Last session: 2 (2026-09-28), metrics housekeeping and simulator spec

### Done

- Session 1 row in `metrics/sessions.csv` finalized with final token counts and
  cost.
- `tokens_cache` split into `tokens_cache_read` and `tokens_cache_write`
  (CLAUDE.md, CSV, script).
- `metrics/pricing.json` (official Anthropic prices, source URL, retrieved
  2026-09-28); `metrics/session_tokens.py` computes the API-equivalent cost and
  accepts `--since` / `--until`. Decision 0006.
- Decision 0001 updated with the real alternatives and the "limp" challenge.
- The GitHub repository was renamed to `n-le-bourdiec/palimp` (GitHub reported
  the move on push). The local `origin` now points to the new URL and 0001 uses
  the new name.
- `docs/simulator-spec.md`: company model, personas, events, artifact formats
  with `[VSRX-n]` assumptions, ground truth schema, difficulty knobs, traps,
  determinism, dev / held-out split, independence rules.
- containerlab / vSRX feasibility: the machine checks could not be run (see
  Known issues). The session report gives the steps and the commands to run.

### Next

- First step of every session: finalize the previous session's metrics row
  (session 2's row is provisional, see below).
- Candidate missions: review of the simulator spec by the project lead; vSRX lab
  setup once feasibility is confirmed; pydantic models and the "set" parser;
  simulator skeleton (company model and seeded RNG only).

### Open questions

- Simulator spec: are the difficulty knob values and the trap list acceptable?
  Is the held-out salt mechanism (secret salt kept by the project lead) the
  split you want?
- Should `simulator` become a separate uv workspace member now, or later?
- Model ids in `pricing.json` other than opus-5-5, fable-5-1, sonnet-5 and
  haiku-4-5 follow the naming pattern but are unconfirmed.

### Known issues

- In session 2, the Claude Code permission classifier blocked the local
  hardware and WSL checks (WSL version, CPU virtualization, RAM, Docker). They
  were not retried by other means. The project lead needs to run them or allow
  them.
- Session 2's metrics row was measured before its final commit, so it misses
  the last few API calls. Finalize it at the start of session 3.
- Git identity is set in the repository config only (`n-le-bourdiec`).

## Measuring tokens and cost

Claude Code stores each conversation as JSONL in
`~/.claude/projects/<project-slug>/<session-id>.jsonl` (slug here:
`d--projet-code-Palimp`). Sessions 1 and 2 share transcript
`3a8f81f6-6569-476c-acc9-fee746e79b0b`, because the conversation was continued.
Each palimp session starts at the timestamp of its opening prompt:

- session 1: until `2026-09-28T14:58:54.152Z`
- session 2: since `2026-09-28T14:58:54.152Z`

To finalize session 2, run:

    uv run python metrics/session_tokens.py 3a8f81f6-6569-476c-acc9-fee746e79b0b --since 2026-09-28T14:58:54.152Z --until <session 3 prompt timestamp>

If session 3 runs in a new conversation, `--until` is not needed. To find a
prompt timestamp, search the transcript for the prompt text (`This is session N`).
Cost is API-equivalent (decision 0006), not a billed amount.
