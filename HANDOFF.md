# Handoff

## Last session: 11 (2026-10-05), analyzer: Medium ingest, T2 and T4 evidence

### Note for simulator sessions

- No ground truth schema change. The analyzer now reads every T2 and T4
  item; the eval harness reads `manifest.json` (`format_draw`) only to break
  results down per format variant. palimp itself never reads the manifest.

### Done

- Session 10 metrics row finalized (57 calls, 3.72 USD API-equivalent);
  session 10 commits pushed, CI green.
- CLAUDE.md: every session pushes its commits and reports the CI status of
  the last push in the session report.
- Ingest on Medium seeds 0 to 9: zero unknown lines in every artifact, before
  and after (config, commits, hit counts, logs, tickets, 49 rollbacks each).
  Checked beyond unknown counts: every log event has a timestamp, every hit
  count row names a configured policy. Locked in by `tests/test_medium_ingest.py`
  (slow, CI). Seeds 0 to 9 contain no standard (unstructured) RT_FLOW lines.
- Log year: an undated syslog timestamp takes its year from an ISO server
  stamp on the same line, from `--log-year` (year of the first undated line,
  on `ingest` and `explain`), or is inferred from the newest commit (then
  ticket dates); December to January rollover handled; inferred year printed
  as a warning. Unit tests in `tests/test_log_year.py`.
- Log reader keeps per policy (keyed FROM/TO/NAME): sessions, first and last
  seen, sources, destinations, ports, services, sessions per hour and weekday,
  active days. Log window start and end in `Dataset.log_window`.
- T2 collectors (`evidence.py`, `behavior.py`): hit count row (any layout,
  any row order), log summary with time-of-day pattern (nightly, business
  hours, daytime, around the clock) and recurrence hint (daily, weekly,
  monthly, quarterly, single day, irregular; late start or early stop in the
  window called out). Decision 0019: each T2 item has `signal` present,
  absent or blind; no logging, deactivated and missing artifacts are blind.
- T4 collector (`services.py`): one item per policy naming each application's
  service (Junos predefined, well-known port, application sets expanded,
  `any` stated as nothing to infer).
- Eval (`eval/evidence_recall.py`) now scores T1 to T4, per trap (per rule
  and per instance), per format variant, T2 direction, and "absent" signals
  on live rules. `eval/trap_rules.py` lists rules of a trap (harness only).
- Medium seeds 0 to 9 (1542 rules): T1 99.9%, T2 100.0% (direction agrees
  100.0%), T3 84.2%, T4 100.0%. No format variant below 81.9% on any tier.
  Per trap instance mean recall: BATCH 100%, LIVE-NOLOG 100%, MISLEADING
  100%, RARE-JOB 100%, HISTORY-HORIZON 88.5%, EMERGENCY 59.3%, DEACTIVATED
  53.2% (the gaps are all T3).

### Next

- Confidence scoring and verdicts (not started, by mission). Inputs to use:
  blind T2 items never count as support; 32 "absent" T2 items fall on live
  rules in seeds 0 to 9 (22 zero hit counts, 10 empty logs, all on
  RARE-JOB, LIVE-NOLOG or HISTORY-HORIZON rules): absent alone must never
  give "removal candidate".
- Hit count clear detection: zero hits on a policy whose logs show sessions
  in the window means the counters were cleared; zero hits on every rule of a
  zone pair is the same hint. Not implemented.
- T3 recall gaps: DEACTIVATED (33.6% T3 per rule) and EMERGENCY-LOADBEARING
  (22.1%), mostly config.set and rollbacks items. Look at what the ground
  truth expects there.
- The recurrence hint is tested on synthetic days only: Medium log windows
  are 60 days, so weekly, monthly and quarterly patterns never show in them.
- `report` and `questions` commands.

### Open questions

- Should a blind T2 item be emitted for every policy without logging (988
  blind items over seeds 0 to 9), or only in `explain` text? Kept in the
  evidence list so the LLM writer can cite the gap (decision 0019).
- Per trap metrics counted per rule are dominated by large instances
  (HISTORY-HORIZON 616 rules, BATCH 125): per instance figures are printed
  next to them. Which one should be the headline metric?
- Carried over from session 10: Hard trap weights; Medium size (8 MB per
  scenario); TRAP-HISTORY-HORIZON tagging; on_call persona; decision 0015;
  `commit activate`; CONFIRMED-TEXT; scenario directory names.

### Known issues

- Session counts are those logged: the simulator samples about one log line
  per policy and day, so "sessions" undercount real traffic.
- Time of day uses the logged time (UTC in Medium); a device in another time
  zone would shift "nightly".
- Junos predefined applications beyond the five documented ones in
  `junos_defaults_applications_13.2.txt` are from general knowledge (VSRX-12).
- Carried over: VSRX-2b unverified; ticket assignee `svc-ansible`; S2 and S5;
  git identity in repository config only; session 2 Part C checks not done.

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
in session 11). Session 11 has transcript
`0d141375-db8e-4e9e-8979-0100e197eb49`. Finalize it at the start of session
12 with:

    uv run python metrics/session_tokens.py 0d141375-db8e-4e9e-8979-0100e197eb49

Cost is API-equivalent (decision 0006), not a billed amount.
