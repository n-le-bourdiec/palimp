# Handoff

## Last session: 31 (2026-10-20), analyzer: CI green on simulator 0.4.0, review-4 fixes, shadowed rules (decision 0046)

### Done

- Session 30 metrics finalized (134 calls, 15.37 USD).
- Process rule in `CLAUDE.md`: main stays green; a simulator change that
  breaks analyzer tests goes on a branch, merged after the analyzer session
  makes it green.
- CI green again (run 39438709395 on `487de86`). The 6 anonymize failures
  were privacy bugs, fixed in anonymize (tests not weakened): a kept word
  that starts a longer known name (`web`, `webshop`) now stays at the start
  of its replacement, so the copy keeps the abbreviation palimp reads;
  replacement initials equal to an original name (`req GJ` to `req CI`)
  redraw the mapping. New test with invented realistic names. The 3 report
  failures were an outdated expectation (firewall team findings since
  session 29, first generated in Medium by simulator 0.4.0).
- Baseline on simulator 0.4.0 (`docs/evaluation-history.md`): 0 dangerous
  errors; eval script now reports underconfidence and per intent kind.
- Part B: commit comments and tickets confirm two-letter names; review-4
  fixes (ticket-only descriptions, factory default sources, broad permits
  say what they permit and inbound ones open the team list, hosting
  platforms are locations, `MS-SQL-PORT-GROUP` names mssql, an object named
  `ANY` read by contents, deny questions to the firewall team); shadowed
  rules (`V-SHADOWED`, at most verify); deny tuning on seeds 0-19
  (`V-DENY-QUIET` keep, `C-BLOCK` MEDIUM).
- Medium 20-99 and Hard 20-49 after: block vs best 100% (was 80.9% and
  64.4%), 0 dangerous, verdict moves only verify to keep on quiet denies (27
  and 31). Real configs: 0 verdict moves rule by rule, 1 shadowed rule found
  (`docs/real-configs-robustness.md`).

### Next

- Project lead: review decision 0046 (in particular items 5 `ANY` and 7).
- Held-out workflow: add the Hard table (decision 0036) before the second
  held-out run; consider rotating the salt (simulator version changed).
- Release preparation (decision 0032 item 5).
- Simulator backlog: shadowed rules (a rule after a catch-all deny) are
  never generated, so `V-SHADOWED` is tested only on unit fixtures and one
  real configuration.

### Open questions

- Shadowed rules: removal_candidate needs approval (not before release).
  Today a shadowed keep becomes verify; a shadowed rule with hits stays
  verify with the contradiction stated.
- An object named `ANY` that is not 0.0.0.0/0 no longer makes a rule a
  catch-all deny or broad permit: its verdict follows the usual rules,
  removal_candidate included on a positive not-live signal (asked in the
  session 31 prompt; no real configuration verdict moved).
- `V-DENY-QUIET` keeps a deny with no traffic seen; a deny with no
  visibility at all stays verify (firewall team). Should it be keep too?
- Carried from session 30: owner of deny rules naming an application
  object; ceilings of catch-all deny, broad permit and factory default;
  deactivated deny as removal_candidate.
- Carried over: `ad` as a conditional role; decision 0039 items 2 and 4;
  decision 0036 point 3; anonymize prompt login and host; `--strip-text`;
  decision 0020 example; 90% vs best trade; HIGH with an open ticket;
  decision 0019 blind items; on_call persona; decision 0015; `commit
  activate`; CONFIRMED-TEXT; scenario names.

### Known issues

- Underconfidence measured before simulator 0.4.0 (57%, 68% in session 28)
  came from tier-based ceilings; 0.4.0 replaces them (decision 0045).
- Simulator 0.4.0: deny rules never log (no `RT_FLOW_SESSION_DENY` sample);
  no custom application or dynamic application names are generated; the
  extra commits of the firewall team rules shift the retained window, so
  TRAP-MISLEADING-COMMENT lands on other rules than in 0.3.0 (mechanics
  unchanged).
- Known limit (decision 0044 item 6): a two-letter name is never read in
  not-live signals, so 2 Medium V-CONTRADICTION rules whose decommission
  names `ci` stay at keep (session 28).
- Part B items 10, 12 and 13 landed in one commit (`da54749`): they share
  `palimp.semantics` and the factory default is a broad permit.
- Commit `74e382a` says it restores the 5 Hard rules; it restored 4, the
  fifth came with `d8ffe8d`.
- Person names stay possible applications at LOW (no name list, decision
  0042).
- `junos-ntp`, `junos-ldap`, `junos-ms-sql`, `junos-smb` and a few other
  predefined names still have no published definition (VSRX-12d).
