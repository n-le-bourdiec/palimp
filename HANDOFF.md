# Handoff

## Last session: 13 (2026-10-05), evaluation infrastructure: unseen dev check and held-out workflow

No change under `src/palimp` (by mission).

### Note for analyzer sessions

- No ground truth schema change. Held-out ground truth uses the same schema;
  its `scenario_id` is `<level>-<index>` and can equal a dev id. Only the
  manifest tells them apart (`split: held-out`, `holdout_index`, no `seed`).
  Decision 0021.
- `eval/evidence_recall.run_seed` takes `holdout=False`; `eval/verdicts.py`
  has `--holdout N` (workflow only, needs `HOLDOUT_SALT`, aggregate output).

### Note for simulator sessions

- `palimp-sim generate --holdout INDEX` (decision 0021, spec section 8.2
  updated): needs `HOLDOUT_SALT`, else exit code 2 with a clear message. Seed
  = `2**63` + first 8 bytes of `SHA-256("<salt>:<level>:<index>")`; `generate`
  now rejects dev seeds outside `[0, 2**63)`. `ground_truth()` takes an
  optional `scenario_id`. Dev output unchanged (golden hashes pass), version
  stays 0.3.0. Tests in `simulator/tests/test_holdout.py`.

### How the project lead runs the held-out evaluation

1. Once: GitHub repository, Settings, Secrets and variables, Actions, New
   repository secret, name `HOLDOUT_SALT`, any long random value. Never put it
   on the development machine (decision 0007). Rotate it when a simulator
   change affects difficulty.
2. Each run: Actions tab, workflow "Held-out evaluation", "Run workflow"
   button, branch `main`, "Run workflow".
3. Read the result in the run page summary ("Held-out run record": date,
   palimp commit, palimp and simulator versions, who started it, then the
   headline, per trap, per format variant and calibration tables). The log
   shows the same tables and nothing per rule. Every run stays in the Actions
   history.
4. Paste only the aggregate tables into a session prompt if you want an
   agent to see them, and never ask it to tune on them.

The workflow (`.github/workflows/holdout.yml`) generates 50 Medium held-out
scenarios under `$RUNNER_TEMP/holdout`, runs palimp and the verdict eval,
uploads nothing and deletes the scenarios at the end, even on failure. A
failure prints only `held-out scenario N failed (details hidden)`. It was not
triggered in session 13 and has never run. It was dry-run locally with a test
salt (not the secret) on 1 and 2 scenarios.

### Done

- Session 12 metrics row finalized (85 calls, 6.18 USD API-equivalent).
- Part A, five conflicts on untrapped rules (seeds 5, 10, 11, 15, 19), report
  only: all five are false conflicts, the same rule each time,
  `monitoring-to-servers` (`mon-01` to `servers-net`, udp/161, ground truth
  app `shared-monitoring`, no trap). The description and the ticket (related
  CI `shared-monitoring`) name `monitoring`; the address objects give `mon`
  (an abbreviation) and `servers` (a role word for "all servers", not an
  app). Nothing in the artifacts contradicts. Effect: confidence lowered
  (MEDIUM or LOW instead of a possible HIGH), intent app counted wrong
  (`mon`). Verdict `keep` is right in all five. Seeds 20 to 99 show 13 more
  on the same rule, plus 1 on `rule-54` (not inspected).
- Overfitting check, current code unchanged, no tuning. Seeds 0 to 19
  reproduce session 12 exactly. Seeds 20 to 99 (12553 rules), never looked at
  before: verdict vs best 91.1% (dev 90.0%), vs expected 86.8% (85.3%),
  dangerous errors 0 (0; naive 160), overconfidence 0.0%, HIGH intent app
  right 97.9% (96.7%), HIGH verdict = best 97.5% (97.0%). Full tables in the
  session 13 report. No drop: no sign of overfitting to seeds 0 to 19. Note:
  seeds 20 to 99 are still dev seeds of the same generator, not held-out.
- Held-out generation in the simulator CLI, eval `--holdout` mode, workflow,
  decision 0021.

### Next

- Project lead: create the `HOLDOUT_SALT` secret and trigger the first
  held-out run (baseline before the next tuning round).
- Analyzer, from session 12 (unchanged): 183 dead rules at `verify` (best
  `removal_candidate`) on 0 to 19 (697 on 20 to 99); 126 not-live rules with
  hits at `keep` (409); `ask` names the owner 18.5% (18.3%); `report` and
  `questions` commands.
- Analyzer: the `mon` and `servers` vocabulary gap above (abbreviation of a
  known app, role word `servers`).
- 20 to 99: one `verify` rule got `removal_candidate` (best `verify`, not
  live per the dangerous count) and V-CONTRADICTION fires 94 times (12 on
  0 to 19). Not inspected.

### Open questions

- Should held-out runs also cover Easy, or other scenario counts? The
  workflow has `LEVEL` and `SCENARIOS` at the top; inputs were left out so
  every run is comparable.
- From session 12: is 90% vs best with 0 dangerous errors the right trade;
  deactivated rules always removal candidates; HIGH with an open ticket.
- Carried over: blind T2 items per policy (decision 0019); per trap headline
  metric (per rule or per instance); Hard trap weights; Medium size; on_call
  persona; decision 0015; `commit activate`; CONFIRMED-TEXT; scenario names.

### Known issues

- Held-out `scenario_id` can equal a dev id (decision 0021); tools must read
  the manifest `split`.
- Session 13 read `docs/simulator-spec.md` and simulator code (needed to build
  held-out generation) and also ran palimp on dev scenarios. It changed no
  analyzer code, so the independence rule was not used to tune anything.
- App vocabulary misses names with no ticket and no object prefix
  (`vendor-arch-109` does not name `archive`; `mon-01` does not name
  `monitoring`).
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
`8ed29a6f-73ed-4fd4-b799-5bcf0a8290c4` (finalized in session 13). Session 13
has transcript `427d7108-6479-4578-a3a6-f699f1889575`. Finalize it at the start
of session 14 with:

    uv run python metrics/session_tokens.py 427d7108-6479-4578-a3a6-f699f1889575

Cost is API-equivalent (decision 0006), not a billed amount.
