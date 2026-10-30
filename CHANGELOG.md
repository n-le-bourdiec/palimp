# Changelog

All notable changes to palimp. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/) (0.x: the command line and the
report format may still change).

## [Unreleased]

## [0.1.0] - not released yet (release candidate)

First public version, a beta: palimp has never been run on a real SRX
history (see Known limits in the README).

### Added

- Juniper SRX security policies, zone and global, read from the
  configuration in set or hierarchical format (auto-detected, saved terminal
  sessions accepted), with rollback files, commit history, hit counts, RT_FLOW
  session logs and an optional ticket or CMDB CSV export.
- Evidence in four tiers (direct, behavioral, structural, contextual), a
  confidence level from the tiers present and their agreement, a verdict
  (keep, verify, removal candidate) and the question to ask, per rule. A
  removal candidate always rests on a positive not-live sign, never on
  missing traffic alone.
- Commands: `ingest`, `explain`, `report` (Markdown and JSON, with a "What
  palimp could not see" section), `questions` (one email per person, one per
  zone pair for rules with no owner name, a firewall team cleanup list and an
  answer CSV), `anonymize` (keyed, consistent pseudonymization, optional
  `--strip-text` and `--shift-dates`) and `demo` (a bundled synthetic
  scenario and its report).
- An experimental LLM writer, off by default (`--llm`), local Ollama only:
  every sentence must cite evidence or it is replaced by the deterministic
  text.
- Fully offline: no network egress, no telemetry, no update check.

### Evaluation

- Dev numbers on simulator 0.5.1 (Medium seeds 20-99, Hard seeds 20-49):
  verdict equal to the best achievable 91.7% and 98.1%, no removal candidate
  on a live or still needed rule (naive baseline: 191 and 148), intent right
  vs best achievable 82.1% and 78.6%, HIGH confidence intent right 96.7% and
  95.6%. Held-out run pending.
