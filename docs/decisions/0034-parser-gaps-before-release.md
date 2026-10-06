# 0034 Parser gaps before release: deactivated scopes, global policies, application services

- Status: Accepted
- Date: 2026-10-06
- Supersedes: the "Reported, not applied" item of decision 0033 for
  `inactive:` on a zone pair, on `policies` or on `security` (the
  `apply-groups` part of that item stands)

## Context

Session 20 left four parser gaps open before release (decision 0032):

1. `inactive:` on a zone pair, on `security policies` or on `security`
   (set format: `deactivate security policies from-zone X to-zone Y`, and
   so on) was reported, and the policies under it were read as active.
   Marking them deactivated moves them toward `removal_candidate`, so
   decision 0033 left it to the project lead.
2. Global policies (`security policies global policy NAME ...`) were not
   read at all: such a rule was missing from every output.
3. `then permit application-services { ... }` (set:
   `then permit application-services application-firewall rule-set X`)
   left the action unset: the set reader only knew `then permit` as a leaf.
4. `apply-groups` stays a warning.

## Decision

- **Deactivated scopes** (approved by the project lead in the session 21
  prompt). Junos semantics: "When you deactivate a statement, that specific
  statement is ignored and is not applied at all when you issue a commit
  command" (Juniper, "Modify the Configuration of a Device", section
  "Deactivate and Reactivate Statements and Identifiers",
  https://www.juniper.net/documentation/us/en/software/junos/cli/topics/topic-map/modifying-configuration.html,
  release metadata junos 26.2, retrieved 2026-10-06), and the `deactivate`
  command reference: it adds the `inactive:` tag, "effectively commenting
  out the statement or identifier from the configuration"
  (https://www.juniper.net/documentation/us/en/software/junos/cli/topics/ref/command/deactivate.html,
  retrieved 2026-10-06). A deactivated container takes its whole subtree
  with it. So:
  - `deactivate security policies from-zone X to-zone Y` (hierarchical:
    `inactive: from-zone X to-zone Y { ... }`) deactivates every policy of
    that zone pair;
  - `deactivate security policies global` deactivates every global policy;
  - `deactivate security policies` and `deactivate security` deactivate
    every policy.
  The builder records the scope and applies it when the model is built,
  whatever the order of the lines. Each policy gets `deactivated = True`
  and the scope statement in `deactivated_statements`, so it follows the
  existing deactivated-rule path: T3 `deactivated` evidence, V-NOTLIVE
  unless traffic is seen (then V-CONTRADICTION, verify), and the question
  goes to the firewall team on the cleanup list (decision 0026), never to
  an application owner. `ingest` still prints a note naming the scope.
- **Global policies**, both formats. A global policy is read as a policy
  with zones `global`/`global` and the key `global/NAME` (`PolicyKey`
  prints and parses that form; Junos does not allow `global` as a
  from-zone, so the key cannot collide with a zone pair). Its
  `match from-zone` and `match to-zone` conditions are kept
  (`Policy.match_from_zones`, `match_to_zones`; empty means any zone, as
  `show security policies global` prints "From zones: any"). It goes
  through the same evidence and verdict pipeline. Two consequences:
  - session logs carry the real zones of each session, not `global`: the
    log summary of a global policy merges every summary with its name,
    except zone pairs where a zone policy has the same name. The counts
    are summed; distinct sources and destinations are a lower bound when
    the per-pair lists were capped.
  - no documentation sample shows how `show security policies hit-count`
    prints a global policy: the row is looked up under `global global
    NAME`; if none matches, the hit count item is blind (no use claimed
    either way).
  The rule text says "from any zone" or names the match zones; the
  internet-facing check (decision 0030) treats a global policy with no
  zone restriction as reaching a zone named like the internet when its
  addresses are open (safe direction: it ranks higher in Worth a look).
- **Application services.** `then permit application-services ...` sets
  the action to `permit` and records each attached service with its
  arguments (for example `application-firewall rule-set rs1`,
  `ssl-proxy profile-name ssl-profile-1`) in
  `Policy.application_services`. Each policy with services gets one T3
  evidence item (kind `application_services`, no application named), as
  structure an engineer chose for this rule. It does not change
  confidence (it names no application) or the verdict.
- **`apply-groups`** stays warn-only, both formats. Statements inherited
  from groups are missing from the model and `ingest` says so. Revisit
  after the real public configurations test (decision 0032 item 3):
  until real configurations show how groups are used on security
  policies, an expansion would be designed on guesses, and wildcards
  (`<*>`) with `apply-groups-except` make a partial expansion worse than a
  clear warning.

New fixtures (decision 0013), all copied from Juniper documentation pages
with source URL and retrieval date in the header:
`display_set_global_policies.txt`, `display_set_global_policy_zones.txt`,
`hier_global_policies.txt`, `hier_global_policy_zones.txt` (Global
Security Policies page), `display_set_application_services.txt`,
`hier_application_services.txt` (Application Firewall page). No
documentation sample shows a deactivated zone pair; the tests use inline
samples and say so.

## Alternatives considered

- Keep warning on deactivated scopes: rejected by the project lead. The
  policies really match nothing; reading them as active hides that from
  the cleanup list and can show a stale rule as live structure.
- Mark scope-deactivated policies with a separate evidence kind and a
  softer verdict: rejected, Junos makes no difference between a policy
  deactivated by itself and one under a deactivated zone pair.
- Read global policies as one policy per matched zone pair: rejected,
  Junos evaluates one rule; splitting it would multiply verdicts and
  questions for a single rule.
- Treat any `then permit <option>` (`tunnel`, `firewall-authentication`,
  `destination-address`) as permit: postponed, outside the stated mission
  and without documentation fixtures in this session. These still leave
  the action unset (listed in `HANDOFF.md`).

## Consequences

- Medium seeds 20 to 99: verdicts compared before and after (see session
  21 notes in `metrics/sessions.csv` and `HANDOFF.md`). The simulator
  writes none of these constructs, so no verdict is expected to change.
- On real configurations, rules under a deactivated zone pair now become
  removal candidates (unless traffic is seen) and appear on the firewall
  team cleanup list.
- Global policies now appear in every output; before this they were
  silently missing.

## Challenged by Nathan

Yes, in the session 21 prompt: global policies and the
application-services permit were raised as release blockers, and the
deactivated-scope behavior was approved. Outcome: all three implemented as
above; `apply-groups` kept warn-only on purpose.
