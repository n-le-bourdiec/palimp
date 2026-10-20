# Handoff

## Last session: 30 (2026-10-20), simulator: realistic names, naming source confidence, firewall team rules (decision 0045)

### Note to analyzer sessions (schema change, decisions 0017 and 0045)

The ground truth JSON Schema changed (additive, `schema_version` stays 1):

- intent kinds `block` (specific deny or reject), `cleanup_deny` (catch-all
  deny), `broad_permit` (any/any/any permit), `factory_default`;
- event kind `security_rule`; hits reason `blocked`;
- these rules have `intent.app_id` `firewall` (a pseudo application listed
  in `apps` when used) and `owner_to_ask` `firewall_team` (not a person id).

Expected values of the new kinds: active deny and catch-all deny keep/keep
MEDIUM; deactivated deny removal_candidate (both); broad permit best verify,
LOW; factory default best verify, MEDIUM (spec 4.11). From simulator 0.4.0,
Medium and Hard `max_justified_confidence` comes from naming sources (spec
6.1), not tiers. Medium and Hard numbers before and after 0.4.0 are not
comparable (`docs/evaluation-history.md`). Easy artifacts are unchanged.

### Done

- Session 29 metrics finalized (154 calls, 10.97 USD).
- Realistic names in Medium and Hard (spec 2.5, `naming.py`): site codes,
  server roles, people's workstations, generic objects, application names
  on 25% to 60% of the applications; policy names and descriptions in new
  styles (tickets, zone-to-zone, object-based, free text).
- Naming source confidence model (spec 6.1, `sources.py`).
- Firewall team rules (spec 4.11, `rulekinds.py`): deny and reject (some
  deactivated), catch-all deny, broad permit, factory default.
- Simulator 0.4.0, goldens and stored Hard trap counts regenerated,
  decision 0045, format assumptions DENY-1 and HITCOUNT-ACTION-1.
- Distributions before and after (spec 7.6): application rules with no
  naming source 7.7% to 33.4% (Medium), 4.6% to 36.9% (Hard);
  `max_justified_confidence` LOW 0.8% to 68.7% (Medium), 1.7% to 75.9%
  (Hard); 337 Medium and 279 Hard firewall team rules.

### Next

- Analyzer session: measure palimp on simulator 0.4.0 dev seeds (Medium
  20-99, Hard 20-49), new enum values and `firewall_team` in the
  evaluation.
- Project lead review of `../palimp-realconfigs/review-4.md` (carried).
- Held-out workflow: add the Hard table (decision 0036) before the second
  held-out run; consider rotating the salt (spec 8.2, simulator version
  changed difficulty).
- Release preparation (decision 0032 item 5).

### Open questions

- Firewall team rules are all owned by `firewall_team`, including denies
  that name an application object (none generated yet): right owner?
- Catch-all deny MEDIUM, broad permit LOW, factory default MEDIUM in the
  ground truth: confirm the ceilings.
- The confidence model counts a commit comment and a ticket as sources that
  are not names (they can back a two-letter name); decision 0044 lists only
  a port, an application name, a dynamic application or a description.
- Deactivated deny: removal_candidate (usual deactivated rule) in the
  ground truth; decision 0044 says a deactivated deny follows the usual
  rules.
- Carried over from session 29: deny rules routed to owners or the
  firewall team; `ad` as a conditional role; `default-permit` with no
  Juniper sample; an object literally named `ANY`.
- Carried over: decision 0039 items 2 and 4; decision 0036 point 3;
  anonymize prompt login and host; `--strip-text`; decision 0020 example;
  90% vs best trade; HIGH with an open ticket; decision 0019 blind items;
  on_call persona; decision 0015; `commit activate`; CONFIRMED-TEXT;
  scenario names.

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
`5fd285ac-95ef-4a18-a704-c9c5c246fd1b`. Finalize it at the start of session
31 with:

    uv run python metrics/session_tokens.py 5fd285ac-95ef-4a18-a704-c9c5c246fd1b

Cost is API-equivalent (decision 0006), not a billed amount.
