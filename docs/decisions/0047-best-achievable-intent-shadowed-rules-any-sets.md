# 0047 Best achievable intent, rule kind, shadowed rules and ANY sets in the simulator

- Status: Accepted; the confidence model it relies on (decision 0045 item 2)
  amended by decision 0049 for `best_achievable_confidence`;
  `best_achievable_intent` unchanged
- Date: 2026-10-20 (session 32, simulator)
- Supersedes: the part of decision 0045 item 3 that makes the pseudo
  application `firewall` the intent of the firewall team rules for scoring.
  `firewall` stays where the schema needs a string (item 2 below).
- Schema change under decision 0017 (additive, `schema_version` stays 1).
- Challenged by Nathan: yes (session 32 prompt, 1 challenge): intent was
  scored against an answer nobody can know. On simulator 0.4.0, intent
  accuracy reads 44% (Medium) and 40% (Hard) because about a third of the
  application rules have no naming source at all, and firewall team rules
  carry the pseudo application `firewall`. palimp was scored wrong for
  answering "purpose unknown" when nothing could tell the application.

## Context

Verdicts already have two expected values: `verdict` (full knowledge) and
`best_achievable_verdict` (what the artifacts support). Confidence has
`max_justified_confidence` and, in Hard, `best_achievable_confidence`
(decision 0040). Intent had only `intent.app_id`, the true application,
even when no object, name, service, description, comment or ticket that
the generator wrote names it (33.4% of Medium and 36.9% of Hard application
rules, spec 7.6). Firewall team rules (decision 0045) have no application at
all; `firewall` was a placeholder that palimp can never print.

Session 31 (decision 0046) also listed two simulator backlog items, at low
frequency: rules placed after a catch-all deny (shadowed), and an address
object named like the `any` keyword that holds specific addresses.

## Decision

1. **`expected.best_achievable_intent`** (every rule, every level): the
   application a perfect analyzer can name from the artifacts.
   - Application rules: the rule's application when at least one naming
     source of spec 6.1 names it, counted with the spec 6.1 rules (a
     two-letter name alone does not count). One source is enough: the
     intent is right or wrong, how sure palimp may be is the separate
     confidence field. `null` when no source names it: "purpose unknown" is
     then the right answer.
   - Hard, TRAP-STALE-NAME that no artifact reveals (decision 0040): when no
     source names the true application but sources name the replaced one,
     the replaced application, as `best_achievable_confidence` already does.
     85 Hard rules on seeds 0 to 49.
   - Firewall team rules (`block`, `cleanup_deny`, `broad_permit`,
     `factory_default`): always `null`. Their intent is the kind of rule,
     read from its structure.
2. **`expected.rule_kind`** (every rule): `application`, or the firewall
   team kind (`block`, `cleanup_deny`, `broad_permit`, `factory_default`,
   equal to `intent.kind`). An evaluator scores intent on
   `best_achievable_intent` for application rules and on `rule_kind` for
   the others.
   - The pseudo application `firewall` is kept only where the schema needs
     a string: `intent.app_id` (required string), `flows[].app_id` (every
     flow belongs to an application) and the `apps` entry those two refer
     to. It never appears in `rule_kind` or `best_achievable_intent`.
     Making `intent.app_id` nullable would break the required field that
     analyzer sessions already read; it is not done.
3. **Schema** (additive): both fields are optional in the schema (an older
   ground truth stays valid) and always written from simulator 0.5.0; trap
   id `TRAP-SHADOWED-BY-DENY`.
