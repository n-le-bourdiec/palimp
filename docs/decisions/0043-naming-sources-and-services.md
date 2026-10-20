# 0043 Naming sources, products and services (second pass on intent quality)

- Status: Accepted
- Date: 2026-10-20 (session 28, analyzer)
- Supersedes: decision 0042 item 3, the part that counts the address objects
  of each side of a rule as two sources, and decision 0042 item 4, the part
  that gives a dynamic application alone LOW.
- Extends: decision 0042 (name filters), decision 0026 (questions routed to
  the firewall team).
- Challenged by Nathan: yes (session 28 prompt, after reviewing
  `../palimp-realconfigs/review-2.md`): person names set by a shared source,
  the lost deactivated question, `redis` lost as if it were a role. The two
  open questions of session 27 were answered in the same prompt.

## Context

The project lead's review of 30 real rules after decision 0042 found three
bugs and answered two questions:

- A shared source conflict added the other object's name to the intent
  ("Probably for craig").
- Deactivated rules showed "Can this policy be removed?" instead of the
  cleanup question of decision 0026.
- `DMZ-WITNESS-REDIS-PFS` (application set `REDIS`, zone `REDIS-DMZ-PRIV`)
  named nothing: `redis` was filtered as a zone name word, and application
  set names were not learned.
- A dynamic application states what the rule matches: MEDIUM alone.
- The same prefix on both sides of a rule (`BARCLAY-HQ` to `BARCLAY-US`) is
  one naming convention, not two sources.

## Decision

1. **A conflict never defines the application.** The applications named by
   a shared address or shared source item are cited in the conflict, never
   added to the intent.
2. **The assessment carries the cleanup question.** A deactivated rule not
   kept gets "Is this deactivated rule kept on purpose, as a rollback
   switch?" and the firewall team ask in the assessment itself, so `explain`,
   the report and the questionnaires agree. The cause: the session 27 review
   script printed the assessment question, which had never been the cleanup
   question; the report was right.
3. **Product names.** `PRODUCTS` in `palimp.apps` (redis, nessus, oracle,
   sap, mysql, mssql and similar): a product names an application in any
   object, policy or application name, even when a zone name holds the same
   word. A product is never a server role (`mysql` and `mssql` leave
   `SERVER_ROLES`). Free text is read as before: a commit comment that
   mentions `ansible` is about the tool. Anonymize keeps product names.
4. **Application names as a name source.** The first segment of custom
   application and application-set names is learned like that of address
   object names, with the same filters; `tcp`, `udp`, `port` and similar are
   generic words.
5. **Address objects count once.** Both sides of a rule together are one
   source (supersedes decision 0042 item 3 on this point). Two sources need
   two different kinds: the address objects, the policy name, a custom
   application or application-set name, and (item 7) a well-known port.
6. **Dynamic application alone: MEDIUM** (rule C-DYNAMIC-APP), never HIGH
   without traffic: it is the rule's own match criterion, not a name chosen
   by a person.
7. **Predefined applications and product ports.** `palimp.services.PREDEFINED`
   holds the Junos predefined applications of the documentation (VSRX-12d).
   `PORT_NAMES` maps a well-known port to the product or service it stands
   for (`tcp/8834` nessus, `tcp/3128` proxy, `udp/53` dns). A port alone never
   names the application of a rule (T4). A port known for a product, plus a
   name naming that product, counts as two sources.
8. **A server role that matches the service** (`ROLE_SERVICES`: a `dns`
   object on udp/53, an `ntp` object on udp/123, a database object on
   tcp/1521) counts as two sources and names that service (or product) as
   the application.
9. **Two-letter names** (`bi`, `hr`, `ad`): the first segment of an object or
   application name, when it is not a generic word, a role or a zone word, is
   kept as a two-letter name (`Vocabulary.short`). It names an application
   only when two sources name it (for example the address objects and the
   policy name), never alone. `ad` leaves `SERVER_ROLES` for this. The
   not-live readers (decommissions, migration leftovers) do not use these
   names: a two-letter name never moves a rule toward removal.
10. **A flow described without an application.** When nothing names an
    application, the intent describes the flow from the services matched,
    the server roles, where the hosts sit (`PLACES`: management, user, DMZ,
    guest, VPN, partner, vendor) or the zones ("SNMP traps from the
    management range to anywhere in zone b"). Confidence stays LOW (C-WEAK).
    "Purpose unknown" remains only when neither a service nor a role is known.
11. **Name and service contradiction.** When the policy name names a service
    (`NAME_FAMILIES`: snmp, ssh, rdp, dns, ntp and similar) that none of the
    matched applications offers (`FAMILY_PORTS`), a T3
    `name_service_mismatch` item is a conflict (HIGH becomes MEDIUM,
    C-NAME-SERVICE), and the question "is the name stale, or does the rule
    match the wrong application?" goes to the firewall team list. With
    traffic seen, the verdict is verify (V-NAME-SERVICE) instead of keep,
    and the owners are not asked. Other verdicts are unchanged: a removal
    candidate stays one (its not-live signal does not depend on the name).
    `any`, `junos-defaults` and ports in no family are never compared.

Items 1 to 10 change confidence or the intent text, never a verdict. Item 11
moves keep to verify only.

## Alternatives considered

- Keep both sides as two sources and detect only identical prefixes.
  Rejected by the project lead: one naming convention whatever the suffix.
- Products in free text too. Rejected: tool names in commit comments
  (`ansible`, `jenkins`) would conflict with the objects of the rule.

## Consequences

- More rules at LOW on the dev sets (simulated objects often name the
  application on both sides), see `docs/evaluation-history.md`, session 28.
- The product list is incomplete by nature; a product it lacks is read like
  any other name.
