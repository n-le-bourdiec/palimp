# 0031 palimp anonymize: keyed, consistent, structure-preserving replacements

- Status: Accepted
- Date: 2026-10-06

## Context

Users who hit a palimp bug need to share their artifacts in a public issue,
and those artifacts hold internal addresses, host and application names,
people and ticket numbers. The copy must stay analyzable: palimp learns
applications and abbreviations from names (decision 0022), reads signal words
(temporary, decommission, role words, ticket prefixes), matches log addresses
to address objects and tells public from private addresses (decision 0030).
A copy that changes the analysis does not reproduce the bug.

## Decision

`palimp anonymize -a DIR -o OUT --key KEYFILE [--strip-text] [--shift-dates]
[--mapping]` writes a copy of the files palimp reads (`config.set`,
`commits.txt`, `hitcount.txt`, `tickets.csv`, `logs/rt_flow.log`,
`rollbacks/rollback-NN.set`) plus `ANONYMIZED.txt`. Any other file is not
copied. All replacements come from HMAC-SHA256 with the key (32 random bytes
in hexadecimal, created if KEYFILE does not exist):

- IP addresses: bit i is flipped by a keyed bit of the first i bits
  (Crypto-PAn style, so prefix-preserving), except at a node of the address
  tree that holds a private or reserved range of `palimp.addresses` below it.
  Such bits are kept, so an address stays in its range, and a public address
  stays public. In logs, `/N` after an address is a port and is kept.
- Names: each run of letters and each run of digits is replaced character by
  character, each by a keyed permutation of the alphabet that depends on the
  run's preceding characters. Length, case, separators and shared prefixes
  are kept, so `mon` stays the start of `monitoring` and palimp still learns
  abbreviations. One-letter runs, `junos-*` names, `any`, and words palimp
  reads as signals (role words, temporary words and their `tmep` typos,
  ticket prefixes, decommission words, `requested by`) are kept. Person
  names, logins and object names share one mapping, so `req JL` initials are
  replaced with the initials of the replaced name.
- Free text (descriptions, commit comments, ticket summaries): known names,
  letter runs of known names, IP addresses, ticket IDs, e-mail addresses,
  initials after `req` and upper-case short names are replaced; other words
  are kept. Commit types and revisions are kept. `--strip-text` removes
  description lines, commit comments and ticket summaries.
- Configuration lines palimp does not read (system, SNMP, ...) are replaced
  word by word, except Junos keywords, numbers and interface names.
- Dates are kept. `--shift-dates` moves every date (ISO, commit stamps,
  syslog `Mar  4` stamps, ticket dates) back by a keyed number of whole weeks
  between 1 and 520, so weekdays and times of day stay.
- If a replacement word equals a kept signal word or a word left in free text
  (where palimp would then read a name), the whole mapping is drawn again
  with the next salt. The result stays deterministic: the same key and input
  give byte-identical output.
- The key and the optional `OUT.PRIVATE-mapping.json` must be outside OUT;
  the command refuses an existing OUT and a key inside OUT or the artifacts.
  Neither is needed to analyze the copy.

## Alternatives considered

- Random tokens per name (`name-0001`): rejected, it loses the shared
  prefixes and the signal words palimp needs, and needs a stored table to be
  consistent across runs.
- Crypto-PAn on the whole IPv4 space: rejected, a private address could
  become public and change the internet-facing ranking (decision 0030).
- Format-preserving encryption of every token, no kept words: rejected,
  `temp`, `users`, `CHG` and `decom` carry the evidence of many verdicts.
- Drop free text by default: rejected, descriptions and comments are the T1
  evidence; `--strip-text` is the cautious option.
- Shift dates by any number of days: rejected, weekdays feed the recurrence
  hints of the behavior evidence.

## Consequences

- Tested on Medium dev seeds 0 to 9: verdicts, confidence and owner
  certainty identical on the copy, no original name, person, ticket ID or
  address left in it (a value can only reappear as another value's
  replacement); with `--shift-dates` on seed 0, judgments identical too.
- Limits, said in the README: this is keyed pseudonymization, not
  encryption. Replacements keep length and prefixes, and short words go
  through few permutations, so someone who knows the network may recognize
  parts of it. A name palimp does not know (a person named only in a
  comment) stays in free text. Public addresses near a reserved range keep
  more leading bits. A kept signal word that starts a longer name
  (`test`, `testlab`) no longer shares its prefix with it, which can lose an
  abbreviation. Dates in free text are shifted only in ISO form.
- `palimp.addresses` is shared by the report (decision 0030) and the
  anonymizer.

## Challenged by Nathan

Mission set by the project lead in the session 19 prompt. Not challenged.