4. **Shadowed rules, Medium and Hard** (spec 4.11, `rulekinds.py`, own
   sub-generator `shadowed`). Junos appends a new policy at the end of its
   zone pair; an admin who forgets `insert policy ... before` leaves it
   after the catch-all deny, where it never matches. Per scenario 0, 1 or 2
   (weights Medium 0.7, 0.25, 0.05; Hard 0.5, 0.35, 0.15), 20 to 400 days
   after a catch-all deny from the users zone or the internet to the
   servers, DMZ or management zone: a senior admin or the operator adds an
   access rule for a new workstation or vendor address to a live
   application tier, after the deny. Its flow keeps trying and hits the
   deny. The rule is protected from hit count cleanups, migrations and
   replacements end its flow without moving it, and application events
   (decommission, migration cleanup, renames, copied comments) leave it
   alone, so no other draw moves. Ground truth: intent is the application
   (best achievable intent as item 1), `live` false, `still_needed` true
   while its flow still runs and no permit carries it, `verdict` verify
   (removal_candidate once its flow has ended), `best_achievable_verdict`
   verify, owner `firewall_team` (only the firewall team can move it),
   evidence `policy X after catch-all deny Y` (T3, not_live), trap
   `TRAP-SHADOWED-BY-DENY`. palimp marking it removal_candidate while it is
   still needed counts as the most severe error (decision 0038).
5. **`ANY` address sets, Medium and Hard** (spec 2.5, `medium.py`, own
   sub-generator `any-object`). In 20% of Medium and 30% of Hard scenarios,
   an address set named `ANY` or `Any-Hosts` holds the user site subnets
   (the same members as the set of every site), and 1 to 3 rules of a
   senior admin or the operator use it as source in place of that set. The
   traffic does not change. It names no application (generic object). It
   tests that palimp does not read the name as the `any` keyword (decision
   0046 item 5).
6. **Version** 0.5.0. Easy artifacts stay byte-identical; Easy
   `ground_truth.json` changes only by the version string and the two new
   fields (test `test_easy_changed_only_by_version`, now checked against
   0.3.0 and 0.4.0). On Medium 0 to 99 and Hard 0 to 49, every 0.4.0 rule
   keeps its expected values, owner, traps and intent; in 6 scenarios some
   names take another uniqueness suffix (`-2` to `-3`). The 0.4.0 numbers
   were never published (no release, no held-out run on 0.4.0); 0.5.0 is
   the release basis.

## Alternatives considered

- Let the evaluation side decide that "purpose unknown" is right when the
  analyzer finds no source: the evaluation would then judge with the
  analyzer's own reading. The simulator knows what it wrote; the expected
  answer belongs in the ground truth, like `best_achievable_verdict`.
- Strict reading of the prompt for hidden stale names (`null` when no
  source names the true application): palimp would be scored wrong for
  naming the application the artifacts show, while decision 0040 already
  makes that application the apparent one for confidence. Kept consistent
  with 0040; flagged to the project lead.
- `best_achievable_intent` as an object with an intent kind: intent kinds
  of application rules are not scored today; the kind of a firewall team
  rule is `rule_kind`. Kept to one nullable string.
- Shadowed rules with a removal_candidate best verdict: the project lead
  asked for verify, and removal on a rule a still-running flow wants is the
  most severe error.
- A shadowed rule that duplicates a working rule above the deny
  (TRAP-SHADOWED-DUPLICATE, spec 7.3): a different case (the rule is
  redundant, not broken), left in the backlog.
- An `ANY` object on deny rules: no catch-all look-alike deny is generated
  yet; application permits come first (the real configuration case of
  decision 0046).

## Consequences

- Analyzer sessions: the evaluation can score intent against
  `best_achievable_intent` and `rule_kind`; old scoring on `intent.app_id`
  still works but keeps counting unknowable answers as wrong (HANDOFF note).
- `V-SHADOWED` (decision 0046) gets simulated cases: 10 Medium rules in 8
  of 100 scenarios, 21 Hard rules in 14 of 50.
- Retained history shifts by one commit per shadowed rule (more
  TRAP-HISTORY-HORIZON tags in 10 Hard seeds); stored Hard trap counts
  regenerated.
- Medium and Hard dev metrics on 0.5.0 are comparable with 0.4.0 rule by
  rule, except the new rules and the renamed ones.
