# 0042 Name filters, server roles and the corroboration rule

- Status: Accepted
- Date: 2026-10-13 (session 27, analyzer)
- Extends: decision 0022 (applications learned from names) and the
  `ROLE_WORDS` list of `palimp.apps`.
- Changes: the C-T3 confidence rule of decision 0020 (an application named by
  address objects alone was MEDIUM).
- Challenged by Nathan: yes (session 27 prompt, after reviewing the session
  26 real configuration sample). See below.

## Context

On 32 real public SRX configurations (session 26, decision 0032 item 3),
every application name came from address object names, since no tickets
were given. Real object names often start with a zone, a place, a person's
first name or a generic word: `addr-`, `en-`, `bad-`, `local-`, `dan-`.
palimp read those first segments as applications and gave MEDIUM confidence
to rules named after them (session 26: 76 of 157 MEDIUM rules named such a
word). Simulated object names always start with the application name, so the
dev metrics did not show it.

The project lead's challenge: generic words and person first names must not
become applications, policy names must be read, and `dynamic-application` must
be read.

## Decision

1. **Name filters.** A name learned from object names alone is never shorter
   than 3 letters, never a generic network word (`GENERIC_WORDS`, one
   documented list in `palimp.apps`, with a test), never a server role and
   never a word of a zone name of the configuration (`Security_52_Clients` in
   zone `Security_52`, seen on the real configurations).
   Names that tickets.csv backs (related CIs, their bare regional names,
   ticket short names, abbreviations of a related CI) are kept whatever their
   length or word: a ticket is an explicit source. The old `ROLE_WORDS` list
   stays filtered everywhere.
2. **Server roles.** `sql`, `db`, `web`, `jump`, `proxy`, `dns`, `mail`,
   `backup` and similar (`SERVER_ROLES`) say what a host does, not which
   application it serves. When no application is named, the intent describes
   the flow by the roles of each side and the well-known services matched
   ("SMB file sharing between SQL servers"), at LOW confidence.
3. **Corroboration rule.** An application taken only from names stays LOW
   (rule C-T3-SINGLE) unless a second independent source names it. Sources:
   the address objects of each side of the rule (both sides count as two),
   the policy name, a custom application name, a dynamic application. T1
   (description, annotation, commit comment, ticket) agreeing with the
   objects keeps its own rules (C-T1-T3-AGREE and following). This only
   lowers confidence and never changes a verdict. A policy name that repeats
   an address object name of the rule (`Hosted-Nets_to_X` with the object
   `Hosted-Nets`, separators and a trailing number aside) is not independent
   for what that object names: it is not counted (seen on the real
   configurations).
4. **New naming evidence.** The policy name is T3 evidence (`policy_name`)
   with the same filters. `match dynamic-application` is read (DYNAPP-1) as
   T3 evidence that names its application (`junos:SLACK` names `slack`); a
   dynamic application alone is one source, so LOW (open question for the
   project lead, session 27).
5. **Anonymize keeps the filtered words**, like it keeps role words
   (decision 0031), so an anonymized copy gives the same judgments.

Person first names are not listed: no list of names can be complete, and the
corroboration rule already keeps a name seen once at LOW.

## Alternatives considered

- A list of person first names. Rejected: incomplete by nature, and the
  corroboration rule covers the case without one.
- Keeping MEDIUM for object names and lowering only flagged words. Rejected:
  any unseen word would still pass; a second source is the general fix.
- Tuning the word lists against the simulator. Rejected (session 27 prompt):
  simulated names are not realistic; session 29 makes them so.

## Consequences

- Dev sets: see `docs/evaluation-history.md`, session 27. Verdicts do not
  move from the corroboration rule; the name filters can move a verdict only
  through a shared address no longer named after two applications.
- Fewer rules get a named intent on real configurations, and those named
  only once are LOW.
- The anonymize check counts only names holding a word palimp does not keep.
