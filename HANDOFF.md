# Handoff

## Last session: 18 (2026-10-06), analyzer: questionnaire fixes, real local model measure, prompt injection

### Note for analyzer sessions

- No ground truth schema change.
- Decision 0028 (supersedes the licensing part of 0027): untrusted artifact
  text (descriptions, commit comments, ticket summaries) sits in an
  `<artifact_data>` block of the prompt as neutralized JSON strings and
  licenses no fact in validation; a sentence citing only free text must
  attribute it; judgment and instruction words are rejected. Ollama
  requests: `think: false`, 400 token cap.
- `--no-llm` stays the default (measured, see `docs/llm-writer-measure.md`).
  If `--llm`: `qwen3.5:4b-q4_K_M`.
- Every questionnaire says "If we do not hear back, the rule is kept."
  `palimp report` also writes `00-firewall-team-cleanup.txt`. "Worth a
  look" is ranked by risk (`report.LookEntry`, `Report.worth_a_look`):
  any application or any source, internet-facing zone (`INTERNET_ZONES`),
  counters only, LOW confidence; Markdown top 20, JSON all.

### Done

- Part A: session 17 metrics finalized (75 calls, 4.98 USD); the three
  small fixes above, tested (Easy fast, Medium seed 0 slow).
- Part B: hardware (Ryzen 5 5600H, 31.3 GB RAM, RTX 3050 Laptop 4 GB);
  pulled llama3.2:3b (2.0 GB) and qwen3.5:4b-q4_K_M (3.3 GB);
  `eval/llm_writer.py` measures a model on a stratified sample (60 rules of
  Medium seeds 0-2) and, with `--poison`, the prompt injection test.
  qwen3.5:4b: 16.7% sentences rejected, 58% paragraphs fully LLM, 8.8 s
  per rule; llama3.2:3b: 52.6%, 10%, 4.7 s. 0 judgments changed. Manual
  review of passed sentences (seed 0): about 8% (qwen) and 36% (llama)
  wrong or misleading. Poisoned copy: 0 injected claims kept, 0 judgments
  changed, both models. Prompt injection tests with the fake backend
  (`tests/test_prompt_injection.py`). Three false positives fixed after a
  first run (rule line citations, own policy name, lowercase "may"), and
  the month of a cited ISO date is now licensed.

### Next

- Project lead: read `docs/llm-writer-measure.md` (side by side, review)
  and decide whether the LLM writer is worth more work. Options: give the
  LLM the intent, confidence and verdict reason as sentences it must keep;
  a relation check (a person named with "requested" must come from a
  ticket item of this rule, not an application requester item).
- Known false positives (not fixed, to keep the measure comparable):
  "in zone servers" reads "zone" as an application; ordinary words before
  "server" ("specific", "rule", "allows", "predefined").
- Project lead: held-out run for a release including sessions 14 to 18.
- Carried over: remaining dead rules at verify (mostly no logging), owners
  of applications with no ticket.

### Open questions

- Is the LLM writer worth more sessions, given the numbers? (decision 0028)
- Internet-facing is a zone name list (`internet`, `untrust`, `outside`,
  `external`, `wan`): good enough, or should it use public addresses?
- Carried over: decision 0020 example without a migration (needs
  approval); held-out level and count; 90% vs best trade; HIGH with an open
  ticket; decision 0019 blind items; per trap metric; Hard trap weights;
  on_call persona; decision 0015; `commit activate`; CONFIRMED-TEXT;
  scenario names.

### Known issues

- Validation checks tokens, not relations: a sentence relating true facts
  wrongly passes (about 8% of passed qwen sentences).
- A paragraph with a rejected sentence mixes LLM sentences and the
  deterministic text, which can repeat facts.
- Prose validation does not detect a negated verdict ("should not be kept")
  or a lowercase application name palimp never saw (decision 0027).
- The report prints the artifact path as given on the command line.
- 3 MISLEADING-COMMENT rules on 20 to 99 show no conflict (not inspected).
- `vendor-arch-109` still does not name `archive`.
- Carried over: held-out `scenario_id` can equal a dev id; logged sessions
  undercount traffic; time of day in logged time zone; Junos predefined
  applications from general knowledge (VSRX-12); VSRX-2b; `svc-ansible`; S2
  and S5; git identity in repo config only; session 2 Part C checks.

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
`fd2407ac-42b6-4684-a907-dbaff839c04d`. Finalize it at the start of session 19
with:

    uv run python metrics/session_tokens.py fd2407ac-42b6-4684-a907-dbaff839c04d

Cost is API-equivalent (decision 0006), not a billed amount.
