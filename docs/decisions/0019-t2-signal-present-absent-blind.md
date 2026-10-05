# 0019 T2 evidence says whether traffic is present, absent, or unknowable

- Status: Accepted
- Date: 2026-10-05

## Context

Behavioral evidence (T2) comes from two artifacts: hit counts and RT_FLOW
session logs. "No log line for this policy" means two different things:

- the policy logs sessions and none was logged: no traffic in the window;
- the policy has no `then log` statement (or is deactivated, or the artifact
  is missing): the artifact cannot show its traffic at all.

Treating both as "no traffic" is exactly the TRAP-LIVE-NOLOG error, which
leads to "removal candidate on a live rule", the most severe error. The
confidence scoring to come must be able to tell these cases apart without
parsing claim text.

## Decision

Every T2 evidence item carries a `signal` field:

- `present`: the artifact shows traffic (hits above zero, sessions logged);
- `absent`: the artifact could show traffic for this policy and shows none
  (zero hits, a logging policy with no session in the log window);
- `blind`: the artifact cannot show traffic for this policy (no logging,
  deactivated policy, no hit count row, artifact not provided).

A blind item is emitted on purpose, so that the explanation states the gap
explicitly. It is a stated limit, never evidence of use or non-use: scoring
must not count it as T2 support, and the evaluation harness leaves it out of
T2 recall. `signal` is empty for T1, T3 and T4 items.

palimp emits at most one T2 item per artifact and policy.

## Alternatives considered

- Leave the gap out of the evidence list: the explanation would then be
  silent exactly where the reader most needs a warning.
- A separate "gaps" list outside the evidence: gaps could not be cited with
  an evidence ID by the LLM writer (principle 3).
- Infer the meaning from the claim text: fragile, and locators and claims are
  free text (decision 0011).

## Consequences

- The `Evidence` model gains an optional `signal` field; JSON output of
  `explain` includes it (null for non-T2 items).
- Scoring (next milestone) can require a `present` or `absent` item before
  using T2 to support a verdict.
- An `absent` hit count is still weak when the clear date is unknown:
  hitcount.txt does not record when counters were last cleared, and claims
  say so.

## Challenged by Nathan

Not challenged. The session 11 prompt asked for the distinction ("say
explicitly when a T2 signal is absent because the policy has no logging,
versus because there is no traffic"); the `signal` field is how it is
recorded.
