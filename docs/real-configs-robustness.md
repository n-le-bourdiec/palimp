# Robustness on real public configurations (decision 0032 item 3)

Session 26 (2026-10-13). Aggregate numbers only: the configurations, their
sources and the per-config results stay in a local folder outside the
repository, never committed and never republished. Every line holding a
secret (passwords, keys, SNMP communities, certificates and similar) was
removed before a file was saved, and a check found none left.

## Corpus

- 142 configurations with security policies collected from public GitHub
  repositories (code search), deduplicated; 32 selected that look like device
  output (homelabs, lab repositories, automation backups, tool test captures
  of real devices). Configuration-auditor samples, generated templates and
  hand-written test fixtures were left out.
- 25 hierarchical, 7 set (as palimp detects them); several are saved
  terminal sessions, 6 of them holding both `show configuration` and
  `| display set` output in one file.
- Junos 10.x to 24.x, plus vSRX build-date versions and 2 without a version
  line.
- 30 to 1807 statements per configuration (median 165), 1 to 99 policies
  (median 3), 292 policies in all.
- Configuration alone: no commits, rollbacks, logs, hit counts or tickets.

## Results

| measure | result |
|---|---|
| crashes (`ingest`, `report`, `questions`) | 0 of 32 |
| ingest + report time per configuration | median 0.8 s, max 0.9 s |
| policies found vs an independent count of policy statements | 292 vs 292, all 32 equal |
| unknown statements | 719 of 8646 (8.3%): 697 in one file that is a notes page, not a configuration; 22 of 7771 (0.28%) in the other 31; 23 configurations with none |
| descriptions on policies | 12 policies, in 1 configuration (independent count equal) |
| annotations on policies | 3 policies, in 1 configuration (checked by hand: multi-line notes) |
| deactivated policies | 2 |
| `apply-groups` | 4 configurations; none inherits security policies, address books or applications (groups hold cluster node settings, system, interfaces, IKE and IPsec) |
| verdicts | 290 verify (V-NO-VISIBILITY), 2 removal_candidate (both deactivated) |
| confidence | 135 LOW, 157 MEDIUM, 0 HIGH |
| invariant: removal_candidate only on deactivated rules or positive not-live signals | holds (0 violations) |
| invariant: no HIGH without traffic seen | holds (0 HIGH) |

Before the session 26 fixes: 7882 statements counted, 725 unknown, one
mismatch reported by the independent count (a bug of the counter, not of
palimp). The fixes below mostly split statements that were glued together:
the statement count rose to 8646 while the unknown count fell.

## Fixed in session 26

1. An `application-set` listed inside an `application-set` (a Junos
   construct) was unknown.
2. A hierarchical capture holding `| display set` output too: a `set` line
   outside any block was glued to the next statement until a semicolon, so
   one unknown statement hid hundreds of lines. CLI answers to a mistyped
   command (`^` marker, `syntax error`) and prompts with no host name were
   glued the same way; they are now terminal noise.
3. Security policies of logical systems and tenant systems were unknown
   lines with no explanation. They are stated (ingest warning), and the
   report lists configuration palimp does not read (`apply-groups`, those
   systems, statements not understood) under What palimp could not see:
   12 of the 32 reports show it.

## Still unsupported

- Security policies of logical systems and tenant systems (stated, not
  read; out of v1 scope).
- `delete:` tags of load files (1 configuration, 3 statements).
- `//` comments (1 configuration).
- Output of operational commands inside a capture (2 configurations).
- A command echoed with no prompt (3 configurations, 1 statement each).
- A hand-edited copy missing a `;` (1 configuration).
- A set file with a hierarchical part (not observed; the reverse is read).
- `apply-groups` not expanded (decision 0034; no inherited policy or object
  observed).

## Quality finding (not changed)

Without tickets, every application name comes from address object names.
On real configurations those names are often zone, role, location or
placeholder words: 76 of the 157 MEDIUM rules name such a word as their
application (for example the equivalents of `addr`, `main`, `dmz`, `remote`,
`internal`, `prod`, `client-a`). On synthetic scenarios object names follow
an application convention, so this did not show. Not changed in session 26:
extending the role word list changes intent output and needs a dev set
check and the project lead's approval. A local file with 20 sampled rules
is ready for review.
