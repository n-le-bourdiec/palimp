# 0048 Intent scored against what the artifacts allow; every active deny is keep; endpoints and site prefixes

- Status: Accepted
- Date: 2026-10-29 (session 33, analyzer)
- Supersedes: decision 0044 item 9, the part "an active deny with a not-live
  signal is verify (V-DENY-NOTLIVE)"; decision 0046 item 7, the part "rules
  with no visibility at all stay verify"; decision 0042, the part "person
  names stay possible applications at LOW" for workstation objects; decision
  0043 item 8, narrowed to services that are applications of their own.
- Extends: decision 0047 (best achievable intent and rule kind in the ground
  truth), decision 0036 (Hard table in the held-out workflow).
- Challenged by Nathan: yes (session 33 prompt, 1 challenge): a hidden stale
  name is scored against the name the artifacts show (the replaced
  application of decision 0047), not against null. The session 32 open
  question is closed that way.

## Context

Simulator 0.5.0 (decision 0047) gives every rule `expected.rule_kind` and
`expected.best_achievable_intent`. The evaluation scored intent only against
the true application (`intent.app_id`), so "purpose unknown" on a rule
nothing names was counted wrong, and firewall team rules carried the pseudo
application `firewall`.

Session 31 asked the project lead whether an active deny with no visibility
at all should be keep too (decision 0046 kept it verify).

## Decision

1. **Intent scoring (`eval/verdicts.py`).**
   - Application rules (`rule_kind` application): right when palimp's first
     named application is `best_achievable_intent`. When it is null, palimp
     is right when it names no application ("Purpose unknown", or a flow
     description with no application). palimp must also read the rule as an
     application rule (not as a cleanup, block, broad permit or factory
     default).
   - Firewall team rules: `rule_kind` against palimp's own reading of the
     rule, in the order of the report's intent sentence: catch-all deny
     evidence gives cleanup, then factory default, then broad permit, then a
     deny or reject action gives block.
   - Hidden stale names (85 Hard rules): `best_achievable_intent` is the
     name the artifacts show; confidence stays scored against
     `best_achievable_confidence`. No special case in the script.
   - The old number stays in the output, labeled "vs true application".
   - A summary table gives, for all rules, each rule kind,
     TRAP-SHADOWED-BY-DENY and rules with an `ANY` source (a source object
     named `ANY` or `Any-Hosts`, never the `any` keyword): verdict vs best,
     intent vs best achievable, intent vs true application, overconfidence,
     underconfidence, dangerous errors of palimp and of the naive baseline.
2. **Every active deny or reject rule is keep**, with or without visibility,
   whatever its signals (project lead's answer to the session 31 question).
   Removing a block opens the traffic it blocks; keeping it opens nothing.
   The verdict rule says what the artifacts show: `V-DENY-NOTLIVE` (a
   not-live signal, was verify), `V-DENY-TRAFFIC` (traffic reaches it, was
   `V-TRAFFIC` or a traffic verify rule), `V-DENY-QUIET` (no traffic seen,
   unchanged), `V-DENY-BLIND` (no visibility, was `V-NO-VISIBILITY` verify).
   The rule comes right after `V-CLEANUP-RULE`, before every other verdict
   rule. A deactivated deny follows the usual rules. A deny placed after a
   catch-all deny stays keep (`V-SHADOWED` applies to other rules only).
3. **The question stays, at low priority.** `V-DENY-NOTLIVE` and
   `V-DENY-BLIND` rules stay in the firewall team list ("Is this block still
   wanted?"), in its last section, titled "Rules that block traffic (low
   priority)". The report entry carries the question; the assessment's
   question stays empty (a keep is never asked of an owner).

4. **Endpoints name no application** (tuned on Medium 0-19 and Hard 0-19).
   An address object whose name holds a workstation or remote access word
   (`pc`, `lt`, `laptop`, `nb`, `notebook`, `desktop`, `wks`, `ws`, `vpn`,
   `remote`, `support`), unless a ticket backs that word as an application,
   is a person's machine or an outside party's access: `greta-jansen-pc-5`,
   `LT-Oskar-Gallo`, `Calder-Systems-VPN`. Its first segment is not learned
   and it names no application. Policy names are not endpoints (they may name
   the application next to `remote`). No person name list (decision 0042
   stands on that): the rule reads the role word, not the name.
5. **Site prefixes are not applications.** A first segment no ticket backs
   is a site when the objects it starts go on with the names of two
   applications tickets.csv knows (`GRT-ERP-APP01`, `GRT-LMS-WEB01`), with at
   least 6 distinct server roles (`OKV-DB01`, `OKV-NS01`, `OKV-SMTP01`, ...),
   or with a word for where users sit (`MRD-Users`, `DNX-LAN`,
   `brv_clients`). It is not learned. Anonymize keeps the words of items 4
   and 5 (as it keeps role words, decision 0042 item 5), so an anonymized
   copy gives the same judgments.
6. **A database engine or a file, backup or mail transfer protocol on a
   matching server role names no application** (`ROLE_SERVICES` keeps DNS,
   NTP, proxy, directory, RADIUS, log, monitoring and FTP). `srv-db-01` on
   tcp/1433 says SQL Server, not which application uses it: the intent
   describes the flow and names none, LOW (C-WEAK). On the tuning seeds the
   old rule was right for dns, ntp and vault (services that are applications
   here) and wrong for mssql, postgresql, oracle, mysql, smb, ndmp and smtp.
7. **Verdicts do not move with items 4 and 5.** Positive not-live signals and
   shared addresses keep the reading of names before session 33
   (`vocabulary(places=False)`), like regional instances (session 24): read
   with the new rules, a decommission of `crm-it` matched `DNX-CRMIT-APP01`
   once `dnx` was a site (3 Hard and 2 Medium tuning rules toward
   removal_candidate), and `RZ-TMS-APP01` no longer named a second
   application for a shared address (17 TRAP-IP-REUSE rules toward keep).
   Moving the not-live reading needs the project lead's approval.

## Alternatives considered

- Keep `V-NO-VISIBILITY` verify on deny rules (decision 0046): the project
  lead answered keep.
- Drop the deny question entirely: the project lead asked to keep it at low
  priority.
- List every active deny in the firewall team list: rules with traffic on
  them or no traffic seen give no reason to ask; the list would grow with
  every block.
- Score intent with the evaluation's own reading of "purpose unknown" when
  `best_achievable_intent` is absent (ground truth before 0.5.0): the script
  falls back to `intent.app_id` there, as before.

- Use the new name reading for not-live signals too: it moves rules toward
  removal_candidate (item 7); needs approval.
- Lower C-T1-ONLY (a T1 alone naming the application) to LOW: on Medium
  0-19, 149 such rules have a best achievable confidence of HIGH and 197 of
  LOW; no single level fits, left for a later session.
- A person name list: rejected in decision 0042, still rejected.

## Consequences

- Verdicts move only toward keep: verify to keep on active deny rules.
  Items 4 to 6 move intent and confidence only.
- Medium overconfidence rises on the tuning seeds (7.2% to 9.7%): with the
  person name gone, a rule whose T1 names the application no longer
  conflicts with its objects and gets MEDIUM (C-T1-ONLY), where the ground
  truth often says LOW. Hard overconfidence falls (7.4% to 5.3%).
- Intent numbers are not comparable with those recorded before session 33;
  the old number is still printed next to the new one.
