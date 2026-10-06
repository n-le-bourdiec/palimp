# 0033 Hierarchical reader: one model builder, annotations as T1, unsupported constructs reported

- Status: Accepted
- Date: 2026-10-06
- Supersedes: nothing (implements item 1 of decision 0032)

## Context

Decision 0032 adds the hierarchical (curly-brace) Junos format to v1. The
two formats must give the same internal model, and the hierarchical format
carries one thing set output does not: annotations (`/* ... */`, written
with `annotate`, HIER-1c). Some hierarchical constructs change what the
configuration means in ways palimp cannot reproduce safely.

## Decision

- One model builder. The hierarchical reader
  (`palimp.formats.junos_hier`) walks the text into the statements
  `display set` would print (full path, one per leaf, `[ a b ]` lists
  expanded, `deactivate` after an `inactive:` subtree, as VSRX-2a shows)
  and feeds the builder of the set reader. `palimp.formats.junos_config`
  detects the format per file by a vote of the statement lines.
- Same file names. `config.set` and `rollbacks/rollback-NN.set` hold either
  format; evidence locators keep saying `config.set`.
- Terminal captures: output of `show X Y` in configuration mode, or of
  `show configuration X Y`, is read relative to `X Y` (the documentation
  samples are all of this kind); `[edit X]` banners add `X`.
- Annotations: a `/* ... */` on its own line(s) annotates the next
  statement. One on the same line after a statement, or followed by a
  closing brace, is dropped, as the documentation says Junos drops it. An
  annotation on a policy, or on a statement inside one, is kept on the
  policy and becomes a T1 evidence item (kind `annotation`), treated like
  the description everywhere: intent kind for confidence, ticket
  references, initials after `req`, temporary words, untrusted free text
  in LLM validation (decision 0028), free text in `anonymize`.
  Annotations elsewhere (zone pairs, objects, other hierarchies) are not
  used.
- Reported, not applied:
  - `apply-groups` (both formats): statements inherited from configuration
    groups are missing from the model; `ingest` warns, the README points to
    `| display inheritance`.
  - `inactive:` on a zone pair (`from-zone X to-zone Y`), on `policies` or
    on `security` (both formats): the policies under it are read as active
    and `ingest` warns. Marking them deactivated would move them toward
    `removal_candidate`, which needs the project lead's approval (working
    rule 2).
- `protect:` and `replace:` prefixes are dropped; `#` starts a comment
  outside quoted strings.

## Alternatives considered

- Convert hierarchical text to set lines and reuse `parse_set` unchanged:
  rejected, annotations and line numbers would be lost, and quoting would
  have to be rebuilt.
- A separate model builder for the hierarchical format: rejected, two
  builders drift apart; the round-trip test would only catch it on the
  constructs the simulator writes.
- Accept `config.conf` or `.txt` names: postponed, every evidence locator
  says `config.set`; the README tells users to save either format under
  that name.
- Expand `apply-groups`: rejected for v1, wildcards (`<*>`) and
  `apply-groups-except` make a partial expansion worse than a warning.

## Consequences

- Medium dev seeds 0 to 9 rendered as hierarchical text give identical
  model, creation commits, verdicts, confidence and owners
  (`tests/test_hier_roundtrip.py`), and identical judgments after
  `anonymize` (`tests/test_anonymize.py`).
- No verdict changes on set-format input. `apply-groups` lines and
  deactivated zone pairs in set format are now ignored with a warning
  instead of counted as unknown; `attach` and `description` under an
  address book are ignored instead of unknown.
- Open: no documentation sample shows `inactive:`, an annotation or a
  description on a security policy (HIER-1b to HIER-1d stay partly
  unverified until real configurations are read, decision 0032 item 3).

## Challenged by Nathan

Not yet. The deactivated zone pair choice is listed as a question for the
project lead in `HANDOFF.md`.