- Real configs, still unsupported: tenant and logical system policies
  (stated, not read); `delete:` load tags; `//` comments; operational
  command output inside a capture; a command echoed without a prompt; a set
  file with a hierarchical part (not observed); `match url-category`.

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
- Other `then permit` children (`destination-nat`, `source-nat`,
  `services-offload`) still leave the action unset (decision 0037: no
  sample, not asked). `destination-address` has a syntax reference only
  (PERMIT-OPT-3), no configuration sample.
- Global policies: how hit counts and RT_FLOW name them is undocumented
  (GLOBAL-1). Hit count looked up under `global global NAME` (blind when
  absent); logs merged by policy name across zone pairs, except pairs where
  a zone policy has the same name.
- Anonymize: a `host/prefix` address keeps its own mapping (the same as the
  address written alone), except the one host per subnet whose mapping has
  zero host bits: it takes the mapped network's host bits instead, so it
  no longer matches its bare log address (session 24).
- Probe detection (decision 0039): a source reaching 3 policies and 3
  destinations with unanswered sessions; tuned on synthetic logs, where an
  unanswered session to a dead host closes with `idle Timeout` (VSRX-15,
  unverified). Rename detection needs a unique match within one commit.
- Working-tree files sometimes appear with CRLF line endings on this
  machine (index is LF); Python rewrites keep them. Normalize with
  `sed -i 's/
$//'` before scripted edits (session 24).
- The anonymized `## Last commit:` header line is treated as free text
  (the time zone abbreviation is replaced, harmless).
- Anonymize limits (decision 0031): pseudonymization, not encryption;
  names palimp does not know stay in free text; non-ISO dates in free text
  are not shifted; a kept signal word that starts a longer known name now
  keeps its place at the start of the replacement (session 31, decision
  0046); people with a one-letter name word may get other initials.
- LLM writer limits frozen for v1 (decisions 0027 to 0029).
- The report prints the artifact path as given on the command line.
- 3 MISLEADING-COMMENT rules on 20 to 99 show no conflict (not inspected).
- `vendor-arch-109` still does not name `archive`.
- Carried over: held-out `scenario_id` can equal a dev id; logged sessions
  undercount traffic; time of day in logged time zone; Junos predefined
  applications from general knowledge (VSRX-12); VSRX-2b; `svc-ansible`; S2
  and S5; session 2 Part C checks.
- Test suite runs in parallel (`-n auto`, pytest-xdist): 8 min with
  `--runslow` on this machine before session 25 (19 min serial). The Hard
  distribution test no longer bounds it (session 25).
- Stored Hard trap counts (`simulator/tests/data/hard_trap_counts.json`)
  must be regenerated when a simulator change moves Hard trap tags; the
  fixture seed tests catch a mismatch on 5 seeds in every run.

## Plan before release (decision 0032)

1. Hierarchical config format (session 20).
2. Hard level with 4 new traps: TRAP-RENAME-CHAIN, TRAP-IP-REUSE,
   TRAP-SCANNER-HITS, TRAP-STALE-NAME (session 22, decision 0035).
3. Robustness on real public configs: local only, never committed, never
   republished. Done in session 26 (`docs/real-configs-robustness.md`).
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

- Deny rules naming an application object, deny rules with logging
  (needs a `RT_FLOW_SESSION_DENY` sample), custom application names and
  dynamic applications as naming sources (decision 0045).
- Shadowed rules: a rule placed after a catch-all deny of its zone pair
  (decision 0046 item 6); address objects named like the `any` keyword
  (`ANY`) with narrower contents (decision 0046 item 5).
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
has transcript `3dbc7b1c-2c24-4e93-9d78-317745861978` (finalized in session
23). Session 23 has transcript `9941fbb6-f557-4a77-95a2-c41b0b29505e` (finalized in
session 24). Session 24 has transcript
`6ede7008-8cee-4e93-a9f2-2a82c52771a8` (finalized in session 25). Session 25
has transcript `1fc8d6dd-973f-4e31-90a8-b193e45219b2` (finalized in session
26). Session 26 has transcript `1c765544-e3ec-47e1-8473-5ee1cc86ff24`
(finalized in session 27). Session 27 has transcript
`4fa256b5-0487-44e9-a639-0af270d28f5c` (finalized in session 28). Session 28
has transcript `7aff9bc7-fe4f-4fd9-bae1-a4831d16e63e` (finalized in session
29). Session 29 has transcript `2b84db4c-8e39-40ea-a296-b7749a1c6593`
(finalized in session 30). Session 30 has transcript
`5fd285ac-95ef-4a18-a704-c9c5c246fd1b` (finalized in session 31). Session 31
has transcript `82425030-2c0d-4a09-a086-7597631acbb2`. Finalize it at the
start of session 32 with:

    uv run python metrics/session_tokens.py 82425030-2c0d-4a09-a086-7597631acbb2

Cost is API-equivalent (decision 0006), not a billed amount.
