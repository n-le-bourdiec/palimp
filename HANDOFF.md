# Handoff

## Last session: 24 (2026-10-13), analyzer: decision 0038, anonymize host bits, Hard quality (decision 0039)

### Done

- Part A: session 23 metrics finalized (110 calls, 6.15 USD). Decision
  0038: a dangerous error is `removal_candidate` on a rule that is live
  **or** still needed; `eval/verdicts.py` prints both counts. Baseline with
  the new definition: Hard 0-19, Hard 20-49 and Medium 20-99 all 0 (old
  and new); the rules where the definitions differ are the TRAP-IP-REUSE
  rules (72 on 0-19, 65 on 20-49), all `keep` at baseline, none
  `removal_candidate`. Held-out run 1 noted as scored with the old
  definition. Anonymize keeps the host bits of `host/prefix` addresses
  (distinct hosts stay distinct; test on the documentation fixture).
- Part B (decision 0039), tuned on Hard 0-19, checked on 20-49, Medium
  20-99 checked after each item (no change on Medium):
  1. Regional instances (`payroll-pl`, `hr-de`) read exactly; a bare name
     with instances is ambiguous, candidates listed, MEDIUM at most. HIGH
     intent right 57% -> 94.3% (0-19), 95.5% (20-49).
  2. Renamed policies: history joined across names (creation comment,
     siblings, old-name logs). No metric change (most renames predate the
     retained history).
  3. Reused destination addresses: `shared_address` item, conflict,
     `V-SHARED-ADDRESS` (verify), MEDIUM at most. TRAP-IP-REUSE 0% -> 100%.
  4. Probe traffic (scanner, monitoring) from close-line packet counts:
     `V-PROBE-ONLY` (verify). TRAP-SCANNER-HITS 0% -> 45% / 37%.
  5. Stale names: `shared_source` item lowers confidence only. Small effect.
  Verdict = best 98.1% -> 97.3% (0-19), 98.2% -> 97.4% (20-49): the cost of
  item 3 (see open questions). Zero dangerous errors throughout.

### Next

- Project lead decisions on the open questions below (reuse cost, not-live
  reading with instances).
- Held-out workflow: add the Hard table (decision 0036) before the second
  held-out run.
- Decision 0032 item 3: real public configs, local only.
- Simulator session: update the spec Hard policy count to 415 (decision
  0036).

### Open questions

- Reused addresses (decision 0039 item 4): both sides of a shared address
  get `verify` because nothing tells the retired application from the
  current one (or from a renamed one). On 0-19 that catches all 72
  TRAP-IP-REUSE rules and turns 155 rules best judged `keep` into
  `verify` (TRAP-STALE-NAME verdict = best 100% -> 62%). Keep this trade,
  or restrict (for example to the side with the older latest ticket:
  34 caught, 70 flagged)?
- Not-live signals with regional instances (decision 0039 item 2): reading
  instances in decommission links would move 3 rules of Hard 0-19 from
  `verify` to `removal_candidate` (application right, best `verify`, not
  dangerous). Not done without approval. Approve?
- Scanner rules without logging show only hit counts: no artifact tells
  probe hits from business hits. Accept as a known limit?
- Carried over: decision 0036 point 3 (drawn instances); anonymize prompt
  login and host; `--strip-text` in the issue template; decision 0020
  example without a migration (needs approval); 90% vs best trade; HIGH
  with an open ticket; decision 0019 blind items; on_call persona; decision
  0015; `commit activate`; CONFIRMED-TEXT; scenario names.

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
  `sed -i 's/$//'` before scripted edits (session 24).
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
  `--runslow` on this machine (19 min serial). Wall time is bounded by one
  simulator test, `test_hard_trap_distribution_over_seeds_0_to_49`
  (350 s alone); see the simulator backlog.

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

- Test speed (session 23): `test_hard_trap_distribution_over_seeds_0_to_49`
  takes 350 s alone and bounds the parallel suite (8 min); splitting it
  per seed (or caching scenarios) would let xdist spread it.

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
`6ede7008-8cee-4e93-a9f2-2a82c52771a8`. Finalize it at the start of session
25 with:

    uv run python metrics/session_tokens.py 6ede7008-8cee-4e93-a9f2-2a82c52771a8

Cost is API-equivalent (decision 0006), not a billed amount.
