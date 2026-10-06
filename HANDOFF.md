# Handoff

## Last session: 22 (2026-10-06), simulator: Hard level with four new traps (decision 0035)

### Note for analyzer sessions

- No ground truth schema change (decision 0017 does not apply). The schema
  already had everything Hard uses. New in practice, in Hard ground truth
  only: `status.still_needed` can be true while `status.live` is false;
  `name_history` can hold several names (the last one is the key);
  `hits_reason` takes `scanner`, `monitoring` and `ip_reuse`; global
  policies are keyed `from_zone` `global`, `to_zone` `global`.
- `palimp-sim generate --level hard --seed N` exists. Hard scenarios take
  about 9 s and 14 MB each. About half are hierarchical (file names stay
  `config.set` and `rollback-NN.set`, the active one starts with a
  `## Last commit:` header) and about 4 in 10 have global policies. Read
  only the ground truth schema and the artifacts, as before.
- Easy and Medium output is byte-identical to session 21 (golden hashes and
  seeds 0 to 9 of both levels compared): Medium dev scores and the second
  held-out run on Medium stay comparable.
- No Hard evaluation was run (simulator session). Before tuning anything on
  Hard, the project lead decides the Hard dev seed range and whether Hard
  joins the held-out run (decision 0021).

### Done

- Part A: session 21 metrics finalized (124 calls, 6.53 USD); local branch
  `backup-pre-rewrite-s21` deleted after checking its tree equals the
  rewritten session 20 commit and every subject is on main.
- Part B (decision 0035): `levels.HARD`, `hard.HardSimulation` (Medium
  hooks that draw nothing in Medium), the seven v1 traps with larger drawn
  counts and the four new traps, each drawn with zero possible, with ground
  truth tags, verdicts, `max_justified_confidence` from non-misleading
  evidence, misleading evidence marked, and a naive-reading test
  (`simulator/tests/test_hard.py`). Format variants drawn and recorded in
  `format_draw`: hierarchical config (`inactive:`, `/* */` annotations,
  shapes checked against the `hier_*.txt` fixtures) and global policies.
  Spec 5.1, 7.1 to 7.5, 11 (VSRX-13 to 15), 12 (S18 to S21) updated.
- Speed (shared code, bytes unchanged): configuration snapshots without
  deepcopy and integer address matching; Hard went from 21 s to about 8 s
  per scenario, Medium from 2.6 s to 1.8 s.
- Measured over Hard seeds 0 to 49: 415 policies on average (369 to 475),
  33.7% dead (28 to 41%), 8.5 s (max 10.7 s), 13.9 MB (max 17.3 MB);
  per-trap table in spec 7.5.

### Next

- Decision 0032 item 3 (analyzer): real public configs, local only, never
  committed. Check there: `inactive:`, annotations and descriptions on real
  security policies (HIER-1b to HIER-1d), global policies in hit counts and
  logs (GLOBAL-1), how `apply-groups` is used on policies (decision 0034).
- Analyzer: first Hard dev evaluation once the project lead sets the seed
  range; per-trap metrics for the four new traps.
- Project lead: try `palimp anonymize` on a real config before
  recommending it in the issue template; review the limits in decision
  0031 and the capture issue below.
- Carried over: remaining dead rules at verify (mostly no logging), owners
  of applications with no ticket.

### Open questions

- Hard in the held-out run: which level and how many scenarios (decision
  0021)? The salt rotation rule (spec 8.2) applies if Hard is added.
- Hard policy count is 415 on average, under the spec's approximate 450:
  acceptable, or raise access requests (needs a version bump, which moves
  the Easy and Medium hashes through the version string)?
- TRAP-SCANNER-HITS is also tagged on dead rules the scanner reaches by
  accident (86% of scenarios have one, for 80% drawn): keep tagging by
  condition, or only the drawn subjects?
- The Medium column "v2" values of spec 7.1 (IP reuse 0.1, 1 rename a
  year, cleanup errors 0.02, a contractor period) stay unapplied: applying
  them changes Medium output. Leave Medium as is until after the release?
- From the session 22 prompt challenges, still open on the analyzer side:
  other `then permit` options (`tunnel`, `firewall-authentication`,
  `destination-address`) read as permit or not; anonymize on terminal
  captures (prompts and banners treated as names).
- Should the issue template ask for `--strip-text` by default?
- Carried over: decision 0020 example without a migration (needs
  approval); 90% vs best trade; HIGH with an open ticket; decision 0019
  blind items; on_call persona; decision 0015; `commit activate`;
  CONFIRMED-TEXT; scenario names.

### Known issues

