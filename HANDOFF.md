# Handoff

## Last session: 14 (2026-10-05), analyzer: vocabulary abbreviations and application owners

### Note for analyzer sessions

- No ground truth schema change.
- New `palimp.owners` module, new T3 evidence kind `app_requesters`, new
  `Assessment` fields `owner` (stated only when certain) and
  `owner_candidates`. Every policy now has an `ask` line, `keep` included;
  `question` stays non-keep only. Decision 0022.
- `eval/verdicts.py` headline now also shows owner stated as certain (right,
  wrong), right owner among the candidates, and T1-T3 conflicts on untrapped
  and MISLEADING-COMMENT rules.

### Done

- Part A: session 13 metrics finalized (60 calls, 2.89 USD API-equivalent).
  First held-out run recorded in `docs/evaluation-history.md`. Commit
  `15c9086` tagged `v0.1.0-baseline` and pushed. CLAUDE.md: the held-out
  workflow is run only by the project lead, at most once per release, every
  run recorded in `docs/evaluation-history.md`.
- Part B, tuned on Medium dev seeds 0 to 19, checked on 20 to 99. Held-out
  never looked at.
  - Vocabulary: role words (`servers`, `srv`, `mgmt`...) never name an app;
    ticket aliases win over object segments; an object segment of 3+ letters
    that starts exactly one related CI is its abbreviation (`mon`).
  - Owners: candidates from referenced ticket requester, requesters of the
    application's tickets, `req XX` initials resolved to one requester.
    Admins (commit users, assignees) named apart, never owners. Certain only
    when all sources agree, one application, no conflict, and 2+ tickets by
    that person or two sources agree. Otherwise "Not sure who owns it" plus
    candidates.

| metric | 0-19 before | 0-19 after | 20-99 before | 20-99 after |
|---|---|---|---|---|
| verdict vs best achievable | 90.0% | 90.3% | 91.1% | 91.2% |
| dangerous errors | 0 | 0 | 0 | 0 |
| conflicts, untrapped rules | 5 of 1469 | 0 | 14 of 5690 | 0 |
| conflicts, MISLEADING-COMMENT | 44 of 44 | 44 of 44 | 167 of 170 | 167 of 170 |
| intent app right | 95.1% | 97.1% | 95.6% | 97.4% |
| owner named in `ask` | 18.5% | 85.9% | 18.3% | 88.9% |
| owner stated certain, right | 18.5% | 58.3% | 18.3% | 61.3% |
| owner stated certain, wrong | 14 | 0 | 48 | 0 |
| HIGH: intent app right | 96.7% | 97.1% | 97.9% | 98.2% |
| overconfidence | 0.0% | 0.0% | 0.0% | 0.0% |

"Before" for owners wrong: old code had no `owner` field, so any other person
or admin named in `ask` counts as stated wrong (eval docstring). The 20-99
baseline was rerun from a clean worktree of the pre-change commit.

### Next

- Project lead: held-out run for a release that includes session 14.
- Analyzer: owners of applications with no ticket (aggregating `req`
  initials across policies would add about 10 apps on 0 to 19); intent app
  for two-application flows (ground truth owner is the source side app).
- From session 12, unchanged: 183 dead rules at `verify` (best
  `removal_candidate`) on 0 to 19; not-live rules with hits at `keep`;
  `report` and `questions` commands; V-CONTRADICTION on 20 to 99.

### Open questions

- Should two-application flows name the source side app owner first? The
  ground truth owner is the source side app on dev seeds; not done, palimp
  lists both sides without ranking by direction.
- Real-world risk (decision 0022): a service desk filing every ticket of an
  application would be stated as its owner.
- Carried over from session 13: held-out level and count; 90% vs best trade;
  deactivated rules; HIGH with an open ticket; decision 0019 blind items;
  per trap metric; Hard trap weights; on_call persona; decision 0015;
  `commit activate`; CONFIRMED-TEXT; scenario names.

### Known issues

- 3 MISLEADING-COMMENT rules on 20 to 99 show no conflict (unchanged, not
  inspected).
- `vendor-arch-109` still does not name `archive` (segment `arch` is not a
  first segment).
- Carried over: held-out `scenario_id` can equal a dev id; logged sessions
  undercount traffic; time of day in logged time zone; Junos predefined
  applications from general knowledge (VSRX-12); VSRX-2b; `svc-ansible`; S2
  and S5; git identity in repo config only; session 2 Part C checks.

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
14). Session 14 has transcript `22237df9-50f6-42f3-9347-a937849aa44c`.
Finalize it at the start of session 15 with:

    uv run python metrics/session_tokens.py 22237df9-50f6-42f3-9347-a937849aa44c

Cost is API-equivalent (decision 0006), not a billed amount.
