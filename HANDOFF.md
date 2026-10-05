# Handoff

## Last session: 12 (2026-10-05), analyzer: verdicts, confidence, first real evaluation

### Note for simulator sessions

- No ground truth schema change. The new harness `eval/verdicts.py` reads
  `expected`, `status.live`, `intent.app_id`, `people`, `traps` and
  `created.event_id`; the slow test `tests/test_medium_verdicts.py` reads
  `status.live`. palimp itself never reads ground truth or manifest.
- Observation, not a request: `expected.verdict` is `removal_candidate` for
  many dead rules whose only not-live evidence is zero hits and no log lines
  (193 rules over seeds 0 to 19 have T2-only not-live evidence). Decision 0020
  makes palimp answer `verify` there on purpose.

### Done

- Session 11 metrics row finalized (67 calls, 4.54 USD API-equivalent).
- Decision 0020: absence of evidence is never evidence of absence.
  `removal_candidate` needs a positive not-live signal; zero hits and no log
  lines alone give `verify`. Refinements recorded in the same file.
- Evidence items carry `kind` and `apps` (applications they name). App
  vocabulary (`apps.py`) learned from the artifacts: ticket related CI,
  object name first segments (role words like `pc`, `users` skipped), ticket
  short names (`Decom ESHOP` + related CI `webshop` gives `eshop`).
- New evidence: T3 deactivated policy, T3 temporary label (temp, test,
  urgent, typos of temp), T1 decommission leftover (`notlive.py`): a commit
  comment or ticket retiring an app, linked to its commit (ticket ID in the
  comment, else close date), that deleted policies on the same objects, and
  every app the policy names is the retired one.
- Ingest records `removed_by_commit` (policies each commit deleted).
- `assess.py`: verdict rules V-CONTRADICTION, V-NOTLIVE, V-TEMPORARY-IN-USE,
  V-TRAFFIC-NOT-RECENT, V-TRAFFIC, V-NO-TRAFFIC-SEEN, V-NO-VISIBILITY;
  confidence rules C-T1-T3-CONFLICT, C-T1-T3-AGREE (HIGH, needs traffic
  seen), C-T1-T3-AGREE-NO-TRAFFIC, C-T1-ONLY, C-T3, C-WEAK. Conflict findings
  cite both evidence IDs. Question and who to ask on every non-keep verdict.
- `explain` shows the assessment; `explain --all` text collapses blind T2
  items into numbered global notes (the JSON keeps every item).
- `eval/verdicts.py`: verdict accuracy (expected and best achievable),
  dangerous errors listed, overconfidence, calibration, per trap (rule and
  instance), per format variant, naive baseline (zero hits gives removal).
- Medium dev seeds 0 to 19 (3099 rules), final:
  palimp 90.0% vs best achievable (naive 90.1%), 85.3% vs expected (naive
  90.2%), dangerous errors 0 (naive 44), overconfidence 0.0%, HIGH: intent
  app right 96.7%, verdict = best 97.0%. Before the new not-live evidence and
  refinements: 86.5% vs best, 0 dangerous, 2.4% overconfident.
- Conflicts flagged on all 44 TRAP-MISLEADING-COMMENT rules, 68 BATCH-COMMIT
  rules and 5 untrapped rules.
- Slow test: zero removal candidates on live rules, Medium seeds 0 to 9.

### Next

- 183 dead rules stay at `verify` (best achievable `removal_candidate`):
  mostly decommissions with no comment and no exported ticket. Candidate
  positive signals: the destination never seen in any log while logging
  rules to neighboring hosts are (decision 0020 lists it), decommission
  commit found without a marker (a commit that deletes most rules of one
  application).
- 126 not-live rules with hits get `keep` (best `verify`): hits since an
  unknown clear date on a retired app. Hit count clear detection (session 11
  next list) and the retired-app signal on rules with traffic would help.
- `ask` names the ground truth owner only 18.5% of the time: palimp names
  the ticket requester, or the latest requester for the app. Look at who the
  owner is in the artifacts.
- `report` and `questions` commands (the questions are now in the JSON).
- Held-out seeds were not run (by mission). Run them only after the next
  tuning round is frozen.

### Open questions

- Is 90.0% vs best achievable with 0 dangerous errors the right trade, given
  that the ground truth `expected.verdict` rewards removal on absence alone?
- Should deactivated rules always be removal candidates (all 238 match the
  ground truth today)? A deactivated rule kept as a fallback is a real case.
- HIGH now needs traffic seen. Should a T1 that names a ticket still open
  also allow HIGH?
- Carried over: blind T2 items per policy (decision 0019); per trap headline
  metric (per rule or per instance); Hard trap weights; Medium size; on_call
  persona; decision 0015; `commit activate`; CONFIRMED-TEXT; scenario names.

### Known issues

- App vocabulary misses names with no ticket and no object prefix
  (`vendor-arch-109` does not name `archive`: prefix matching was dropped
  because `web` named `webshop`).
- Five conflicts on untrapped rules (not inspected).
- Carried over: logged sessions undercount traffic; time of day in logged
  time zone; Junos predefined applications from general knowledge (VSRX-12);
  VSRX-2b; ticket assignee `svc-ansible`; S2 and S5; git identity in repo
  config only; session 2 Part C checks.

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
`8ed29a6f-73ed-4fd4-b799-5bcf0a8290c4`. Finalize it at the start of session
13 with:

    uv run python metrics/session_tokens.py 8ed29a6f-73ed-4fd4-b799-5bcf0a8290c4

Cost is API-equivalent (decision 0006), not a billed amount.
