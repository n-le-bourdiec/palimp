# 0014 Extra evidence items are not errors unless misleading

- Status: Accepted
- Date: 2026-10-04
- Supersedes: the session 6 amendment of decision 0011 (now removed from
  0011) and the consequence of 0011 about "found but not expected" items

## Context

Decision 0011 counts evidence items palimp reports without a ground truth
counterpart separately, as "found but not expected". On the Easy dev seeds,
palimp reports about 20 such T3 items. In session 6 a clarification was added
to 0011 as an "Amendment". That clarification changes how these items are
scored, which is a change of decision, not a factual correction, so under the
project rules it belongs in a new decision that supersedes the old text.

## Decision

Evidence items palimp finds that the ground truth does not list are not
counted as errors, unless they are misleading.

- An extra item is **misleading** when its claim points toward an intent or a
  verdict that the ground truth contradicts (for example an extra T3 item that
  makes a live rule look like a removal candidate).
- An extra item that is true but simply not listed (for example a generic
  address object) is **neutral**.

The harness does not yet classify extra items as misleading or neutral. Until
it does, they are reported per tier and artifact but never scored as errors.

## Alternatives considered

- Keep the clarification as an amendment of 0011: rejected, amendments are
  reserved for factual corrections (CLAUDE.md).
- Count every extra item as a false positive: penalizes true evidence the
  ground truth happens not to list, and pushes the analyzer toward reporting
  less.
- Ignore extra items entirely: hides misleading evidence, which is exactly
  what can produce a "removal candidate on a live rule".

## Consequences

- Precision of evidence is not measured yet; only recall is.
- A classifier for misleading extra items is needed before verdicts are
  scored. It must work from the ground truth (intent and verdict), not from
  locator text, to respect decision 0011.

## Challenged by Nathan

Yes, twice. First challenge (session 6): extra items are not errors. Second
challenge (session 7): the clarification changes the decision, so it must
supersede rather than amend 0011. Outcome: this decision.
