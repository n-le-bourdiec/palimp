# 0011 Evidence recall matches on rule, tier and artifact

- Status: Accepted
- Date: 2026-10-04

## Context

The evaluation harness (`eval/evidence_recall.py`) compares the evidence palimp
reports for each rule with the evidence the ground truth says a perfect
analyzer could find. Both tools describe the location of an item in a free
text `locator`, written independently (the analyzer must not copy simulator
conventions).

## Decision

An expected ground truth item counts as found when palimp reports, for the
same rule (zone pair and name), an item with the same tier and the same
artifact. Matching is one-to-one. Locators and claims are not compared. Items
palimp reports without a ground truth counterpart are counted separately as
"found but not expected", per tier and artifact.

## Alternatives considered

- Match on locator text: would force both tools to share a locator syntax,
  which couples the analyzer to the simulator.
- Match on a shared structured locator (file plus line): more precise, but
  needs a schema change on both sides; possible later.

## Consequences

- Recall is optimistic: an item with the right tier and artifact but pointing
  at the wrong commit or ticket would still count as found. A stricter match
  (for example on ticket ids and commit indexes) should come with a structured
  locator.
- "Found but not expected" items are not errors by themselves; they show where
  the two tools disagree on what counts as evidence.

## Challenged by Nathan

No.
