# 0013 Documentation-sourced fixtures replace the vSRX lab for now

- Status: Accepted
- Date: 2026-10-04
- Supersedes: the vSRX lab line of decision 0005 ("Real Junos output formats
  come from a vSRX lab (containerlab) and are stored as parser fixtures") and
  the matching consequence in decision 0003

## Context

The simulator and the readers rely on twelve format assumptions (VSRX-1 to
VSRX-12) meant to be checked on a vSRX lab. A real vSRX is not available
(image access, licensing and host virtualization are not settled).

## Decision

Until a real device is available, format assumptions are checked against
sample output copied from Juniper's official documentation
(juniper.net/documentation, CLI reference, syslog reference). Each sample is
stored under `tests/fixtures/junos_docs/` with a header giving source URL,
page title, Junos release shown and retrieval date. A sample counts only if it
is copied from a documentation page; nothing is invented. Results are recorded
in `docs/format-assumptions.md` as CONFIRMED, CORRECTED or UNVERIFIED.

A real vSRX (or a real SRX capture) stays a later upgrade and would take
precedence over documentation samples.

## Alternatives considered

- Wait for a vSRX lab: blocks every format check for an unknown time.
- Use samples from forums or blog posts: closer to real devices sometimes, but
  unverifiable provenance and often edited.

## Consequences

- Documentation samples are often abridged, reformatted, or from older
  releases. Behavioral assumptions (retention, counter reset, order after
  insert) are rarely shown and may stay UNVERIFIED.
- Fixtures carry their provenance, so a later vSRX capture can replace them
  one by one.

## Challenged by Nathan

Decision made by Nathan (project lead), session 6.
