# 0005 Evaluation through a synthetic simulator with ground truth

- Status: Accepted, vSRX lab line superseded by 0013 (documentation-sourced fixtures for now)
- Date: 2026-09-28

## Context

Measuring whether palimp recovers the right intent needs data where the true
intent of every rule is known. Real inherited firewalls have no such ground
truth, and real data cannot be shared publicly.

## Decision

A synthetic company simulator generates a realistic firewall history plus a
ground truth file giving the true intent of every rule.

- The simulator lives in its own `simulator` package and never shares code with
  the analyzer in `src/palimp`.
- Scenarios are split into a dev set and a held out test set. Held out results
  are never looked at while tuning the analyzer.
- Real Junos output formats come from a vSRX lab (containerlab) and are stored as
  parser fixtures.
- Key metrics: intent accuracy, confidence calibration (HIGH must be right 90%
  or more of the time), zero unsourced claims, and "removal candidate on a live
  rule" counted as the most severe error.

## Alternatives considered

- Evaluate only on real anonymized firewalls: realistic, but no ground truth,
  small sample, and not shareable.
- Manual review of outputs: does not scale and is not reproducible.

## Consequences

- The simulator is a real piece of work, with its own risk: the analyzer could
  learn the simulator's habits rather than real world patterns. Code separation
  and the held out set limit this; real world checks remain needed.
- Metrics are reproducible and can be tracked per session in
  `metrics/sessions.csv`.

## Challenged by Nathan

No.
