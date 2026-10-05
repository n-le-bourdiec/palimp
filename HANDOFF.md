# Handoff

## Last session: 16 (2026-10-05), analyzer: report and questions commands

### Note for analyzer sessions

- No ground truth schema change.
- CLAUDE.md working rule 2 (new): initiative outside the mission only in the
  safe direction (toward keep or verify), flagged in the report; anything
  toward removal_candidate needs the project lead's approval first.
- Decision 0024 amended: `V-TRAFFIC-STOPPED` is an approved extension; an old
  destination silent in every log is a removal signal only together with an
  observed migration (TRAP-RARE-JOB). The decision 0020 example "destination
  never seen in any log" alone stays not implemented and would need approval.
- Decision 0025: report citations `[E3]` in a rule section, `[R12.E3]`
  elsewhere, `[G1]` for facts about the whole artifact set; rules numbered
  R1.. in configuration order; yes/no questions where yes = still needed.
- New modules `palimp.report` (model, Markdown, JSON) and
  `palimp.questions` (questionnaires, `answers.csv`). New commands
  `palimp report -a DIR -o OUT` and `palimp questions -a DIR -o OUT` (OUT is a
  directory). `report.build` raises on a removal_candidate without a
  not-live item.

### Done

- Part A: session 15 metrics finalized (81 calls, 5.14 USD). CLAUDE.md rule,
  decision 0024 amendment (challenge recorded).
- Part B: `report` and `questions`, tests (`tests/test_report.py`: Easy
  scenario fast, Medium dev seeds 0 to 4 slow): every cited ID resolves,
  every rule exactly once, no removal_candidate without a cited not-live
  item, every non-keep rule asked exactly once.
- Readability check on Medium seed 0: 170 policies, 20 removal_candidate,
  7 verify, 143 keep (47 of them on counters only), 18 questionnaires for 27
  rules. No verdict changed (the report only reads the findings).

### Next

- Project lead: read a generated report and questionnaire (session report
  has excerpts); held-out run for a release including sessions 14 to 16.
- LLM prose for `explain` and the report (cited sentences, validation pass).
- Questionnaires: many candidate groups with a single name ("not sure",
  one candidate); maybe merge per person with a clear "you may not be the
  owner" section (decision 0025 rejected merging for now).
- Carried over: remaining dead rules at verify (mostly no logging), owners
  of applications with no ticket.

### Open questions

- Should keep rules with LOW confidence or counters-only traffic also get a
  question (today only verify and removal_candidate are asked)?
- Carried over: decision 0020 example without a migration (now needs
  approval, see above); held-out level and count; 90% vs best trade; HIGH
  with an open ticket; decision 0019 blind items; per trap metric; Hard trap
  weights; on_call persona; decision 0015; `commit activate`;
  CONFIRMED-TEXT; scenario names.

### Known issues

- The report prints the artifact path as given on the command line.
- 3 MISLEADING-COMMENT rules on 20 to 99 show no conflict (not inspected).
- `vendor-arch-109` still does not name `archive`.
- Carried over: held-out `scenario_id` can equal a dev id; logged sessions
  undercount traffic; time of day in logged time zone; Junos predefined
  applications from general knowledge (VSRX-12); VSRX-2b; `svc-ansible`; S2
  and S5; git identity in repo config only; session 2 Part C checks.

## Simulator backlog (v2)

For simulator sessions. Analyzer sessions add items here, they never read
simulator code.

- Service desk tickets: a service desk files tickets on behalf of
  application owners (requester = service desk agent, owner named elsewhere
  or not at all), to test that palimp does not take the requester as the
  owner (decisions 0022 and 0023).

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
session 10). Session 10 has transcript `3649919e-84f0-4cd3-8b8d-c49cc31eff22` (finalized
in session 11). Session 11 has transcript `0d141375-db8e-4e9e-8979-0100e197eb49`
(finalized in session 12). Session 12 has transcript
`8ed29a6f-73ed-4fd4-b799-5bcf0a8290c4` (finalized in session 13). Session 13
has transcript `427d7108-6479-4578-a3a6-f699f1889575` (finalized in session
14). Session 14 has transcript `22237df9-50f6-42f3-9347-a937849aa44c` (finalized
in session 15). Session 15 has transcript
`f3652112-9922-44ff-96a9-e1ce452c6128` (finalized in session 16). Session 16
has transcript `b14ba40d-eb4c-4ee4-bc69-02b4a94d38bb`. Finalize it at the
start of session 17 with:

    uv run python metrics/session_tokens.py b14ba40d-eb4c-4ee4-bc69-02b4a94d38bb

Cost is API-equivalent (decision 0006), not a billed amount.
