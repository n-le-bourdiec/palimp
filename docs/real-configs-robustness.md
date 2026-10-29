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

## Session 27: intent quality after decision 0042

The project lead reviewed the 20 sampled rules: robustness approved, intent
quality not (generic words and person first names read as applications,
policy names ignored, `dynamic-application` not read). Decision 0042 adds
name filters (short, generic, server role and zone name words), server
roles, the corroboration rule, the policy name as T3 evidence and
`dynamic-application` as evidence naming the application.

Same 32 configurations, configuration alone, before (session 26 code) and
after (session 27 code):

| measure | before | after |
|---|---|---|
| MEDIUM rules | 157 | 17 |
| MEDIUM rules naming a generic word or a person-like token (session 27 classifier, below) | 102 | 0 |
| rules with a named intent (any level) | 157 | 91 |
| rules naming a person-like token (all LOW after) | 9 at MEDIUM | 15 at LOW |
| rules described by server roles, no application named | 0 | 19 |
| rules with `dynamic-application` | 21 (not read) | 21, 20 with a named intent |
| verdicts | 290 verify, 2 removal candidates | identical, rule by rule |

The session 26 count (76 of 157) used a hand classification; the session 27
classifier is a local script with a wider word list (zone names of the
configuration, words shorter than 3 letters, a generic word list and a list
of common first names), so it counts 102 on the same output. Both
classifiers run on the before and after output give the same direction.

Remaining doubts, visible in the new local review file (30 rules, stratified,
at most 3 any/any rules): a site prefix on both sides of a rule counts as
two sources (MEDIUM); a policy name is independent only when it does not
repeat an object name of the rule; person names on both sides of a rule
would be MEDIUM (not observed). Term-based custom applications (`term`
statements) show as "protocol unknown": a parser gap, not changed.

## Session 28: second pass on intent quality (decision 0043)

The project lead reviewed `review-2.md` and approved decision 0042, then
asked for decision 0043: a conflict never sets the intent, the cleanup
question in the assessment, product and application names as name sources,
address objects counted once, a dynamic application alone MEDIUM,
predefined applications, product ports, server roles matching the service,
two-letter names only when confirmed, flows described without an
application, `term` applications read, and the name/service contradiction.

Same 32 configurations, configuration alone, before (session 27 code,
`a5f4b8c`) and after (session 28 code), counted by one local script on both:

| measure | before | after |
|---|---|---|
| MEDIUM rules | 17 | 57 |
| of which C-T3 (two sources) / C-DYNAMIC-APP | 15 / 0 | 35 / 20 |
| MEDIUM rules naming a generic, short or person-like word (session 27 classifier) | 0 | 8 |
| rules with a named intent (any level) | 91 | 107 |
| rules naming a person-like word (all LOW) | 12 | 8 |
| rules with a flow described, no application named | 19 | 54 |
| rules with "Purpose unknown" | 182 | 131 |
| name/service contradictions | not read | 7 (`ALLOW-SNMP` to `ALLOW-SNMP-6`, all on `junos-https`) |
| shared address / shared source items | 0 / 4 | 5 / 4 |
| deactivated rules with the cleanup question | 0 of 2 | 2 of 2 |
| verdicts | 290 verify, 2 removal candidates | identical, rule by rule |

The 8 flagged MEDIUM rules are all two-letter names confirmed by a policy
name and an object that start with the same code (`LT-Gates-Paxton`,
`FG-MB-AIRCON`, `FG_Server_EG_Camera`, `AZURE-MS-SQL`): the rule as asked
(two sources), but the codes look like site or team prefixes, a question for
the project lead. The 20 C-DYNAMIC-APP rules are the `unified-*` rules of one
configuration. Person-like words drop from 12 to 8 because a shared source
no longer adds the other object's name to the intent. A new local review
file `../palimp-realconfigs/review-3.md` holds 30 rules: the six rules the
session 28 prompt names (review-2 rules 1, 2, 3 and 7, `ALLOW-SNMP`, the
`BARCLAY` prefix rule), then the same strata as review 2.

## Session 29: rule semantics and review-3 fixes (decision 0044)

The project lead reviewed `review-3.md` and approved decision 0043, then
asked for decision 0044: confirmed names only in the intent, two-letter names
never confirmed by the policy name, `dc` out of the server roles and `ad` read
only on LDAP or Kerberos, the name/service flag only when no object carries
the service word, an Ask line that never says "the team that runs any",
several conflicts in one clause, and rule semantics: deny and reject rules,
catch-all deny (cleanup) rules, Junos factory default policies, broad
permits, quoted stated purpose, ticket look-up in the question.

