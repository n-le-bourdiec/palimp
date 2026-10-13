# 0038 Dangerous error: removal_candidate on a live or still needed rule

- Status: Accepted
- Date: 2026-10-13
- Supersedes: the definition of a dangerous error used by `eval/verdicts.py`
  since it was added on 2026-10-05 ("removal_candidate on a rule whose
  `status.live` is true"). The metric line of `CLAUDE.md` now names this
  decision.

## Context

The ground truth gives two separate facts for every rule (JSON Schema,
`status.live` and `status.still_needed`). A rule can be not live in the
sense of its original intent (the application it was written for is
retired) and still needed, because it now carries other traffic that
matters: an address of the retired application was reused by a current
one (TRAP-IP-REUSE), or a broad rule took over flows of removed rules.

The evaluation counted only `status.live`. A `removal_candidate` on such a
rule was then scored as a plain verdict miss, while removing the rule
breaks a current flow, which is exactly the harm the dangerous error
metric is meant to catch. The project lead raised it in the session 24
prompt.

## Decision

1. A dangerous error is `removal_candidate` on a rule whose `status.live`
   **or** `status.still_needed` is true.
2. `eval/verdicts.py` reports the new count as "dangerous errors" and the
   old count (`status.live` only) next to it, in the headline, per trap
   and per format variant, for palimp and the naive baseline. The list of
   dangerous rules says, for each one, whether it is live or only still
   needed.
3. Held-out run 1 (2026-10-05) was scored with the old definition; this is
   noted in `docs/evaluation-history.md`. It is not rerun (the held-out
   workflow runs at most once per release).
4. The release gate (decision 0032: no dangerous error on held-out or on
   real public configs) uses the new definition.

## Alternatives considered

- Keep `status.live` only and add a separate "still needed" metric: two
  numbers for one harm, and the gate would have to name both. Rejected.
- Count only rules with `status.still_needed` (ignore `live`): a live rule
  that is no longer needed is still dangerous to remove blind (the owner
  must confirm first). Rejected.

## Consequences

- The dangerous error count can only grow for the same verdicts. Earlier
  dev numbers stay comparable through the old count printed next to it.
- Analyzer tuning must keep zero dangerous errors under the new
  definition on Hard 0-49 and Medium 20-99 (session 24).

## Challenged by Nathan

Raised by the project lead (session 24 prompt, challenge 1 of 3): the
dangerous error metric must include rules that are still needed. Accepted
as stated.
