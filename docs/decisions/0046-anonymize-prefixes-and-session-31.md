# 0046 Anonymize keeps kept-word prefixes; session 31 analyzer changes

- Status: Accepted
- Date: 2026-10-20 (session 31, analyzer)
- Supersedes: decision 0031, the limit "a kept signal word that starts a
  longer name no longer shares its prefix with it".
- Challenged by Nathan: yes (session 31 prompt): the anonymize failures on
  simulator 0.4.0 are privacy bugs, to be fixed in anonymize, never by
  weakening the tests; CI red on main is not acceptable (process rule added to
  `CLAUDE.md`).

## Context

Simulator 0.4.0 (decision 0045) draws realistic names: site codes, server
roles, people's workstations, hostnames such as `WEB-Servers-2`. Six
anonymize tests failed on it, in two ways:

1. Judgments changed after anonymizing (Medium and hierarchical seeds 7 and
   8). palimp reads a name segment as an abbreviation of a related CI when it
   is the start of exactly one (`web` of `webshop`, palimp.apps). Anonymize
   keeps signal words such as `web` (decision 0042) but replaced `webshop`
   letter by letter, so the copy lost the abbreviation: confidence dropped
   (HIGH to MEDIUM, MEDIUM to LOW), owners and intents moved. Decision 0031
   listed this as a known limit; with realistic names it is frequent.
2. "Original names left in the copy" (seed 2): the initials after `req`
   (`req GJ`) are mapped with the first-letter permutation, and `GJ` became
   `CI`, the name of a policy of the same configuration. Not a leak of `CI`
   itself, but a reader of the copy cannot tell it apart from one.

## Decision

1. A kept signal word of at least 3 letters (`web`, `sql`, `backup`) that is
   a whole run of a known name and the start of a longer replaced run of a
   known name stays at the start of that run's replacement: `webshop` becomes
   `web` plus 4 keyed letters. The rest of the run is permuted as before
   (each letter by a permutation keyed on the letters before it).
2. Replacement initials that equal an original known name (and are not
   themselves a replacement) count as a collision: the whole mapping is drawn
   again with the next salt, like the existing collisions with kept words.
3. A new test uses invented realistic names (site codes `PAR1` and `LYO2`,
   a workstation `PC-SLINDQVIST`, ticket numbers in policy names and
   descriptions, hostnames with a role and a site) and checks that no
   identifying run is left, that judgments are identical, and that the
   intents are the replaced names of the original intents. It fails on the
   anonymizer before this decision.

## Alternatives considered

- Replace signal words too when they start a longer name: rejected, palimp
  needs them (roles, decision 0042), and every judgment would move.
- Drop the abbreviation rule in palimp.apps: an analyzer change outside the
  mission, and it moves rules toward lower confidence on real names.
- Relax the test to tolerate collisions: rejected by the project lead
  (never weaken the tests).

## Consequences

- The copy reveals that a replaced name starts with a kept word, but only
  when that word is itself a name segment of the same artifacts (`web-01`
  next to `webshop`). README says so.
- Medium dev seeds 0 to 9, set and hierarchical: judgments identical, no
  original name left.

## Part B (session 31)

4. Two-letter names (extends decision 0044, project lead decision in the
   session 31 prompt): a commit comment and a ticket (summary or related CI)
   are sources that are not names, like a description: either one confirms
   a two-letter name an object or application name gives. The policy name
   still never does. Confidence only (LOW to MEDIUM), no verdict moves.
5. Review-4 fixes (`../palimp-realconfigs/review-4.md`):
   - a description or annotation made only of ticket references
     (`CR576958`) is not quoted as a stated purpose; the ticket look-up
     question already asks about it;
   - factory default evidence cites its real source: `trust-to-untrust` is
     the SRX210 factory default sample; the trust to trust pair is the SRX300
     factory default table (no name); `default-permit` is practitioner usage,
     in no Juniper sample;
   - a broad permit's intent says what it permits ("Permits all traffic from
     zone untrust to zone LAN"); broad permits from a zone named like the
     internet open the firewall team list, in their own section;
   - hosting platforms (`azure`, `aws`, `gcp`, `oci`) are where an
     application runs, never an application unless tickets.csv backs the
     name; anonymize keeps them like other signal words. A product written in
     two words in a custom application or application-set name
     (`MS-SQL-PORT-GROUP`) names the product (mssql);
   - an address-book object named like the keyword (`ANY`) is read by its
     contents: any only when it holds 0.0.0.0/0 or ::/0. The keyword itself
     is lowercase `any`;
   - deny and reject rules asked about go to the firewall team only (Ask
     line and a "Rules that block traffic" section of the team list), not to
     the owner of what they name.
   Direction: confidence and routing only. Broad permits and factory
   defaults are already at most verify. A rule using an object `ANY` that is
   not 0.0.0.0/0 is no longer read as catch-all deny (keep) or broad permit
   (verify): its verdict follows the usual rules (keep, verify, or
   removal_candidate only on a positive not-live signal, as for any rule).
