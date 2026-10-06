# Handoff

## Last session: 19 (2026-10-06), analyzer: palimp anonymize, internet-facing from public addresses, LLM frozen for v1

### Note for analyzer sessions

- No ground truth schema change.
- Decision 0029: the LLM writer stays experimental and off by default for
  v1. No further LLM work before v1 (`palimp.prose`, `palimp.llm`,
  `eval/llm_writer.py` only kept passing).
- Decision 0030: internet-facing (Worth a look ranking only) is a public
  address on either side (`palimp.addresses`, documentation ranges count as
  public), else a zone named like the internet on a side with `any` or
  unresolved addresses. Reason in `RuleEntry.internet`.
- Decision 0031: `palimp anonymize -a DIR -o OUT --key KEYFILE
  [--strip-text] [--shift-dates] [--mapping]`. Words palimp reads as
  signals are kept in names (`palimp.anonymize.is_signal`): if you add a
  word list to the analyzer (role, temporary, decommission, ticket prefix,
  internet zone), add it to `is_signal` too, or anonymized copies will
  stop reproducing the analysis. `tests/test_anonymize.py` (slow) catches it
  on Medium seeds 0 to 9.

### Done

- Part A: session 18 metrics finalized (148 calls, 9.82 USD); decision 0029
  (README and `--help` say experimental); decision 0030 with tests. Medium
  seed 0: 34 internet-facing rules (29 by public address, 5 by zone), same
  count as the zone list on this seed.
- Part B: `palimp anonymize` (`src/palimp/anonymize.py`): HMAC-SHA256 keyed;
  prefix- and class-preserving IP mapping; names mapped run by run with
  prefix-dependent permutations (length, case, shared prefixes kept); known
  names, IPs, ticket IDs, e-mails, initials after req and upper-case short
  names replaced in free text; system and SNMP lines word by word; mapping
  redrawn with the next salt if a replacement hits a kept word. Only files
  palimp reads are copied, plus `ANONYMIZED.txt`. Key created if missing;
  key and `OUT.PRIVATE-mapping.json` refused inside OUT. About 4.5 s for a
  Medium scenario.
- Tests: Medium seeds 0-9 identical verdicts, confidence, owner certainty
  and Worth a look ranking, no original name, person word, ticket ID or IP
  left (except as another value's replacement); shifted dates keep
  judgments (seed 0); same key same bytes, other key other mapping;
  strip-text; address classes and subnets; CLI guards.
- README: "Sharing a problem config safely in an issue".

### Next

- Project lead: try `palimp anonymize` on a real config before
  recommending it in the issue template; review the limits in decision 0031.
- Project lead: held-out run for a release including sessions 14 to 19.
- Carried over: remaining dead rules at verify (mostly no logging), owners
  of applications with no ticket.

### Open questions

- Should the issue template ask for `--strip-text` by default? (palimp
  keeps free text by default, as the prompt asked.)
- Carried over: decision 0020 example without a migration (needs
  approval); held-out level and count; 90% vs best trade; HIGH with an open
  ticket; decision 0019 blind items; per trap metric; Hard trap weights;
  on_call persona; decision 0015; `commit activate`; CONFIRMED-TEXT;
  scenario names.

### Known issues

- Anonymize limits (decision 0031): pseudonymization, not encryption;
  names palimp does not know stay in free text; non-ISO dates in free text
  are not shifted; a kept signal word that starts a longer name loses the
  shared prefix; people with a one-letter name word may get other initials.
- LLM writer limits frozen for v1 (decisions 0027 to 0029): wrong relations
  between true facts pass validation (about 8% of passed qwen sentences);
  negated verdicts and unseen lowercase application names not detected;
  mixed paragraphs can repeat facts.
- The report prints the artifact path as given on the command line.
- 3 MISLEADING-COMMENT rules on 20 to 99 show no conflict (not inspected).
- `vendor-arch-109` still does not name `archive`.
- Carried over: held-out `scenario_id` can equal a dev id; logged sessions
  undercount traffic; time of day in logged time zone; Junos predefined
  applications from general knowledge (VSRX-12); VSRX-2b; `svc-ansible`; S2
  and S5; git identity in repo config only; session 2 Part C checks.

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
has transcript `63a66e24-b7a2-43f0-9fe2-32d2c7b0b4af`. Finalize it at the start
of session 20 with:

    uv run python metrics/session_tokens.py 63a66e24-b7a2-43f0-9fe2-32d2c7b0b4af

Cost is API-equivalent (decision 0006), not a billed amount.
