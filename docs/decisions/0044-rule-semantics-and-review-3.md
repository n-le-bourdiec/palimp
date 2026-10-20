# 0044 Rule semantics (deny, cleanup, factory default, broad permit) and review-3 fixes

- Status: Accepted
- Date: 2026-10-20 (session 29, analyzer)
- Supersedes: decision 0043 item 9, the part where the policy name may
  confirm a two-letter name, and the part where `ad` leaves the server roles;
  decision 0043 item 11 is narrowed (see item 4 below).
- Extends: decision 0020 (verdict and confidence rules), decision 0026
  (firewall team list), decision 0028 (untrusted free text).
- Challenged by Nathan: yes (session 29 prompt, after reviewing
  `../palimp-realconfigs/review-3.md`, 4 challenges): unconfirmed names listed
  at MEDIUM (`FG-MB-AIRCON`), `dc` read as a domain controller, the Ask line
  "the team that runs any", and deny rules treated like permits. Decision 0043
  was approved in the same prompt.

## Context

The project lead's review of 30 real rules after decision 0043 found that a
confirmed two-letter name pulled every unconfirmed name of the rule into the
intent, that a policy name confirms a prefix the objects share (one naming
convention), that `dc` means data center at least as often as domain
controller, that the Ask line could say "ask the team that runs any", and that
several conflicts made the intent sentence unreadable. Real configurations
also showed rule semantics palimp ignored: deny and reject rules, catch-all
deny rules, Junos factory default policies, broad permits, free text purpose
statements and ticket numbers used as policy names.

## Decision

Part A (review-3):

1. **Confirmed names only.** When at least one application is named by two
   sources (C-T3), the applications only one source names leave the intent.
2. **Two-letter names** need a source that is not a name: a well-known port,
   a dynamic application, a custom application or application-set name, or a
   description or annotation. The policy name never confirms them (it follows
   the naming convention of the objects) and the policy name item no longer
   lists them. Names of 3 letters or more keep the policy name as a source.
3. **"At most verify"** (decision 0043 item 11): keep becomes verify; a
   removal candidate stays one. The session 28 reading is confirmed.
4. **Name and service mismatch** is flagged only when no address object of
   the rule carries the service word as a token: `to-bank-sftp` with the
   object `bank-sftp` names a host; `ALLOW-SNMP` on junos-https still flags.
5. **Server roles.** `dc` is no longer a role. `ad` is a conditional role
   (`CONDITIONAL_ROLES`): read as a directory server only when the rule matches
   LDAP or Kerberos (`tcp/88` and `udp/88` join `PORT_NAMES` as `kerberos`), so
   it then names that service, like a `dns` object on udp/53. Anonymize keeps
   `ad`.
6. **Two-letter names in not-live signals: no**, not before release. Known
   limit: the 2 Medium V-CONTRADICTION rules whose decommission names `ci`
   stay at keep (session 28).
7. **Ask line.** With no owner and no confirmed application, the team that
   runs the destination objects, else the source objects, else the firewall
   team; never "the team that runs any". An application only one source names
   is never listed as an owner (Ask line, report group).
8. **Several conflicts** are summarized in one clause of the intent sentence
   ("Conflicts: 4 shared addresses, see E4 to E7."); one conflict is still
   stated in full. The detail stays in the evidence.

Part B (rule semantics, `palimp.semantics`):

9. **Deny and reject rules.** The intent says what is blocked ("Blocks FTP
   from anywhere in zone untrust to the 192.168.1.0/24 network"), the question
   is "Is this block still wanted?". An active deny with a not-live signal is
   verify (V-DENY-NOTLIVE), never removal_candidate: removing a deny opens
   traffic. A deactivated deny follows the usual rules.
10. **Catch-all deny** (any source, any destination, any application, zone
    pair or global): a cleanup rule, intent says so, verdict keep
    (V-CLEANUP-RULE), confidence MEDIUM (C-CLEANUP, structure alone).
11. **Stated purpose.** Description and annotation text is quoted in the
    intent sentence as a claim ("Stated purpose, a claim palimp does not
    check: the description says ..."), brackets and quote marks neutralized,
    never raising confidence, and left out of the LLM fallback text (free text
    licenses no fact, decision 0028).
12. **Broad permits** (any source, any destination, any application): a T3
    `broad_permit` item, listed in the firewall team list ("Broad permits"),
    verdict at most verify: keep, V-NO-TRAFFIC-SEEN and V-NO-VISIBILITY become
    V-BROAD-PERMIT, asked of the firewall team only. More specific verify
    rules (V-TEMPORARY-IN-USE, V-TAKEOVER-IN-USE and the others) keep their
    rule and their owners, the rule is still listed for the team.
13. **Junos factory default policies**: the any/any/any permit named
    `trust-to-untrust` from trust to untrust (SRX210 factory default sample,
    FACTORY-1, fixture `hier_factory_default_srx210.txt`), or `default-permit`
    from trust to untrust or trust to trust (FACTORY-2 table, FACTORY-3
    practitioner name, unverified). Intent "Junos factory default policy",
    confidence MEDIUM (C-FACTORY-DEFAULT), verdict verify (V-FACTORY-DEFAULT)
    under the same rule as item 12, question to the firewall team "Was this
    factory default kept on purpose?".
14. **Ticket references not found** in tickets.csv, policy names included:
    the question starts with "Look up CHG0142136 in your change system: it
    may say why this rule exists."

## Alternatives considered

- Catch-all deny at HIGH confidence: the structure leaves little doubt, but
  no traffic or direct source confirms it; MEDIUM keeps calibration safe.
- Deny rules asked of the firewall team only: not asked in the prompt; deny
  rules keep the owner routing, a question for the project lead.
- `ad` as a plain role: rejected, `AD-` may be a site or a team prefix.
- `default-permit` recognized on any zone pair: rejected, only the two pairs
  the documentation lists.

## Consequences

- Verdicts move toward verify (broad permits, factory defaults, deny rules
  with not-live signals) and toward keep only for active catch-all deny
  rules (V-CLEANUP-RULE), which carry no traffic risk: a deny never opens a
  flow. No move toward removal_candidate.
- Dev set and real configuration numbers: `docs/evaluation-history.md`
  (session 29) and `docs/real-configs-robustness.md`.
