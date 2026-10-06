# 0029 The LLM writer stays experimental and off by default for v1

- Status: Accepted
- Date: 2026-10-06
- Supersedes: nothing (confirms the default of decision 0028 and closes the
  open question "Is the LLM writer worth more sessions?")

## Context

Decision 0027 added an optional prose paragraph written by a local LLM,
decision 0028 hardened it against prompt injection and measured two real
local models (session 18, `docs/llm-writer-measure.md`). The best one,
qwen3.5:4b-q4_K_M on a 4 GB laptop GPU:

- brings no clear gain over the deterministic text, which is the
  assessment itself and often states the intent, confidence and verdict
  reason that the LLM paragraph leaves out;
- passes about 8% of its validated sentences although they relate true
  facts to the wrong evidence (a check on tokens cannot see a wrong
  relation);
- turns a 170-rule report from 1.7 seconds into about 25 minutes.

## Decision

- The LLM writer stays in v1 as an experimental option: `--llm` on
  `explain` and `report`, off by default. `--no-llm` stays the default and
  must stay fully functional (CLAUDE.md principle 3).
- No further LLM work before v1: no prompt changes, no new validation
  checks, no new model measures. The code, its tests (fake backend,
  prompt injection) and the measure script stay as they are and must keep
  passing.
- The README and `--help` call the option experimental.

## Alternatives considered

- Keep improving it (give the LLM the intent, confidence and verdict reason
  as sentences it must keep; a relation check on requesters): postponed
  after v1. The gain is uncertain and the time cost of a report stays.
- Remove the LLM writer from v1: rejected, the code is tested, isolated and
  off by default; removing it would lose the prompt injection defenses and
  the measure harness for a later version.
- Make it the default: rejected on the numbers above (decision 0028).

## Consequences

- Sessions before v1 do not touch `palimp.prose`, `palimp.llm` or
  `eval/llm_writer.py` except to keep them passing.
- Known limits of decisions 0027 and 0028 stay open (wrong relations
  between true facts, negated verdicts, unknown lowercase application
  names) and are listed in `HANDOFF.md` for after v1.

## Challenged by Nathan

Decided by the project lead in the session 19 prompt, from the session 18
measure. Not challenged.
