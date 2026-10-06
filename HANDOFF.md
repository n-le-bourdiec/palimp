# Handoff

## Last session: 20 (2026-10-06), analyzer: plan before release (decision 0032), hierarchical config format (decision 0033)

### Note for analyzer sessions

- No ground truth schema change.
- Decision 0032: plan before release (below). v1 reads set and hierarchical
  configurations (decision 0003 superseded in part).
- Decision 0033: `palimp.formats.junos_config.parse_config` detects the
  format per file and is what ingest, rollbacks and anonymize call. The
  hierarchical walker (`palimp.formats.junos_hier.statements`) feeds the
  set reader's `_Builder`, so any new statement the analyzer reads must be
  added to the builder only, and both formats get it. `Policy.annotations`
  holds `/* */` notes; evidence kind `annotation` is treated like
  `description` (assess `INTENT_KINDS`, owners initials, ticket refs,
  temporary words, prose `FREE_TEXT_KINDS`, anonymize free text). If you add
  a description-based rule, add annotations to it too.
- `tests/conftest.py` has `to_hierarchical(src, dst)`: renders a scenario's
  config and rollbacks as hierarchical text from the parsed model.

### Done

- Part A: session 19 metrics finalized (67 calls, 5.85 USD, 43 min);
  decision 0032 recorded, plan below, CLAUDE.md v1 scope updated.
- Part B: hierarchical reader (`inactive:`, `protect:`/`replace:` dropped,
  `/* */` annotations on the next statement, `##` comments, quoted strings,
  `[ ]` lists, prompts and `[edit]` banners, relative `show X Y` output);
  `apply-groups` and deactivated zone pairs reported, not applied (both
  formats); `ingest` prints the format of each file. Annotations are T1
  evidence. Rollbacks may be hierarchical (mixed formats work). Anonymize
  rewrites hierarchical files.
- Fixtures: 8 samples from 6 Juniper documentation pages
  (`tests/fixtures/junos_docs/hier_*.txt`), all parse with 0 unknown lines;
  HIER-1a to HIER-1e in `docs/format-assumptions.md`.
- Round trip on Medium seeds 0-9: model, creation commits, verdicts,
  confidence and owners identical. Anonymize on hierarchical renderings of
  seeds 0-9: identical judgments and Worth a look ranking, nothing left.
- README: artifact layout, both formats, plain statement that palimp has
  never been run on a real SRX history (decision 0032 item 4, done early,
  safe direction).

### Next

- Decision 0032 item 2 (simulator sessions): Hard level with
  TRAP-RENAME-CHAIN, TRAP-IP-REUSE, TRAP-SCANNER-HITS, TRAP-STALE-NAME.
- Decision 0032 item 3: real public configs, local only, never committed.
  First thing to check there: `inactive:`, annotations and descriptions on
  real security policies (HIER-1b to HIER-1d unverified on policies).
- Project lead: try `palimp anonymize` on a real config before
  recommending it in the issue template; review the limits in decision 0031.
- Carried over: remaining dead rules at verify (mostly no logging), owners
  of applications with no ticket.

### Open questions

- `inactive:` on a whole zone pair (or on `security policies`): palimp reads
  the policies under it as active and warns. Marking them deactivated would
  be correct but moves them toward `removal_candidate`: approve? (decision
  0033)
- `apply-groups`: warn only (current) or expand simple groups without
  wildcards?
- Should the issue template ask for `--strip-text` by default?
- Carried over: decision 0020 example without a migration (needs
  approval); held-out level and count; 90% vs best trade; HIGH with an open
  ticket; decision 0019 blind items; per trap metric; Hard trap weights;
  on_call persona; decision 0015; `commit activate`; CONFIRMED-TEXT;
  scenario names.

### Known issues

- Hierarchical: file names stay `config.set` and `rollback-NN.set` whatever
  the format. `global` policies (`security policies global`) are not read
  in either format (pre-existing). An `inactive:` leaf with a value is kept
  as `description x` in `deactivated_statements`, where set output may
  print only the keyword (no sample). `then { permit { application-services
  ... } }` leaves the action unset in both formats (pre-existing, set reader
  needs `then permit` as a leaf; not changed: verdict direction unknown).
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
  and S5; git identity in repo config only; session 2 Part C checks.
- Session 20 note: `docs/assets/` (diagrams, `gen_diagrams.py`) appeared
  untracked during the session; it was swept into a local commit by
  mistake, removed again before any push, and left untracked on disk.
  `uv run ruff check .` fails on `gen_diagrams.py` (line length): fix or
  exclude it before committing it, or CI turns red.

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
Session 20 has transcript `1561b174-b703-4305-b4b4-d9a8a844a436`. Finalize it
at the start of session 21 with:

    uv run python metrics/session_tokens.py 1561b174-b703-4305-b4b4-d9a8a844a436

Cost is API-equivalent (decision 0006), not a billed amount.
