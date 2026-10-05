# 0017 Event kind `access_request` added to the ground truth schema

- Status: Accepted
- Date: 2026-10-05 (change made in session 9, recorded in session 10)
- Supersedes: nothing

## Context

The ground truth JSON Schema
(`simulator/src/palimp_sim/schema/ground_truth.schema.json`) is the only
contract shared by the simulator and the analyzer: analyzer sessions read it
and nothing else from `simulator/` (CLAUDE.md, independence rule).

Session 9 built the Medium level, which adds ad hoc access requests (spec
4.9): a named workstation or an outside vendor gets access to one back-end
server, and the rule is sometimes removed when the access ends. These are
timeline events, and each event in the ground truth has a `kind` taken from a
closed enum. None of the existing kinds fit. Session 9 added `access_request`
to the enum inside the commit that generated Medium (1a97fca), without a
decision file, and listed it as an open question in `HANDOFF.md`.

## Decision

1. The event `kind` enum gains `access_request`. It is used for the creation
   of an access rule and for its removal when the access ends (the removal
   event carries the note `access removed`).
2. The change is additive: every document valid before stays valid, so
   `schema_version` stays 1.
3. From now on, any change to the ground truth JSON Schema, additive or not,
   gets its own decision file and a note in `HANDOFF.md` addressed to
   analyzer sessions (recorded in CLAUDE.md, session 10).

## Alternatives considered

- Reuse an existing kind (`new_app` or `routine`) with a note: no schema
  change, but per-event metrics and readers of the ground truth could not
  tell access requests from application go-lives or routine changes.
- Bump `schema_version` to 2: signals the change loudly, but nothing in an
  existing document changes meaning, and the analyzer would have to accept
  two versions for no gain.
- Leave the change undocumented beyond the commit message: analyzer sessions
  only see the schema file, so a silent enum change could break an analyzer
  that validates event kinds against a fixed list.

## Consequences

- Analyzer code that maps event kinds (evaluation, reports) must accept
  `access_request`; `HANDOFF.md` carries the note for the next analyzer
  session.
- Schema changes are now visible as decisions, which keeps the independence
  rule workable: analyzer sessions learn about the change without reading
  simulator code.

## Challenged by Nathan

Raised by session 9 itself as an open question (schema change made in a
simulator session). The session 10 prompt asked for this record and for the
rule in point 3. Outcome: adopted as stated.
