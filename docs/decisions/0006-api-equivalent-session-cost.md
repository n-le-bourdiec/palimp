# 0006 Session cost is recorded as an API-equivalent cost

- Status: Accepted
- Date: 2026-09-28

## Context

Each session appends a row to `metrics/sessions.csv`, including `est_cost_usd`.
Sessions run in Claude Code, and Claude Code does not expose a billed amount
for the running session on this machine. Session 1 therefore recorded `n/a`.
Token counts, however, are available per API call in the local transcript,
together with the model id, the cache write duration (5 minutes or 1 hour) and
the speed mode.

## Decision

`est_cost_usd` is the API-equivalent cost: what the session's tokens would cost
on the Claude API at list prices.

- Prices live in `metrics/pricing.json`, copied from Anthropic's official
  pricing page, with the source URL and retrieval date in the file.
- `metrics/session_tokens.py` computes the cost per API call from its model,
  input, output, cache read, 5 minute and 1 hour cache writes, fast mode, US
  inference multiplier and web searches, then sums it.
- If any call uses a model missing from `pricing.json`, the cost is `n/a`
  rather than a partial sum.
- When prices change, update `pricing.json` (new retrieval date). Past rows are
  not recomputed.

## Alternatives considered

- Keep `n/a`: honest but gives no way to compare sessions.
- Actual billed cost: not accessible from Claude Code on this machine, and on
  a subscription plan it does not map to a per-session amount.
- A single blended price per token: simpler, but wrong by a large factor
  because cache reads cost 5% of input on Opus 5.5 and dominate the volume.

## Consequences

- Sessions are comparable in dollars, independently of the plan used.
- The figure is not an invoice amount and must not be read as one.
- Calls made by Claude Code outside the transcript (for example the small model
  behind the web fetch tool) are not counted.
- Model ids in `pricing.json` other than those observed in Claude Code are
  inferred from the naming pattern and noted as unconfirmed.

## Challenged by Nathan

No.
