# Handoff

## Last session: 21 (2026-10-06), analyzer: push unblocked (noreply identity), parser gaps before release (decision 0034)

### Note for analyzer sessions

- No ground truth schema change.
- Git identity: repository config `n-le-bourdiec` /
  `240397139+n-le-bourdiec@users.noreply.github.com` (CLAUDE.md). The 11
  session 20 commits were rewritten to it (author and committer only,
  trees and messages unchanged) and pushed; CI green.
- Decision 0034:
  - a deactivated zone pair, `security policies global`, `security
    policies` or `security` deactivates every policy under it
    (`_Builder.deactivate_scope`, applied in `_Builder.config()` whatever
    the line order); these follow the existing deactivated path
    (V-NOTLIVE unless traffic is seen, cleanup list);
  - global policies: zones `global`/`global` (`models.GLOBAL`), key
    `global/NAME` (`PolicyKey` prints and parses it), `Policy.is_global`,
    `match_from_zones`, `match_to_zones`, `zones_text()`; the log lookup is
    `counters.log_summary` (moved from evidence) with
    `rt_flow.merge_summaries` for global policies;
  - `then permit application-services ...`: action permit,
    `Policy.application_services`, one T3 item kind `application_services`
    (no apps);
  - `apply-groups` stays warn-only until the real public configs test.
- Any new code that reads `policy.from_zone`/`to_zone` as real zones must
  handle `policy.is_global` (see `report._zones`).

### Done

- Part A: repo git identity set to the noreply address; 11 unpushed
  commits rewritten (filter-branch on `origin/main..HEAD` only; dates,
  messages, Co-Authored-By lines and trees identical); 650/650 tests with
  `--runslow`; pushed, CI green. `docs/assets` committed as is, excluded
  from ruff in `pyproject.toml`. Session 20 metrics finalized (11 commits,
  124 calls, 8.00 USD). CLAUDE.md records the noreply identity rule.
- Part B (decision 0034): deactivated scopes (both formats), global
  policies (both formats, through evidence, verdict, report, explain,
  anonymize), application-services permit as T3; 6 new documentation
  fixtures (Global Security Policies page, Application Firewall page),
  all parse with 0 unknown; GLOBAL-1, APPSVC-1, DEACT-1 in
  `docs/format-assumptions.md`; README inputs updated.
- Eval Medium seeds 20-99 before and after: 12553 rules, identical per-rule
  rows (verdict, rule, confidence and every other field); dangerous errors
  0 before and after (the simulator writes none of these constructs).

### Next

- Decision 0032 item 2 (simulator sessions): Hard level with
  TRAP-RENAME-CHAIN, TRAP-IP-REUSE, TRAP-SCANNER-HITS, TRAP-STALE-NAME.
- Decision 0032 item 3: real public configs, local only, never committed.
  Check there: `inactive:`, annotations and descriptions on real security
  policies (HIER-1b to HIER-1d), global policies in hit counts and logs
  (GLOBAL-1), how `apply-groups` is used on policies (decision 0034).
- Project lead: try `palimp anonymize` on a real config before
  recommending it in the issue template; review the limits in decision
  0031 and the capture issue below.
- Carried over: remaining dead rules at verify (mostly no logging), owners
  of applications with no ticket.

### Open questions

- Other `then permit` options (`tunnel`, `firewall-authentication`,
  `destination-address`): read them as permit too? The action shows as
  `-` today; no verdict depends on it.
- Should anonymize recognize prompts and banners in captures (known issue
  below)?
- Should the issue template ask for `--strip-text` by default?
- Carried over: decision 0020 example without a migration (needs
  approval); held-out level and count; 90% vs best trade; HIGH with an open
  ticket; decision 0019 blind items; per trap metric; Hard trap weights;
  on_call persona; decision 0015; `commit activate`; CONFIRMED-TEXT;
  scenario names.

### Known issues

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
   TRAP-SCANNER-HITS, TRAP-STALE-NAME (simulator sessions).
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
`1787e2cd-2949-4e20-ab01-cde64c249ddc`. Finalize it at the start of session 22
with:

    uv run python metrics/session_tokens.py 1787e2cd-2949-4e20-ab01-cde64c249ddc

Cost is API-equivalent (decision 0006), not a billed amount.
