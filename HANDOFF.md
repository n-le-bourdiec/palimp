# Handoff

## Last session: 5 (2026-10-04), analyzer milestone 1

### Done

- Session 4 metrics row finalized.
- Slow marker: `conftest.py` skips tests marked `slow` unless `--runslow` or
  the `CI` variable is set. The leakage test runs seeds 0 to 9 locally and
  0 to 99 in CI. Local suite: about 28 s.
- Analyzer (src/palimp only, built from artifacts and the ground truth schema):
  - `models.py`: pydantic models (Policy, AddressObject, Application, Commit,
    Evidence, Finding, Dataset, ...).
  - `formats/`: one reader per vendor format (junos_set, commits, rollbacks,
    hitcount, rt_flow, tickets). Unknown lines are counted and sampled, never
    fatal.
  - `ingest.py`: reads a directory, finds the commit that created each policy
    by diffing consecutive configurations. `palimp ingest DIR -o out.json`.
  - `evidence.py`: T1 (description, creation commit comment, ticket references
    matched against tickets.csv) and T3 (address objects, policies created in
    the same commit). No scoring.
  - `palimp explain FROM/TO/NAME --no-llm [--json] [--all] -a DIR`.
- `eval/evidence_recall.py`: dev seeds only, subprocess black boxes, recall per
  tier. Easy seeds 0 to 19: T1 100% (2033/2033), T3 100% (1416/1416), rules with
  a T1 item found 97.6% (783/802, equal to what the ground truth expects),
  20 T3 items found but not expected (address objects).
- Decision 0011: recall matches on rule, tier and artifact (locators are not
  compared).

### Next

- Finalize session 5's metrics row first.
- Analyzer: T2 collectors (hit counts, logs) and T4, then confidence scoring
  and verdicts, then `report` and `questions`.
- Eval: compare verdicts and confidence once palimp produces them; consider a
  structured locator so recall can check the exact commit or ticket.
- Simulator milestone 2 (Medium with v1 traps) to make the recall numbers
  meaningful.

### Open questions

- 100% recall on Easy says little: Easy evidence is complete and consistent by
  design, and matching ignores locators (decision 0011). Should the next eval
  step be Medium, or a stricter matcher?
- The 20 extra T3 items: palimp reports address objects for some rules where
  the ground truth lists none. My guess is generic objects (users-all, any
  based rules). Which side should change?
- Independence: I wrote the simulator in sessions 3 and 4, so I knew its
  conventions while writing the analyzer, even without opening its files in
  session 5. A truly blind check needs someone else (or a fresh agent without
  that history) to write or review the analyzer.

### Known issues

- Artifact formats are still VSRX assumptions (VSRX-1 to VSRX-12); readers
  are isolated in src/palimp/formats/ for that reason.
- The standard (unstructured) RT_FLOW syslog format is not parsed yet.
- `palimp explain` without `--no-llm` prints a note and the same output (no
  LLM yet).
- Session 5 metrics row is provisional.
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
- session 5: since `2026-10-04T18:26:35.446Z`

Finalize session 5 with:

    uv run python metrics/session_tokens.py 3a8f81f6-6569-476c-acc9-fee746e79b0b --since 2026-10-04T18:26:35.446Z --until <session 6 prompt timestamp>

If session 6 runs in a new conversation, omit `--until`. Find a prompt
timestamp by searching the transcript for `This is session N`. Cost is
API-equivalent (decision 0006), not a billed amount.
