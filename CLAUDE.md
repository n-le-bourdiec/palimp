# palimp

Read this file fully at the start of every session. It is the project's memory.
Then read `HANDOFF.md` to know where the last session stopped.

## What palimp is

An open-source, offline CLI that reconstructs the lost intent behind inherited
firewall rules. Input: artifacts an engineer finds when inheriting a firewall
(Junos config, commit history, rollback files, session logs, hit counts,
optional ticket/CMDB CSV exports). Output: for each rule, a probable intent,
the ranked evidence behind it, a confidence level, a verdict
(keep / verify / removal candidate) and the question to ask the rule owner.

Existing tools say what a rule does or what is wrong with a ruleset.
palimp answers why a rule exists.

## Non-negotiable principles

1. Zero network egress. Nothing leaves the machine. The optional LLM runs
   locally (Ollama). No telemetry, no update checks.
2. Deterministic first. Parsing, evidence collection and confidence scoring
   are plain, tested, reproducible code.
3. The LLM writes, it never judges. It only turns established facts into
   prose. Every sentence must cite an evidence ID (e.g. [E2]); a validation
   pass rejects any sentence without a valid citation. `--no-llm` must stay
   fully functional.
4. Read-only, always. palimp never connects to a device and never generates
   commands meant to be pushed.

## Evidence hierarchy

- T1 direct: commit comment, policy description, ticket reference in a name.
- T2 behavioral: session logs, hit counts, who actually talks to whom and when.
- T3 structural: address-book object names, zones, rules created in the same
  commit, object consistency.
- T4 contextual inference: well-known ports, common patterns.

Confidence is computed from which tiers are present and whether they agree.
A rule backed only by T4 can never exceed LOW confidence.

## v1 scope

- Juniper SRX security policies only, Junos "set" format input.
- Commands: `ingest`, `explain <policy>`, `report`, `questions`, `anonymize`, `demo`.
- Out of scope for v1: other vendors, live connections, config changes,
  advanced shadowing detection, web UI.

## Testing strategy

palimp is evaluated against a synthetic company simulator that generates a
realistic firewall history plus a ground-truth file (true intent of every rule).
- The simulator and the analyzer never share code.
- Independence rule: analyzer sessions read neither `simulator/` code nor
  `docs/simulator-spec.md`, only the ground truth JSON Schema
  (`simulator/src/palimp_sim/schema/ground_truth.schema.json`). Simulator
  sessions do not read `src/palimp`.
- Any change to the ground truth JSON Schema, even additive, needs its own
  decision file and a note in `HANDOFF.md` addressed to analyzer sessions
  (decision 0017).
- Scenarios are split into a dev set and a held-out test set. Never look at
  held-out results while tuning the analyzer.
- The held-out workflow is run only by the project lead, at most once per
  release. Every run is recorded in `docs/evaluation-history.md`.
- Real Junos output formats come from samples copied from Juniper's official
  documentation, stored under `tests/fixtures/junos_docs/` (decision 0013).
  A vSRX lab stays a later upgrade.
- Key metrics: intent accuracy, confidence calibration (HIGH must be right
  90%+ of the time), zero unsourced claims, and "removal candidate on a live
  rule" counted as the most severe error.

## Stack and conventions

- Python 3.12+, uv for packaging, Typer for the CLI, pydantic for models.
- pytest, ruff (lint + format). CI must stay green.
- License: Apache 2.0.
- Code, docs and commit messages in American English.
- Never use em dashes or en dashes in any text (docs, README, comments, commits).
  Use commas, parentheses or a simple hyphen.
- Small, focused commits with clear messages.

## Decisions

Every significant decision gets a file in `docs/decisions/NNNN-title.md`:
context, decision, alternatives considered, consequences, and whether it was
challenged by Nathan (and the outcome). Never contradict a recorded decision
silently: propose a new decision file that supersedes it.

Amend or supersede:
- Amend the existing file (with a dated "Amendment" section) only to correct
  facts: a wrong date, a missing alternative, a renamed path, a factual error.
- Supersede it with a new file when the decision itself changes. The new file
  says which decision (or which part) it supersedes, and the old file's
  `Status` line points to the new one.

## Working rules for every session

1. One mission per session, stated in the prompt. Do not start other work.
2. Initiative outside the stated mission is allowed only if it moves verdicts
   in the safe direction (toward `keep` or `verify`), and it must be flagged in
   the session report. Anything that moves a rule toward `removal_candidate`
   needs the project lead's approval first.
3. Commit after each meaningful step, so an interruption loses little.
4. Token budget: if you estimate you are close to the usage limit, or you
   receive any usage warning, stop immediately, commit, update `HANDOFF.md`
   and produce the session report. A clean stop beats an unfinished change.
5. Before ending, always:
   - update `HANDOFF.md` (what was done, what is next, open questions, known issues);
   - append one row to `metrics/sessions.csv`;
   - push every commit of the session (`git push`) and check the CI run of the
     last push (`gh run list`, `gh run watch`);
   - print the session report below, with the CI status of the last push.

## Metrics row (metrics/sessions.csv)

Columns: date, session_id, phase, mission, duration_min, model,
tokens_input, tokens_output, tokens_cache_read, tokens_cache_write,
est_cost_usd, commits,
lines_added, lines_removed, tests_total, tests_passing, eval_accuracy,
eval_calibration, eval_dangerous_errors, challenges_received,
decisions_changed, notes

Use real measured values only. If a value cannot be measured (for example
token usage is not accessible), write `n/a`. Never estimate silently.
`challenges_received` and `decisions_changed` are filled from the prompt if provided.
`est_cost_usd` is the API-equivalent cost computed by `metrics/session_tokens.py`
from `metrics/pricing.json` (decision 0006), not a billed amount.

Every session starts by finalizing the previous session's row with its final
token counts and cost, measured with `metrics/session_tokens.py` (use `--since`
and `--until` when several sessions share one transcript).

## Session report format

Print this at the end of every session, as plain text, so it can be pasted back:

```
SESSION REPORT
Mission: <one line>
Status: DONE | PARTIAL | BLOCKED
Done:
- ...
Not done / next:
- ...
Decisions taken (with file names):
- ...
Problems or doubts:
- ...
Questions for the project lead:
- ...
Metrics: tokens in/out/cache, commits, tests passing/total, eval scores if any
CI: <green | red | pending> for commit <short sha>, all commits pushed: yes | no
```
