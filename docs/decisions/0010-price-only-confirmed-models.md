# 0010 Price only models confirmed on official pages

- Status: Accepted
- Date: 2026-10-04 (decided in session 3, recorded as a separate file in session 4)
- Supersedes: the part of 0006 that let `pricing.json` contain model ids inferred
  from the naming pattern.

## Context

Decision 0006 records session cost as an API-equivalent cost computed from
`metrics/pricing.json`. The first version of that file listed model ids that
were not printed on any official page, only inferred from the naming pattern.
A wrong id would silently price a session with the wrong model, or with a model
that does not exist.

## Decision

- `pricing.json` lists only models whose API id appears on Anthropic's official
  models overview page and whose prices appear on the official pricing page.
  Both URLs and the retrieval date are recorded in the file.
- A model missing from `pricing.json` gives `est_cost_usd` `n/a` and a warning
  on stderr. `metrics/session_tokens.py` never guesses a price.

## Alternatives considered

- Keep inferred ids, flagged as unconfirmed (first version): convenient, but a
  flag in a JSON note does not stop a wrong price from reaching the CSV.
- Price unknown models with the closest known model: a silent estimate, which
  CLAUDE.md forbids.

## Consequences

- Sessions run with a model that is not listed get `n/a` until someone adds it
  from the official pages.
- Past rows are not recomputed (0006).

## Challenged by Nathan

Yes, in session 3 ("unconfirmed prices"). Outcome: decision changed.
