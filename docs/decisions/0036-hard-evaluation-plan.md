# 0036 Hard evaluation: dev seed split, held-out table, trap tags, frozen Medium

- Status: Accepted
- Date: 2026-10-13
- Supersedes: nothing. It extends decision 0021 (the held-out workflow
  gains a Hard table later) and settles four open questions left by
  session 22 (decision 0035).

## Context

Session 22 built the Hard simulator level (decision 0035) and left open
questions for the project lead in `HANDOFF.md`:

- does Hard join the held-out run, and how (decision 0021);
- which Hard dev seeds tune the analyzer;
- TRAP-SCANNER-HITS is tagged on every dead rule whose hits all come from
  the scanner or a monitoring probe, including rules the scanner reaches by
  accident (86% of scenarios have one, for 80% drawn): keep tagging by
  condition, or tag only the drawn subjects;
- the Medium "v2" knob values of the spec stay unapplied: apply them now or
  after the release;
- Hard has 415 policies per scenario on average, under the spec's
  approximate 450: accept, or raise access requests.

The session 23 prompt answers all five.

## Decision

1. **Held-out.** Hard joins the held-out workflow later, as a separate
   table. Medium stays the comparable headline: its numbers are compared
   run to run, Hard numbers are reported next to them and never merged into
   them. The workflow change (level, number of scenarios, salt rotation of
   spec 8.2 if it applies) is made in its own session, before the second
   held-out run.
2. **Hard dev seeds.** Seeds 0 to 19 tune the analyzer: they may be
   inspected rule by rule. Seeds 20 to 49 check: aggregate tables and the
   dangerous error list only, used to confirm that a change found on 0 to 19
   generalizes. Seeds 50 and above are not used yet.
3. **Trap tags reflect reality.** A trap tag says what is true of the rule,
   not what the simulator meant to draw. Every rule whose only traffic is a
   scanner sweep (or a monitoring probe) is tagged TRAP-SCANNER-HITS, drawn
   or not, as session 22 does. Per-instance metrics count drawn instances:
   the simulator's per-trap measurements count what was drawn, and the
   evaluation's per-instance column groups tagged rules by creation event
   (`eval/verdicts.py`). The ground truth carries no "drawn" flag, so the
   evaluation cannot separate drawn from accidental instances; adding one is
   a schema change (decision 0017) and is not made.
4. **Medium stays frozen until the release.** The Medium "v2" knob values
   stay unapplied, so Medium output stays byte-identical and the second
   held-out run on Medium stays comparable with the first.
5. **415 policies per Hard scenario is accepted.** No version bump to raise
   access requests. The next simulator session updates the spec number.

## Alternatives considered

- Merge Hard into the held-out headline: breaks run-to-run comparison of
  the headline, which so far is Medium only.
- Keep Hard out of held-out for v1: Hard holds the four new traps, and
  tuning on dev seeds only would leave them without an independent check.
- One Hard dev range used for both tuning and checking: no way to see
  overfitting to the inspected seeds before the held-out run.
- Tag only drawn TRAP-SCANNER-HITS subjects: the tag would hide a real
  situation (a dead rule kept alive in the counters by a scanner) because
  the simulator did not intend it; an analyzer scored on drawn tags only
  could fail on the accidental ones unseen.
- Apply the Medium v2 values now: changes Medium output and breaks
  comparison with held-out run 1.
- Raise Hard access requests to reach 450: needs a simulator version bump,
  which moves the Easy and Medium golden hashes, for a count the evaluation
  does not depend on.

## Consequences

- Session 23 records a Hard dev baseline (seeds 0 to 19 and 20 to 49
  separately) in `docs/evaluation-history.md`, before any Hard tuning.
- Per-trap numbers for TRAP-SCANNER-HITS include accidental instances, so
  they are not comparable with the drawn rate of decision 0035.
- The held-out workflow still runs Medium only until the session that adds
  the Hard table.

## Challenged by Nathan

Yes, on point 3: the session 22 question offered "only the drawn subjects";
the project lead answered that tags reflect reality. Outcome: tagging by
condition stays, as session 22 built it.
