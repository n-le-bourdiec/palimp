# Handoff

## Last session: 6 (2026-10-04), format assumptions vs Juniper documentation

### Done

- Session 5 metrics row finalized (29 calls, 3.74 USD API-equivalent).
- Noted below: one Claude Code conversation per session from session 6.
- Decision 0012: `TRAP-PREPROVISIONED` moves to v2; v1 has 7 traps
  (supersedes the trap list of 0008).
- Decision 0013: documentation-sourced fixtures replace the vSRX lab for now
  (supersedes the vSRX lab line of 0005 and the matching consequence of 0003).
- Decision 0011 amended: extra evidence items are not errors unless misleading.
- CLAUDE.md: independence rule (analyzer sessions read neither `simulator/`
  nor `docs/simulator-spec.md`, only the ground truth JSON Schema; simulator
  sessions do not read `src/palimp`), and the fixture source line.
- 19 fixtures in `tests/fixtures/junos_docs/`, each copied from a Juniper
  documentation page or the System Log Explorer data, with source URL, page
  title, release and retrieval date.
- `docs/format-assumptions.md`: VSRX-1 to VSRX-12 split into 26 claims;
  CONFIRMED 12 (2 only in part), CORRECTED 7, UNVERIFIED 7. Reader results on
  the fixtures and gaps G1 to G10 (analyzer) and S1 to S6 (simulator).
- `eval/format_fixtures.py`: runs the readers on the fixtures. Today: 6 of 15
  reader fixtures parse apart from prompt lines (2 of them leave text in
  `extra`), 9 show real gaps.

### Next

- Analyzer session: fix G4 to G9 in `src/palimp/formats/` (commit `extra`
  text, right-aligned indexes, hit-count layouts, `_LS` messages, collector
  prefix, text after `]`), then G10 (standard RT_FLOW) and G1 (prompt lines).
  Turn `eval/format_fixtures.py` results into tests once they pass.
- Simulator session: S1 to S6, and mark `TRAP-PREPROVISIONED` as v2 in
  `docs/simulator-spec.md` (decision 0012; not done here because analyzer
  sessions must not read the spec).
- Then the analyzer plan from session 5: T2 collectors (hit counts, logs) and
  T4, confidence scoring and verdicts, `report` and `questions`.

### Open questions

- VSRX-4d, where the commit comment is printed, is the riskiest open point:
  the spec puts it on the next indented line, the only documentation hint puts
  it on the same line after the method. Commit comments are palimp's main T1
  source. Can the project lead check on any real SRX (a single
  `show system commit` with one commented commit is enough)?
- Is text evidence (documentation prose, no sample) acceptable to CONFIRM a
  behavioral assumption (VSRX-3, VSRX-5, VSRX-6, VSRX-7c)? The table marks it
  as `text` so it can be downgraded.
- Should palimp accept syslog-server copies of RT_FLOW (collector prefix, no
  `<PRI>`)? Probably yes: inherited logs often come from a collector.
- Carried over: 100% recall on Easy says little (Medium or a stricter matcher
  next?); the 20 extra T3 items (decision 0011 amendment now says they are
  neutral unless misleading, but the harness does not classify them yet).

### Known issues

- Readers fail on several documented layouts (G1 to G10 in
  `docs/format-assumptions.md`); nothing was fixed in this session by design.
- Most documentation samples are old (12.x, 13.x) or state no release.
- The standard (unstructured) RT_FLOW syslog format is not parsed yet (G10).
- `palimp explain` without `--no-llm` prints a note and the same output (no
  LLM yet).
- This session read both `src/palimp/formats/` and the spec's format section
  (it is neither an analyzer nor a simulator session); the next analyzer
  session should not reuse its knowledge of the spec beyond
  `docs/format-assumptions.md`.
- Session 6 metrics row is provisional (measured before the final commit).
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

Session 6 has its own transcript `72beb9ef-54f4-42f0-8f55-6f97aafd613c`.
Finalize it at the start of session 7 with:

    uv run python metrics/session_tokens.py 72beb9ef-54f4-42f0-8f55-6f97aafd613c

Cost is API-equivalent (decision 0006), not a billed amount.
