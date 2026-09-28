# 0004 Zero network egress, local LLM only

- Status: Accepted
- Date: 2026-09-28

## Context

Firewall configurations, logs and ticket exports are sensitive. Many target users
work in environments where sending this data to a third party is forbidden, and
where a tool that phones home would not be approved at all.

## Decision

- palimp makes no network connections: no telemetry, no update checks, no
  remote APIs.
- The optional LLM runs locally (Ollama). The LLM only turns established facts
  into prose; every sentence must cite an evidence ID and uncited sentences are
  rejected.
- `--no-llm` stays fully functional.
- palimp is read-only: it never connects to a device and never generates
  commands meant to be pushed.

## Alternatives considered

- Hosted LLM APIs: better prose quality, but incompatible with the data
  sensitivity and with air gapped use.
- Opt-in telemetry: useful for the project, but it breaks the "nothing leaves the
  machine" promise that makes the tool acceptable to security teams.

## Consequences

- Output quality with the LLM depends on the local model the user can run.
- All analysis (parsing, evidence, confidence) must be deterministic code, so
  the tool is useful without any LLM.
- Dependencies must be checked for hidden network behavior.

## Challenged by Nathan

No.
