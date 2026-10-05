# 0016 Medium format variants drawn per scenario, with syslog clock skew

- Status: Accepted
- Date: 2026-10-05
- Supersedes: no decision file. It replaces the fixed Medium format defaults
  chosen in session 8 (spec 7.1: `log_collection=syslog-server`,
  `rescue_line=yes`, `log_release=pre-22.2`, `hitcount_layout=standard`).

## Context

Session 8 added four format knobs, each matching a layout seen in the
documented Junos samples (`tests/fixtures/junos_docs/`): `log_collection`
(`device` or `syslog-server`), `log_release` (`12.x`, `pre-22.2`, `22.2`),
`hitcount_layout` (`standard` or `legacy`) and `rescue_line`. It gave Medium
one fixed value for each. With fixed values, every Medium scenario has the same
formats, so the analyzer is only ever scored on one combination per level, and
the other layouts are exercised only by hand-picked overrides.

Session 8 also left a known gap: in `syslog-server` lines the server timestamp
equals the device timestamp, which no real collector shows.

## Decision

1. For Medium, the four format knobs are drawn per scenario from the seed
   (sub-generator `formats`), with fixed weights:
   `log_collection` syslog-server 0.6 / device 0.4, `log_release` pre-22.2
   0.7 / 12.x 0.3, `hitcount_layout` standard 0.7 / legacy 0.3, `rescue_line`
   yes 0.5 / no 0.5. The draw is recorded in `manifest.json` (`format_draw`),
   and the effective values in `knobs`.
2. `log_release=22.2` is never drawn. Its attributes after `encrypted` are
   written `N/A`, an assumption no published line confirms, so it stays
   opt-in (`--knob log_release=22.2`).
3. A knob given as an override wins over the draw and is left out of
   `format_draw`. The draw is made for all four knobs anyway, so an override
   does not change the other draws.
4. With `log_collection=syslog-server`, Medium adds a clock skew between the
   syslog server and the device: one value per scenario, 1 to 6 seconds,
   either sign (sub-generator `clock-skew`), applied to the server timestamp
   only and recorded in the manifest (`syslog_clock_skew_seconds`).
5. Easy keeps its session 8 behavior: fixed formats and no skew, even with a
   `log_collection=syslog-server` override. Easy's evidence is meant to be
   complete and consistent, and this keeps every Easy output byte-identical,
   so the simulator version stays 0.2.0 (a bump would change the version
   string in every Easy file).

## Alternatives considered

- Keep fixed Medium formats (session 8): simplest, but scores would hide
  reader failures on the other layouts.
- Draw uniformly: the older layouts (12.x attributes, legacy hit counts) are
  less common on current devices, so they get the smaller weight.
- Draw `22.2` too: it would put an unconfirmed attribute list in the default
  evaluation set.
- Per-line jitter or drift on top of the constant skew: more realistic for a
  busy collector, but no sample shows its size; a constant offset is the
  smallest change that breaks the "same clock" assumption.
- Skew for Easy too: it would change Easy outputs that use the override and
  require a version bump.

## Consequences

- The analyzer must read every combination on Medium; the per-scenario mix is
  reported in the session 9 report (seeds 0 to 99).
- A reader that matches log lines to commits by exact time must allow a few
  seconds of offset between the server prefix and the device timestamp.
- The next change to Medium output needs a version bump, which will also
  change the version string of Easy files; per-level versions may be worth a
  later decision.

## Challenged by Nathan

Yes, twice, in the session 9 prompt: format variants drawn per scenario
instead of fixed Medium defaults, and a clock skew for syslog-server
collection. Outcome: both adopted as stated above.
