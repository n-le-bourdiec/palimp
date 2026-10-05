# Handoff

## Last session: 15 (2026-10-05), analyzer: history lineage and counter evidence

### Note for analyzer sessions

- No ground truth schema change.
- New modules `palimp.lineage` (takeover, migration leftover) and
  `palimp.counters` (inferred counter clears). New evidence kinds: T3
  `takeover`, T3 `migration_leftover` (positive not-live, in
  `NOT_LIVE_KINDS`), T2 `counter_clear` (blind), T2 `log_stopped` (absent).
  New verdict rules `V-TAKEOVER-IN-USE` and `V-TRAFFIC-STOPPED` (both verify).
  Decision 0024.
- `Dataset` keeps `added_by_commit`, `deactivated_by_commit`,
  `past_addresses`; `RemovedPolicy` renamed `PastPolicy` (full match);
  `LogWindow.addresses` lists every logged address.
- Decision 0023: owners of a two-application flow are listed in alphabetical
  order, unranked. Never rank from patterns seen only in simulator data.

### Done

- Part A: session 14 metrics finalized (66 calls, 3.65 USD). Decision 0023,
  service desk scenario added to the simulator backlog below.
- Part B, tuned on Medium dev seeds 0 to 19, checked on 20 to 99. Held-out
  never looked at. The 20 to 99 baseline was rerun from a clean worktree of
  `54dceb3` (the first run crashed on seed 62 because code changed mid-run).

| metric | 0-19 before | 0-19 after | 20-99 before | 20-99 after |
|---|---|---|---|---|
| verdict vs best achievable | 90.3% | 91.4% | 91.2% | 92.0% |
| dangerous errors | 0 | 0 | 0 | 0 |
| dead rules left at verify | 182 | 171 | 693 | 652 |
| not-live rules left at keep | 117 | 94 | 400 | 342 |
| EMERGENCY-LOADBEARING = best | 35/35 | 35/35 | 112/112 | 112/112 |
| DEACTIVATED = best | 238/238 | 238/238 | 1060/1060 | 1060/1060 |
| HISTORY-HORIZON = best | 1104/1279 | 1111/1279 | 5015/5602 | 5040/5602 |

Every verdict that changed on 20 to 99 is on a not-live rule: 41 migration
leftovers to removal_candidate, 71 old hits plus leftover to V-CONTRADICTION
(verify either way), 58 stopped flows keep to verify. Takeover found on 16
of 35 EMERGENCY-LOADBEARING rules on 0 to 19 (the others' covered rules were
removed before the retained history). No counter clear inside the log window
on dev seeds 0 to 19: unit tests only.

### Next

- Project lead: held-out run for a release that includes sessions 14 and 15.
- Analyzer: remaining dead rules at verify are mostly policies without
  logging (89 of 171 on 0 to 19) or whose app vanished before the retained
  history; not-live rules at keep are mostly no-logging policies with hits.
- Owners of applications with no ticket (aggregating `req` initials).
- From session 12: `report` and `questions` commands.

### Open questions

- Decision 0020 example "destination never seen in any log while other
  logging rules to neighboring hosts are seen", without a migration: not done.
- Carried over: held-out level and count; 90% vs best trade; HIGH with an
  open ticket; decision 0019 blind items; per trap metric; Hard trap weights;
  on_call persona; decision 0015; `commit activate`; CONFIRMED-TEXT;
  scenario names.

### Known issues

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
`f3652112-9922-44ff-96a9-e1ce452c6128`. Finalize it at the start of session 16
with:

    uv run python metrics/session_tokens.py f3652112-9922-44ff-96a9-e1ce452c6128

Cost is API-equivalent (decision 0006), not a billed amount.
