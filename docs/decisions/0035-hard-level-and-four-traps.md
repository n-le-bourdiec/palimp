# 0035 Hard level: knobs, four new traps, drawn counts and format variants

- Status: Accepted
- Date: 2026-10-06
- Supersedes: the part of decision 0008 that keeps Hard for v2 (decision
  0032 item 2 already moved it before the release), and the spec 7.2 rule
  "every trap appears at least once in every Hard scenario". The rest of
  decision 0008 stands; Adversarial stays v2.

## Context

Decision 0032 item 2 asks for a Hard simulator level with four traps seen
in real histories: TRAP-RENAME-CHAIN, TRAP-IP-REUSE, TRAP-SCANNER-HITS and
TRAP-STALE-NAME. The session 22 prompt adds three constraints:

- Easy and Medium output stay byte-identical (golden hashes unchanged), so
  the second held-out run on Medium stays comparable with the first;
- trap counts are drawn per scenario as in decision 0018, with some
  scenarios holding none of a given trap;
- Hard draws two format variants per scenario (hierarchical configuration,
  global policies), using the documentation fixtures as the format
  reference, never `src/palimp`.

## Decision

1. **Level.** `levels.HARD` takes the spec 7.1 Hard column: 7 years, 60
   applications, 6 zones, every persona, comment rate 0.35, description rate
   0.2, log rate 0.35, 30 days of logs, hit counts reset 45 days before the
   snapshot, tickets 0.4 / 0.5, cleanup rate 0.3, 150 commits a year, two
   contractor periods. Values the spec leaves "not set yet" are simulator
   choices: 2 decommissions and 1.5 migrations a year, 40 access requests a
   year, health checks from the monitoring server for half the
   applications, Medium's format draws. The 60 applications are the 27
   templates plus regional instances (`erp-de`). `hard.HardSimulation`
   extends `MediumSimulation` through hooks that draw nothing in Medium.
2. **Drawn counts.** Trap producing knobs given as rates in the spec
   (copied comments 0.08, 4 emergencies a year, 6 rare jobs, `ip_reuse_rate`
   0.3, renames) become counts drawn per scenario
   (`levels.HARD_TRAP_COUNT_WEIGHTS`, zero possible), as decision 0018 did
   for Medium. Renames keep the spec rate (4 events a year); the drawn count
   is the number of them placed inside the retained history, where they can
   be seen. `cleanup_error_rate` stays 0: TRAP-CLEANUP-FLAP is not built.
3. **Four traps** (spec 7.5 has the mechanisms and measures):
   - TRAP-RENAME-CHAIN: the cleaner renames policies or server objects to a
     convention; old rollbacks and old log lines keep the old name.
     `name_history` records the chain; truth assumes the rename keeps the
     hit counter (VSRX-13).
   - TRAP-IP-REUSE: an application is retired and its users rule stays; a
     later application's server gets the freed address, and the admin, who
     finds the flow already open, writes no rule. Ground truth: `live`
     false (no flow it was made for), `still_needed` true, `hits_reason`
     `ip_reuse`, verdict and best `verify`, owner to ask the new
     application's owner.
   - TRAP-SCANNER-HITS: a retired application's rule stays and its only
     traffic is a weekly vulnerability scanner sweep from a user LAN, or a
     monitoring probe nobody removed. Ground truth: not live, `hits_reason`
     `scanner` or `monitoring`, verdict `removal_candidate`, best `verify`
     (45 days of counters, spec 7.4 rule). Scanner and probe flows never make
     a rule live. Any dead rule whose hits all come from them is tagged.
   - TRAP-STALE-NAME: an application is replaced by a successor product that
     takes over its servers' address objects (repoint style, spec 4.2). The
     rules keep the old names and descriptions. Ground truth: intent of the
     successor, live, verdict `keep`; the name, the objects, the
     description, the annotation and the go-live comment that name the old
     application are misleading.
4. **Format variants**, drawn per scenario from their own sub-generator
   (`formats-hard`) and recorded in `format_draw`: `config_format`
   (hierarchical 0.5) and `global_policies` (0.4). Hierarchical output
   follows the `hier_*.txt` fixtures; quoted strings have no sample
   (HIER-1d) and are tested as such. File names stay `config.set` and
   `rollback-NN.set`, so the ground truth schema does not change.
   Annotations show only in hierarchical files, and only there are they
   evidence.
5. **No version bump.** Hard is a new level: no Easy or Medium file
   changes, so the simulator stays 0.3.0 and every golden hash stays. Shared
   code changed only in ways that keep Easy and Medium bytes (checked on
   seeds 0 to 9 of both levels): faster configuration snapshots and address
   matching, session names and zones recorded at the time of the session,
   hooks. The first change to Hard output after this one needs a version
   bump, which changes the Easy and Medium hashes through the version
   string (decision 0018 accepted that).
6. **No ground truth schema change.** The schema already lists the `hard`
   level, the four trap ids, the `scanner`, `monitoring` and `ip_reuse` hit
   reasons, `object_rename`, and the contractor, cleaner and on-call
   personas. New in practice: `still_needed` can differ from `live`,
   `name_history` can hold several names, and global policies are keyed
   `global` / `global`.

## Alternatives considered

- Every trap in every Hard scenario (spec 7.2 as written): rejected by the
  session 22 prompt, for the reason of decision 0018 (an analyzer could rely
  on presence).
- A Hard-only version string, so Hard can change without moving the Easy
  and Medium hashes: more machinery; decision 0018 rejected per-level
  versions for the same reason.
- Distinct file names for hierarchical files (`config.conf`): the schema's
  `artifact` enum names `config.set`, so it would need a schema change and a
  decision 0017 note, for no evaluation gain.
- IP reuse where the new application also gets its own rule after the old
  one: the new rule is then shadowed, which is TRAP-SHADOWED-DUPLICATE, a
  trap not built yet.
- More application templates instead of regional instances: about 33 new
  templates of hand-written flows; regional instances reuse checked flows.
- Contractor broad rules (`any` application, /24 sources, spec 3): they
  would shadow later rules (TRAP-SHADOWED-DUPLICATE); contractors keep
  their naming, comments and description habits only.

## Consequences

- Hard scenarios take 6 to 10 s and 11 to 17 MB each on the development
  machine (spec 7.5), under the 30 s / 40 MB limit of the session 22 prompt.
- With 45 days of hit counts, no dead active rule of a Hard scenario can
  reach `removal_candidate` as best achievable verdict (spec 7.4 rule);
  only deactivated rules can.
- `levels.LEVELS` lists `hard`, so `palimp-sim generate --level hard` works,
  and so would `--holdout` with the held-out salt. The held-out set stays
  the project lead's call (decision 0021).
- The grounding of TRAP-STALE-NAME, TRAP-RENAME-CHAIN and TRAP-IP-REUSE is
  partial (spec 12.3).

## Challenged by Nathan

Not challenged when recorded. The session 22 prompt set the constraints
(byte-identical Easy and Medium, drawn counts with zeros, format variants,
the 30 s / 40 MB check), and they are applied as stated.
