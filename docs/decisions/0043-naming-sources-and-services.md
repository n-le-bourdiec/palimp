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

All of these change confidence or the intent text, never a verdict.

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
