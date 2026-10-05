# 0020 Absence of evidence is never evidence of absence

- Status: Accepted
- Date: 2026-10-05

## Context

palimp now has to turn evidence into a verdict (keep, verify, removal
candidate) and a confidence level. The most severe error palimp can make is
"removal candidate" on a rule that still carries needed traffic.

Zero hits and an empty session log look like proof that a rule is unused, and
that is what a naive cleanup tool concludes. They are not proof:

- a quarterly or yearly job does not show in a 60-day log window, and hit
  counters may have been cleared recently (TRAP-RARE-JOB);
- a policy without `then log` never appears in the session log, whatever its
  traffic (TRAP-LIVE-NOLOG, decision 0019);
- the clear date of the hit counters is not in `hitcount.txt`, so "0 hits"
  covers an unknown period.

## Decision

A rule can be a `removal_candidate` only when at least one positive not-live
signal backs it. A positive not-live signal is an artifact that says the rule
is unused, not an artifact that says nothing. Examples:

- the policy is deactivated in the configuration (it matches no traffic);
- a commit comment or a ticket decommissions or retires the application that
  the policy's address objects belong to, after the policy was created;
- a later commit removed other policies to the same address object and left
  this one behind (a cleanup leftover);
- the destination is never seen in any log while other logging rules to
  neighboring hosts are seen (not implemented yet).

Zero hits and no log lines alone always give `verify`, never
`removal_candidate`. A positive not-live signal next to a `present` T2 signal
(traffic seen) is a contradiction and also gives `verify`.

Every verdict and every confidence level carries the identifier of the rule
that produced it, so that each output is explainable and testable.

Confidence is about the intent, and comes from which tiers support it and
whether they agree:

- HIGH needs direct evidence (T1) that names the same application as the
  structural evidence (T3), with no conflict;
- T4 alone never exceeds LOW;
- when two tiers contradict each other (a commit comment names one
  application, the address objects another), confidence is lowered and an
  explicit conflict finding cites both evidence IDs.

## Alternatives considered

- Score absence as a weak not-live signal and let enough of it add up to a
  removal candidate (what the ground truth `verdict` field does for many
  dead rules): this is how a live quarterly job gets removed. Rejected: the
  cost of a wrong removal is an outage, the cost of a wrong verify is one
  question to an owner.
- A numeric score with thresholds: harder to explain and to test than named
  rules, and thresholds invite tuning on the dev set.
- Leave verdicts to the LLM: principle 3, the LLM writes, it never judges.

## Consequences

- Rules that are dead but leave no positive trace get `verify`. Against the
  ground truth `best_achievable_verdict`, palimp loses those points on
  purpose; the evaluation reports them separately from dangerous errors.
- palimp needs evidence collectors for positive not-live signals
  (deactivation, decommission markers, cleanup leftovers), cited like any
  other evidence item.
- Verdict and confidence rules are named (for example `V-NOTLIVE`,
  `C-T1-T3-AGREE`) in the JSON output and in `explain`.

## Challenged by Nathan

Yes, in the session 12 prompt: build the evaluation with a naive baseline
first (zero hits gives removal candidate, otherwise keep), then improve the
evidence. Outcome: adopted; the session reports palimp before and after the
new not-live evidence collectors, next to the baseline.
