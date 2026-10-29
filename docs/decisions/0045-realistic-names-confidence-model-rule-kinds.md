# 0045 Realistic names, naming source confidence and firewall team rules in the simulator

- Status: Accepted; item 3, the pseudo application `firewall` as the scored
  intent of firewall team rules, superseded by decision 0047
- Date: 2026-10-20 (session 30, simulator)
- Supersedes: the Medium and Hard part of the `max_justified_confidence`
  rule of spec section 6 (tiers of the sound evidence: T1 and T2 give HIGH,
  T1 or T3 MEDIUM). Easy keeps it. Decision 0040 stands:
  `best_achievable_confidence` is still computed like
  `max_justified_confidence`, with masked evidence read as sound.
- Schema change under decision 0017 (additive, `schema_version` stays 1).
- Challenged by Nathan: yes (session 30 prompt, 1 challenge): the tests on 32
  real public SRX configurations showed that the simulator is too clean.
  Simulated object names always start with the application name, and
  scenarios hold no deny rules, broad permits or factory defaults.

## Context

Analyzer sessions 27 to 29 (decisions 0042 to 0044) changed how palimp reads
names: generic words, person names and server roles name no application, a
name seen once gives LOW, two independent sources give MEDIUM, two-letter
names need a source that is not a name, and deny, catch-all deny, broad
permit and factory default rules have their own semantics. The dev sets could
not measure any of it: simulated objects name the application on both sides
of every rule, and no simulated rule denies anything. The ground truth still
computed `max_justified_confidence` from evidence tiers, so underconfidence
on the dev sets was 57% to 68% (session 28): the ceiling said MEDIUM or HIGH
where the project lead's own model says LOW.

## Decision

1. **Realistic names, Medium and Hard** (spec 2.5, `naming.py`). Drawn per
   scenario from a new `naming` sub-generator: site codes of 2 or 3 letters,
   server role hostnames (`EG-SQL01`, `SQL01`, `srv-sql-01`), workstations
   named after people, generic objects (`main`, `local`, `Hosted-Networks`),
   and objects named after the application for a share of the applications
   only (drawn per scenario between 0.25 and 0.6). Senior and operator
   policy names are drawn among their own name, an application name, a
   zone-to-zone name, a ticket number (`CHG...`, or a `RITM...` number no
   export holds) and a name built from an object name; their descriptions are
   kept, replaced by a ticket number, or replaced by free text. Automation,
   contractor, on-call, cleaner and global policy names keep their templates,
   so the trap mechanics do not change.
2. **Confidence from naming sources, Medium and Hard** (spec 6.1,
   `sources.py`). `max_justified_confidence` counts the sources the generator
   wrote that name the true application: the address objects (both sides,
   one source), the policy name when it does not repeat an object name, a
   service whose port stands for the application, the description or
   annotation, the retained creation comment, and an exported ticket the rule
   cites. A two-letter name counts only next to a source that is not a name.
   One source gives LOW, two MEDIUM, and HIGH needs two sources, one of them
   a direct statement, plus traffic seen. The rules come from the project
   lead's decisions, stated as simulator rules; the analyzer code is not read.
3. **Firewall team rules, Medium and Hard** (spec 4.11, `rulekinds.py`), from
   a new `rule-kinds` sub-generator: specific deny or reject rules (insecure
   services between zones, a hostile outside range), some deactivated later;
   catch-all deny rules at the end of some zone pairs; broad permits
   (any/any/any); Junos factory default policies when the zones are named
   `trust` and `untrust` (`trust-to-untrust` alone as in the SRX210 sample, or
   `default-permit` on trust to trust and trust to untrust). Expected values:

   | Kind | Verdict | Best achievable | Confidence |
   |---|---|---|---|
   | specific deny or reject, active | keep | keep | MEDIUM |
   | specific deny, deactivated | removal_candidate | removal_candidate | MEDIUM |
   | catch-all deny | keep | keep | MEDIUM |
   | broad permit | verify when it carries traffic, else removal_candidate | verify | LOW |
   | factory default | verify when it carries traffic, else removal_candidate | verify | MEDIUM |

   Owner to ask: `firewall_team`. Intent `app_id`: `firewall`, a pseudo
   application listed in `apps` whenever a scenario has such a rule.
4. **Schema** (additive): intent kinds `block`, `cleanup_deny`,
   `broad_permit`, `factory_default`; event kind `security_rule`; hits reason
   `blocked`. `owner_to_ask` may be `firewall_team`.
5. **Version** 0.4.0. Easy artifacts stay byte-identical; Easy
   `ground_truth.json` and `manifest.json` change only by the version string
   (test `test_easy_changed_only_by_version`). Medium and Hard numbers before
   and after 0.4.0 are not comparable (`docs/evaluation-history.md`).

## Alternatives considered

- Keep tier-based confidence and add names only: the ceiling would stay
  above the project lead's model, and underconfidence would keep measuring
  the simulator, not palimp. Rejected by the mission.
- Read the analyzer's word lists to build the names: forbidden by the
  independence rule, and it would make the simulator agree with the analyzer
  by construction. The names come from the real configuration aggregates and
  the decisions only.
- A per-rule naming source count in the ground truth: useful for analysis,
  but not needed by the evaluation; the distributions are computed by a
  script (session 30 report). Not added, to keep the schema change small.
- Deny rules with logging (`RT_FLOW_SESSION_DENY`): the published template
  has no captured line; left out until a sample exists.
- Deny rules owned by the application they protect (`deny-dmz-to-crm-db`):
  the block belongs to whoever decided it; all firewall team rules are owned
  by `firewall_team`.

## Consequences

- Medium and Hard dev metrics after 0.4.0 are not comparable with earlier
  runs; the next analyzer session measures the effect.
- Analyzer sessions must accept the new enum values and `firewall_team`
  (HANDOFF note).
- Trap mechanics are unchanged, but trap counts move: fewer objects name the
  replaced application (TRAP-STALE-NAME), the rule kinds add
  TRAP-DEACTIVATED and TRAP-HISTORY-HORIZON rules. The stored Hard trap
  counts are regenerated.
- New unverified format shapes: `then reject` without a profile (syntax only)
  and `Deny` in the hit count Action column (the documentation sample shows
  `Permit` and `Reject`).
