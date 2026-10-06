# 0032 Plan before the first release: hierarchical format, Hard level, real public configs

- Status: Accepted
- Date: 2026-10-06
- Supersedes: the "set format only" part of decision 0003 (v1 now also reads
  the hierarchical curly-brace format). The rest of decision 0003 stands.

## Context

After session 19, every v1 command exists (`ingest`, `explain`, `report`,
`questions`, `anonymize`, `demo`). palimp has only ever run on synthetic
scenarios from the simulator, with Junos formats confirmed by Juniper
documentation samples (decision 0013) and practitioner captures (decision
0015). Two gaps stay before a first public release:

- engineers who inherit a firewall usually hold the output of
  `show configuration`, which is hierarchical, not set format; asking them
  to convert first (decision 0003) loses annotations, which only the
  hierarchical format shows, and is a step many will not take;
- the evaluation has no scenario for several traps seen in real histories
  (renamed rules, reused addresses, scanner traffic, names that no longer
  match the rule).

## Decision

Work before release, in this order:

1. Read the hierarchical configuration format (as produced by
   `show configuration`) in addition to set format, with auto-detection.
   Both formats give the same internal model. `/* ... */` annotations
   become a new T1 evidence source.
2. Hard simulator level with four new traps: TRAP-RENAME-CHAIN,
   TRAP-IP-REUSE, TRAP-SCANNER-HITS, TRAP-STALE-NAME (simulator sessions).
3. Robustness on real public configurations (published examples and
   public repositories). They stay local only: never committed, never
   republished, not even anonymized.
4. An end-to-end test on a real vSRX is postponed until after the release
   (no budget for a paid lab). The README states plainly that palimp has
   never been run on a real SRX history, only on synthetic scenarios with
   formats confirmed by Juniper documentation and practitioner captures.
5. Release preparation, then the second held-out run (decision 0021).

The release is a 0.x beta, published when these five items are done and no
dangerous error (removal candidate on a live rule) appears on the held-out
run or on the real public configurations.

## Alternatives considered

- Release now with set format only: rejected, most inherited configs are
  hierarchical, and an untested real-world input path would be the first
  thing users hit.
- A paid vSRX or cloud SRX lab before release: rejected for budget. The
  limitation is stated in the README instead.
- Commit anonymized real public configs as fixtures: rejected, their
  licenses and the consent of their authors are unknown; they are used
  locally only.
- Release as 1.0: rejected, a tool never run on a real history should not
  claim a stable version.

## Consequences

- Decision 0003 no longer requires users to convert hierarchical configs.
- Anonymize must handle hierarchical files (verdict-identity test).
- Rollback files can be hierarchical; lineage and creation-commit
  detection must work on both formats.
- Simulator sessions get the Hard traps in the backlog; any ground truth
  schema change for them needs its own decision (decision 0017).
- The README gets a plain "never run on a real SRX history" statement.

## Challenged by Nathan

Yes, three challenges in the session 20 prompt, all adopted:

- test on real data before release: item 3 (real public configs, local
  only) and the release condition on dangerous errors;
- finish properly before publishing: the five items come before the
  release, and the release is a 0.x beta;
- no paid AWS lab before release: item 4 (vSRX test postponed, README
  states the limitation).