- Hard simulator assumptions, all unverified: a rename keeps the hit
  counter and old log lines keep the old name (VSRX-13); global policies in
  hit counts as `global global NAME`, logs with the real zones (VSRX-14);
  sessions to an address with no live host count hits and close with
  `idle Timeout`, nothing from the server (VSRX-15); descriptions quoted
  only when needed in hierarchical output (HIER-1d); no header on
  hierarchical rollbacks (HIER-1e).
- Grounding of the new traps is partial (spec 12.3): TRAP-SCANNER-HITS has
  a direct source (S18); TRAP-RENAME-CHAIN, TRAP-STALE-NAME and the
  "flow already open, no rule" step of TRAP-IP-REUSE do not.
- Contractor broad rules (spec 3) are not modeled, and CMDB export is not
  generated at any level (spec 7.1 says yes).

- Hierarchical: file names stay `config.set` and `rollback-NN.set` whatever
  the format. An `inactive:` leaf with a value is kept as `description x`
  in `deactivated_statements`, where set output may print only the keyword
  (no sample).
- Other `then permit <option>` forms (`tunnel ipsec-vpn X`,
  `firewall-authentication ...`, `destination-address drop-untranslated`)
  still leave the action unset, both formats (decision 0034, postponed: no
  fixture, outside the session 21 mission).
- Global policies: how hit counts and RT_FLOW name them is undocumented
  (GLOBAL-1). Hit count looked up under `global global NAME` (blind when
  absent); logs merged by policy name across zone pairs, except pairs where
  a zone policy has the same name.
- Anonymize (pre-existing, seen in session 21): in a saved terminal capture,
  prompt and banner words are treated as names (`[edit]` became `[srwb]`,
  `show` became `lufh` in `user@host# show security policies global`), so
  the anonymized capture loses its relative path and parses differently.
  Not fixed (outside the mission). Workaround: give anonymize a plain
  `show configuration` output without prompts.
- The anonymized `## Last commit:` header line is treated as free text
  (the time zone abbreviation is replaced, harmless).
- Anonymize limits (decision 0031): pseudonymization, not encryption;
  names palimp does not know stay in free text; non-ISO dates in free text
  are not shifted; a kept signal word that starts a longer name loses the
  shared prefix; people with a one-letter name word may get other initials.
- LLM writer limits frozen for v1 (decisions 0027 to 0029).
- The report prints the artifact path as given on the command line.
- 3 MISLEADING-COMMENT rules on 20 to 99 show no conflict (not inspected).
- `vendor-arch-109` still does not name `archive`.
- Carried over: held-out `scenario_id` can equal a dev id; logged sessions
  undercount traffic; time of day in logged time zone; Junos predefined
  applications from general knowledge (VSRX-12); VSRX-2b; `svc-ansible`; S2
  and S5; session 2 Part C checks.
- The test suite is slow on this machine: 16 min with `--runslow`
  (session 21 Part A), and one plain run took 37 min. Run targeted test
  files while developing, the full suite before pushing.

## Plan before release (decision 0032)

1. Hierarchical config format (session 20).
2. Hard level with 4 new traps: TRAP-RENAME-CHAIN, TRAP-IP-REUSE,
   TRAP-SCANNER-HITS, TRAP-STALE-NAME (session 22, decision 0035).
3. Robustness on real public configs: local only, never committed, never
   republished.
4. End-to-end test on a real vSRX postponed until after release (no
   budget). The README must state plainly that palimp has never been run on
   a real SRX history, only on synthetic scenarios with formats confirmed by
   Juniper documentation and practitioner captures.
5. Release preparation, then the second held-out run.

Release as a 0.x beta when these are done and no dangerous error appears
on held-out or on the real public configs.

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
has transcript `b14ba40d-eb4c-4ee4-bc69-02b4a94d38bb` (finalized in session
17). Session 17 has transcript `052aad46-2e12-4fa9-99c9-54d4730081ee` (finalized
in session 18). Session 18 has transcript
`fd2407ac-42b6-4684-a907-dbaff839c04d` (finalized in session 19). Session 19
has transcript `63a66e24-b7a2-43f0-9fe2-32d2c7b0b4af` (finalized in session 20).
Session 20 has transcript `1561b174-b703-4305-b4b4-d9a8a844a436` (finalized
in session 21). Session 21 has transcript
`1787e2cd-2949-4e20-ab01-cde64c249ddc` (finalized in session 22). Session 22
has transcript `3dbc7b1c-2c24-4e93-9d78-317745861978`. Finalize it at the
start of session 23 with:

    uv run python metrics/session_tokens.py 3dbc7b1c-2c24-4e93-9d78-317745861978

Cost is API-equivalent (decision 0006), not a billed amount.