Same 32 configurations, configuration alone, before (session 28 code,
`65acdfe`) and after (session 29 code), counted by one local script on both:

| measure | before | after |
|---|---|---|
| MEDIUM / LOW rules | 57 / 235 | 92 / 200 |
| C-T3 rules (two sources) | 35 | 28 |
| rules with a named intent (any level) | 107 | 103 |
| rules with "Purpose unknown" | 131 | 88 |
| Ask lines "the team that runs any" | 128 | 0 |
| deny or reject rules | 16 | 16 |
| of which catch-all deny, keep (V-CLEANUP-RULE) | 0 | 9 |
| of which asked "Is this block still wanted?" | 0 | 7 |
| factory default policies (V-FACTORY-DEFAULT) | not read | 33, in 21 configurations (`default-permit` 25, `trust-to-untrust` 8) |
| broad permits (V-BROAD-PERMIT) | not read | 58 |
| intents quoting a stated purpose | 0 | 15 |
| questions citing a ticket to look up | 0 | 21 |
| intents summarizing several conflicts | 0 | 2 |
| name/service contradictions | 7 | 7 (`ALLOW-SNMP` rules, objects carry no service word) |
| verdicts | 290 verify, 2 removal candidates | 281 verify, 9 keep, 2 removal candidates (the same two, both deactivated) |

Every verdict move is verify to keep, all 9 on active catch-all deny rules
(cleanup rules, a deny never opens a flow). `FG-MB-AIRCON` is LOW (the policy
name no longer confirms `mb`), and its Ask line names `MB-Air-Con`, not the
person names of its sources. A new local review file
`../palimp-realconfigs/review-4.md` holds 30 rules: the seven rules the
session 29 prompt names, then the same strata plus 6 deny or reject rules,
3 factory defaults and 2 broad permits.

## Session 31: review-4 fixes, shadowed rules, deny tuning (decision 0046)

Same 32 configurations, configuration alone, before (`a15ad34`, session 30
analyzer plus the anonymize fix) and after (`2b31281`), compared rule by rule
by one local script on both:

| measure | before | after |
|---|---|---|
| verdicts | 281 verify, 9 keep, 2 removal candidates | identical, rule by rule (0 moves) |
| MEDIUM / LOW rules | 92 / 200 | 94 / 198 |
| rules with "Purpose unknown" | 88 | 30 (58 broad permits now say what they permit) |
| intents quoting a stated purpose | 15 | 5 (10 descriptions were a ticket reference alone, `CR576958`, `CHG0114306`) |
| hosting platform as the intent application (`azure`) | 12 | 0 |
| deny or reject rules asked of the firewall team | 0 | 7 |
| deny rules MEDIUM by their block (C-BLOCK) | 0 | 6 |
| shadowed rules | not read | 1 (`c24 global-snmp-45`, after `global-default-deny-50`; verdict unchanged, verify) |
| Ask lines to the firewall team | 93 | 100 |

Confidence moves: 6 LOW to MEDIUM (deny rules, C-BLOCK), 4 MEDIUM to LOW
(c29 `ON-PREM-to-AZURE-*` rules: `azure` no longer counts, the remaining
`git` name has one source). `ON-PREM-to-AZURE-MS-SQL-CHG0092653` now names
mssql from its application group `MS-SQL-PORT-GROUP`.

## Session 33: active deny keep, endpoints, site prefixes, database roles (decision 0048)

Same 32 configurations, configuration alone, before (`61b4d91`, session
start, simulator 0.5.0 merged) and after (`1c672ae`), compared rule by rule
by one local script on both (a rule counts as "purpose unknown" here when it
names no application and describes no flow; the session 31 count used
another script):

| measure | before | after |
|---|---|---|
| verdicts | 281 verify, 9 keep, 2 removal candidates | 274 verify, 16 keep, 2 removal candidates |
| MEDIUM / LOW rules | 94 / 198 | 85 / 207 |
| rules naming an application | 103 | 94 |
| rules with no application and no flow | 121 | 121 |
| Ask lines to the firewall team | 100 | 100 |

Verdict moves, rule by rule: 7, all verify to keep on active deny rules
with no visibility (`V-NO-VISIBILITY` to `V-DENY-BLIND`, item 2 of decision
0048), still asked of the firewall team at low priority. No other verdict
moves; the two removal candidates are unchanged.

Intent moves (10 rules): 7 rules no longer name `smtp` or `mssql` from a
mail or database server role and its port (now LOW, the flow described);
`support` is no longer an application (`*-AZURE-SUPPORT-TOOL`, 2 rules); the
misspelled city `Glaswgow` is read as a site prefix (1 rule). Confidence
moves: 9 MEDIUM to LOW, none up.
