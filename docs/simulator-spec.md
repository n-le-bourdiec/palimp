# Simulator specification

Status: draft, session 2 (2026-09-28). Spec only, no code yet.

The simulator generates a fictional company's firewall history and the artifacts
an engineer would find when inheriting that firewall, plus a ground truth file
that records the true intent of every rule. palimp is scored against that
ground truth (decision 0005).

Format assumptions that must be checked against a real vSRX before the parser
relies on them are tagged **[VSRX-n]** and listed in the last section.

## 1. Goals and non-goals

Goals:

- Produce artifacts that look like real Junos output, so the palimp parser is
  exercised on realistic input.
- Produce histories where the reason behind each rule is known, including cases
  where the evidence is missing, misleading or contradictory.
- Make every scenario reproducible from a seed and a difficulty level.
- Offer difficulty knobs, so accuracy can be tracked from easy to adversarial.

Non-goals:

- Being a network simulator. No packets, no routing, no NAT behavior beyond what
  is needed to write plausible log lines.
- Covering other vendors, or Junos features outside the v1 scope (decision 0003).
- Sharing any code with palimp (section 10).

## 2. Company model

The simulator first builds a fictional company, then plays a timeline of events
against it. The company state at any date is fully known to the simulator.

The default company is "Fennmoor Logistics", a fictional mid-size company. All
host names use the reserved `.example` domain. Internal addresses come from
RFC 1918 ranges; internet addresses come only from the RFC 5737 documentation
ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24), so no generated address
belongs to anyone real.

### 2.1 Zones

A zone has a name, one or more subnets, an interface (for example `ge-0/0/3.0`)
and a role.

| Role | Typical name variants | Content |
|---|---|---|
| internet | `untrust`, `internet`, `outside` | RFC 5737 hosts: SaaS, update servers, partners' public IPs |
| users | `trust`, `users`, `lan` | office workstations, subnets per site |
| servers | `servers`, `dc`, `prod` | application servers |
| dmz | `dmz` | reverse proxies, mail relay, public web |
| management | `mgmt`, `admin` | jump hosts, monitoring, backup, config tools |
| partners | `partners`, `b2b` | site to site VPN peers |
| restricted | `pci`, `secure` | payment or HR systems, only on medium and above |

The zone naming style is picked once per scenario (a real firewall rarely mixes
styles, but see the contractor period in section 4).

### 2.2 Servers

| Field | Meaning |
|---|---|
| `server_id` | stable internal id, never shown in artifacts |
| `hostname` | for example `crm-db-01`, style depends on the era |
| `ip` | may change over time (migration) |
| `zone` | may change over time (migration) |
| `role` | web, app, db, file, auth, dns, ntp, smtp, monitoring, backup, jump, proxy |
| `app_id` | owning application, or `shared` for infrastructure |
| `active_from`, `active_to` | lifecycle; `active_to` empty while in service |

An IP address freed by a decommission may be reused by a new server later
(knob `ip_reuse_rate`).

### 2.3 Applications

| Field | Meaning |
|---|---|
| `app_id`, `name` | for example `crm`, "Customer CRM" |
| `owner_id` | a person (section 2.4); may change over time |
| `tiers` | subset of web, app, db |
| `servers` | per tier, list of `server_id` |
| `consumers` | who uses it: users zones, partners, internet, other apps |
| `dependencies` | shared services it needs: auth, dns, ntp, smtp, file, other apps |
| `services` | ports and protocols per flow; some standard (`junos-https`), some custom (tcp/8443) |
| `jobs` | scheduled flows: nightly backup, monthly batch, quarterly or yearly export |
| `go_live`, `retired` | lifecycle dates |
| `criticality` | low, medium, high; drives emergency events |

Each application yields a set of **flows**: (source set, destination set,
service, schedule, volume). A flow is the unit of intent. A rule may carry one
flow, several flows, or none.

Shared services (DNS, NTP, SMTP relay, AD, monitoring, backup, jump hosts) are
modeled as applications with `app_id` `shared-<service>`.

### 2.4 Owners

A person has `person_id`, name (from a fixed fictional name list), team,
`joined`, `left`. Owners appear in tickets and CMDB rows, never in the Junos
config itself. When an owner leaves, their applications are reassigned or
become orphaned (knob `orphan_rate`). palimp's "question to ask the rule owner"
is scored against the current owner, or against "orphaned" when there is none.

## 3. Admin personas

Every config change is made by an admin. Admins are instances of personas. A
persona fixes the admin's habits; each admin draws concrete values from the
persona ranges with the scenario seed.

| Persona | Tenure | Commit comment | Policy names | Other habits |
|---|---|---|---|---|
| Meticulous senior | years | usually present, often with ticket id (`CHG0012345`) | descriptive: `users-to-crm-web-https` | sets `description`, enables `log session-close`, deletes what it replaces |
| Hurried operator | 1 to 3 years | often empty or vague: `fix`, `update`, `as requested` | numbered or ad hoc: `rule-47`, `allow-new` | batches unrelated changes into one commit, rarely logs |
| Contractor | 3 to 12 months | own style, sometimes another language style (`MEP projet X`), or none | own convention: `CTR_P012`, `TMP_ACCESS_FOO` | broad rules (`any` application, /24 sources), no cleanup when leaving |
| Automation account | whole period after introduction | templated: `managed by ansible, run 1832` | templated: `app-crm-web-01` | commits `via netconf`, very regular times, consistent objects |
| On-call responder | overlaps others | `urgent`, `incident`, `INC0045678`, or none | `temp-fix`, `emergency-allow`, `test` | commits at night or week-ends, broad rules at the top of the list, never removed |
| Cleaner | short bursts | `cleanup`, `remove unused` | renames to a new convention | deactivates rather than deletes, renames objects, sometimes removes a live rule |

Persona parameters (all ranges, drawn per admin):

- `comment_rate`: probability a commit has a comment.
- `comment_quality`: distribution over ticket reference, meaningful sentence,
  vague word, empty, misleading (describes another change).
- `naming_style`: descriptive, numbered, ticket-based, templated, contractor
  prefix, ad hoc.
- `description_rate`: probability a new policy gets a `description`.
- `log_rate`: probability a new policy gets `then log session-init` and/or
  `session-close`.
- `breadth`: tendency to use `any`, wide subnets and application sets.
- `batch_size`: number of unrelated changes grouped in one commit.
- `cleanup_rate`: probability of removing rules made obsolete by own changes.
- `working_hours`: distribution of commit times (office hours, nights, fixed
  automation schedule).
- `login`: personal account (`jdoe`), shared account (`admin`, `root`) or
  service account (`svc-ansible`). Shared accounts hide the persona.
- `tenure`: `joined` and `left` dates.

## 4. Timeline and events

A scenario covers `years` of history (knob). Time advances day by day. Each day
the scheduler may fire events according to per-event rates and preconditions.
Each event produces three kinds of effects:

1. **Config changes**, grouped into one or more commits, each commit with an
   admin, a timestamp, a login, a client (`cli` or `netconf`) and a comment.
2. **Traffic changes**: flows start, stop, move or change volume from a date.
3. **Side records**: tickets, CMDB updates, owner changes.

Every event and every change gets an internal id recorded in the ground truth,
so each rule's history is traceable.

### 4.1 New application (`new_app`)

- Company: creates the application, its servers, owner and flows.
- Config: address objects for the new servers (zone address book or global
  address book, per era), custom application objects when a port is not a
  predefined `junos-*` application, one policy per flow or per group of flows
  (grouping depends on persona), placed at the end of the zone pair list or
  inserted before a catch-all.
- Commits: one to several; may be spread over days; comment per persona; the
  ticket id may appear in the comment, the policy name or the description.
- Traffic: flows start at `go_live`, which can be days or weeks after the
  commit (pre-provisioned rules with zero hits).
- Tickets: a change ticket with probability `ticket_rate`.

### 4.2 Migration (`migration`)

A server or a whole application moves to a new IP, a new zone, or both.

- Config, one of three styles (drawn):
  - repoint: the address object keeps its name, its value changes;
  - duplicate: new objects and new policies are added, old ones are left
    (removed later with probability `cleanup_rate`);
  - bridge: temporary policies allow old and new servers to talk during the
    cutover, then may or may not be removed.
- Traffic: shifts from old to new addresses on the cutover date.
- Ground truth: old rules become dead, or stay live if the old IP is reused.

### 4.3 Decommission (`decommission`)

- Company: the application is retired, servers are powered off, IPs freed.
- Config: rules and objects removed with probability `cleanup_rate`, otherwise
  kept. Partial removal is common (web rules removed, db rules forgotten).
- Traffic: stops, except leftovers: monitoring still probing, scanners, and
  clients still configured with the old address (short tail of denied sessions).

### 4.4 Emergency rule (`emergency_rule`)

- Trigger: incident on a high criticality application.
- Config: by an on-call responder, broad rule (wide subnet, `any` application,
  or both), inserted at the top of the zone pair, often without logging.
- Commits: at night or on week-ends, comment `urgent` or incident id or none.
  May use `commit confirmed` **[VSRX-4]**.
- Traffic: the rule starts matching flows that other rules already allowed
  (first match wins), so it can look heavily used while being redundant, or it
  can become the only rule carrying a flow if the proper rule is later deleted
  (load-bearing temporary rule).
- Ground truth: intent `emergency_temporary`, with the flow it was really for.

### 4.5 Partial cleanup (`partial_cleanup`)

- By a cleaner or a senior admin, over one or several commits.
- Config: removes a fraction of dead rules; deactivates others (`deactivate`
  statements stay in the config **[VSRX-2]**); removes unused objects; renames
  rules to a new convention.
- Mistakes (knob `cleanup_error_rate`): removes a live rule (traffic starts
  being denied, a ticket may follow, the rule is re-added days later with a new
  name).
- Hit counts may be cleared as part of the cleanup (section 5.5).

### 4.6 Object rename (`object_rename`)

- Config: an address object, application or policy gets a new name (Junos
  `rename` command). References follow.
- History: old rollback files contain the old name; the diff between two
  rollbacks shows a delete and an add, not a rename **[VSRX-5]**.
- Ground truth: records the name chain, so palimp can be scored on linking them.

### 4.7 Contractor period (`contractor_period`)

- A contractor admin is active for a few months on a project (often a new app
  or a migration).
- Config: contractor naming, broad rules, little commenting, may use the shared
  `admin` login, may introduce a second zone or object naming style.
- After leaving: their rules persist; some become dead, some are load-bearing.

### 4.8 Background events

- Routine commits without policy changes (system, interfaces, users). They fill
  the commit history and push old commits out of the retention window.
- Reboots and upgrades: reset hit counts **[VSRX-7]**.
- Monitoring and vulnerability scanners: periodic traffic touching many rules
  (hits that do not reflect business use).
- Owner changes, team reorganizations.
- Log rotation: only the last `log_window_days` of logs survive.

### 4.9 Traffic model

Each flow has a schedule: continuous business hours, 24x7, nightly, weekly,
monthly, quarterly, yearly. For each day and flow the simulator computes a
session count. Sessions are attributed to a policy by evaluating the config in
force that day: zone pair, then first matching policy in order, then the
default policy (deny). The attribution drives both hit counts and log lines.
Policies without logging produce hits but no log lines.

## 5. Output artifacts

Directory layout of one generated scenario:

```
scenario-<id>/
  artifacts/                   # what palimp receives
    config.set                 # final configuration
    commits.txt                # commit history
    rollbacks/
      rollback-01.set ... rollback-49.set
    logs/
      rt_flow.log              # RT_FLOW session logs
    hitcount.txt               # policy hit counts
    tickets.csv                # optional, partial
    cmdb.csv                   # optional, partial and stale
  ground_truth.json            # never given to palimp
  manifest.json                # seed, knobs, simulator version, file hashes
```

The snapshot date (when the engineer "inherits" the firewall) is the end of the
timeline. The device host name is fixed per scenario (for example `fw-hq-01`).

### 5.1 Final configuration (`config.set`)

As printed by `show configuration | display set` **[VSRX-1]**. Contains at least:

```
set system host-name fw-hq-01
set security zones security-zone servers interfaces ge-0/0/2.0
set security zones security-zone servers address-book address crm-db-01 10.20.3.11/32
set security address-book global address crm-web-01 10.20.2.10/32
set applications application tcp-8443 protocol tcp
set applications application tcp-8443 destination-port 8443
set security policies from-zone users to-zone servers policy users-to-crm-web match source-address users-hq
set security policies from-zone users to-zone servers policy users-to-crm-web match destination-address crm-web-01
set security policies from-zone users to-zone servers policy users-to-crm-web match application junos-https
set security policies from-zone users to-zone servers policy users-to-crm-web then permit
set security policies from-zone users to-zone servers policy users-to-crm-web then log session-close
set security policies from-zone users to-zone servers policy users-to-crm-web description "CRM web access CHG0012345"
```

Also: address sets, application sets, deactivated statements, and non-policy
configuration (system, interfaces, routing) as filler so the parser must ignore
what it does not need. Policy order in the output is evaluation order within a
zone pair **[VSRX-3]**. Annotations (`annotate`) do not appear in set format
**[VSRX-2]**, so they are only used as a trap in hierarchical output if that
format is added later. Global policies (`set security policies global ...`) are
off by default and enabled by a knob.

### 5.2 Commit history (`commits.txt`)

As printed by `show system commit` **[VSRX-4]**:

```
0   2026-09-14 22:41:07 CEST by jdoe via cli
    CHG0012345 add CRM export to partner
1   2026-09-12 10:02:55 CEST by svc-ansible via netconf
    managed by ansible, run 1832
2   2026-09-10 16:30:12 CEST by admin via cli commit confirmed, rollback in 10mins
3   2026-09-10 16:24:48 CEST by admin via cli
```

Entry 0 is the active configuration. Comments are on the following indented
line and absent when empty. The number of entries is limited by retention
**[VSRX-6]**, so older history is lost. Time zone of the device is a knob.

### 5.3 Rollback files (`rollbacks/rollback-NN.set`)

One file per retained previous commit, as printed by
`show system rollback NN | display set` **[VSRX-1]** **[VSRX-6]**. Rollback NN
matches commit history entry NN. palimp reconstructs history by diffing
consecutive rollbacks. A knob can instead emit the stored hierarchical files
(`juniper.conf.NN.gz` content, with the `## Last changed:` header), for later
format support **[VSRX-8]**.

### 5.4 Session logs (`logs/rt_flow.log`)

RT_FLOW messages for policies with logging enabled, over the last
`log_window_days` days. Default format is structured syslog **[VSRX-9]**:

```
<14>1 2026-09-14T08:12:44.311+02:00 fw-hq-01 RT_FLOW - RT_FLOW_SESSION_CLOSE [junos@2636.1.1.1.2.129 reason="TCP FIN" source-address="10.10.4.23" source-port="52811" destination-address="10.20.2.10" destination-port="443" connection-tag="0" service-name="junos-https" nat-source-address="10.10.4.23" nat-source-port="52811" nat-destination-address="10.20.2.10" nat-destination-port="443" nat-connection-tag="0" src-nat-rule-type="N/A" src-nat-rule-name="N/A" dst-nat-rule-type="N/A" dst-nat-rule-name="N/A" protocol-id="6" policy-name="users-to-crm-web" source-zone-name="users" destination-zone-name="servers" session-id="81234" packets-from-client="12" bytes-from-client="1840" packets-from-server="10" bytes-from-server="9211" elapsed-time="3" application="UNKNOWN" nested-application="UNKNOWN" username="N/A" roles="N/A" packet-incoming-interface="ge-0/0/1.0" encrypted="UNKNOWN"]
```

Message types: `RT_FLOW_SESSION_CREATE` (log session-init),
`RT_FLOW_SESSION_CLOSE` (log session-close), `RT_FLOW_SESSION_DENY` (deny
policies with logging). A knob switches to the standard (unstructured) syslog
format **[VSRX-10]**. The exact attribute list per message type depends on the
Junos release **[VSRX-9]**.

Volume control: sessions are sampled so a scenario stays small (knob
`log_sample_rate`); the ground truth records the real counts.

### 5.5 Hit counts (`hitcount.txt`)

As printed by `show security policies hit-count` **[VSRX-7]**:

```
Logical system: root-logical-system
 Index   From zone        To zone           Name                    Policy count  Action
 1       users            servers           users-to-crm-web        184223        Permit
 2       users            servers           rule-47                 0             Permit
```

Counts are cumulative since the last reset (reboot, upgrade, or
`clear security policies hit-count`). The reset date is not in the file; it can
sometimes be inferred from the commit history (routine commit comment
`upgrade to ...`) or not at all.

### 5.6 Tickets (`tickets.csv`, optional)

Partial export of a ticketing tool. Columns:

```
ticket_id,opened,closed,status,requester,assignee,summary,category,related_ci
CHG0012345,2026-09-01,2026-09-14,closed,A. Marchetti,jdoe,"Open CRM export to partner SFTP",change,crm
```

Coverage is partial (`ticket_rate`, `ticket_export_coverage`); some tickets are
rejected or cancelled although a rule was created; free text is inconsistent.
This is a fictional format, not tied to a real product.

### 5.7 CMDB (`cmdb.csv`, optional)

```
hostname,ip,environment,application,owner,status,last_updated
crm-db-01,10.20.3.11,prod,crm,A. Marchetti,in service,2025-02-11
```

Partial and stale on purpose (`cmdb_staleness`): retired servers still listed,
new ones missing, old owners.

### 5.8 Manifest (`manifest.json`)

Simulator version, scenario id, seed, difficulty, all knob values, snapshot
date, split (dev or held-out marker, see section 8), and the SHA-256 of every
file.

## 6. Ground truth schema

`ground_truth.json` is one JSON document validated by a JSON Schema kept in the
simulator package and in the evaluation harness (the only shared contract with
the evaluation side, section 10).

```json
{
  "schema_version": 1,
  "scenario_id": "medium-000123",
  "snapshot": "2026-09-28T09:00:00+02:00",
  "rules": [
    {
      "rule_uid": "R-0042",
      "key": {"from_zone": "users", "to_zone": "servers", "name": "rule-47"},
      "name_history": ["users-to-legacy-ftp", "rule-47"],
      "deactivated": false,
      "created": {"event_id": "EV-0107", "date": "2021-03-02", "admin": "adm-3",
                  "persona": "hurried_operator", "in_retained_history": false},
      "intent": {
        "kind": "app_dependency",
        "app_id": "legacy-ftp",
        "flows": ["F-0211"],
        "summary": "Office users upload daily invoices to the legacy FTP server"
      },
      "status": {
        "live": false,
        "still_needed": false,
        "last_real_use": "2024-11-30",
        "hits_in_window": 0,
        "hits_reason": "none"
      },
      "expected": {
        "verdict": "removal_candidate",
        "best_achievable_verdict": "verify",
        "max_justified_confidence": "LOW",
        "owner_to_ask": "P-017"
      },
      "evidence": [
        {"id": "G1", "tier": "T3", "artifact": "config.set",
         "locator": "policy rule-47 destination-address legacy-ftp-01",
         "supports": "intent", "misleading": false},
        {"id": "G2", "tier": "T2", "artifact": "hitcount.txt",
         "locator": "rule-47", "supports": "not_live", "misleading": false}
      ],
      "traps": ["TRAP-HISTORY-HORIZON"]
    }
  ],
  "objects": [ ... ],
  "events": [ ... ],
  "people": [ ... ],
  "apps": [ ... ]
}
```

Field meanings:

- `rule_uid`: stable id, not present in artifacts. `key` is how palimp's output
  is matched to the ground truth (zone pair plus final policy name).
- `intent.kind`: enum `app_access`, `app_dependency`, `shared_service`,
  `management`, `monitoring`, `backup`, `partner_access`, `internet_access`,
  `emergency_temporary`, `migration_bridge`, `test`, `unknown_origin`.
  Intent accuracy is scored on `kind` plus `app_id`, not on free text.
- `status.live`: at least one flow the rule is meant for still exists and is
  matched by this rule. `hits_reason` explains traffic that is not business
  use: `scanner`, `monitoring`, `ip_reuse`, `shadowing_other_rule`, `none`.
- `expected.verdict`: the right answer with perfect knowledge.
  `expected.best_achievable_verdict`: the best answer a perfect analyzer can
  give from the artifacts only. Scoring uses the latter, and reports both.
- `expected.max_justified_confidence`: the highest confidence the available
  evidence supports; used for calibration scoring.
- `evidence`: every piece of evidence a perfect analyzer could find in the
  artifacts, with tier (T1 to T4 as in CLAUDE.md), location, what it supports
  (`intent`, `live`, `not_live`, `owner`) and whether it is misleading.
  Evidence destroyed by retention or log rotation is not listed, but the loss is
  flagged (`in_retained_history: false`).
- `traps`: ids from section 7.3.

## 7. Difficulty levels

### 7.1 Knobs

| Knob | easy | medium | hard (v2) | adversarial (v2) |
|---|---|---|---|---|
| `years` | 2 | 4 | 7 | 10 |
| applications | 8 | 25 | 60 | 120 |
| final policy count (approx) | 40 | 150 | 450 | 1200 |
| zones | 4 | 5 | 6 | 7 |
| personas active | senior | senior, operator, automation | all | all, several shared logins |
| `comment_rate` (weighted mean) | 0.9 | 0.6 | 0.35 | 0.2 |
| misleading comment rate | 0 | 0.03 | 0.08 | 0.15 |
| `description_rate` | 0.8 | 0.4 | 0.2 | 0.1 |
| `log_rate` | 0.9 | 0.6 | 0.35 | 0.2 |
| `log_window_days` | 90 | 60 | 30 | 14 |
| days since hit count reset | 365 | 180 | 45 | 7 |
| `ticket_rate` / export coverage | 0.9 / 1.0 | 0.6 / 0.8 | 0.4 / 0.5 | 0.2 / 0.3 |
| CMDB present / staleness | yes / low | yes / medium | yes / high | no |
| `cleanup_rate` | 0.9 | 0.6 | 0.3 | 0.15 |
| `cleanup_error_rate` | 0 | 0 (v2: 0.02) | 0.05 | 0.1 |
| emergency events per year | 0 | 1 | 4 | 8 |
| contractor periods | 0 | 0 (v2: 1) | 2 | 4 |
| `ip_reuse_rate` | 0 | 0 (v2: 0.1) | 0.3 | 0.5 |
| renames per year | 0 | 0 (v2: 1) | 4 | 10 |
| commits per year (drives history horizon) | 20 | 60 | 150 | 300 |
| rare jobs (quarterly, yearly) | 0 | 2 | 6 | 12 |
| log format | structured | structured | structured | standard |

Each knob can be overridden individually; a scenario is defined by a level plus
overrides.

Scope (decision 0008): v1 implements Easy and Medium only. Hard and Adversarial
are v2. In v1, Medium uses the values shown first; the values marked "v2" apply
once the matching traps exist. Migrations in v1 use the duplicate and bridge
styles only (repoint produces `TRAP-STALE-NAME`, a v2 trap).

### 7.2 Trap coverage rule

v1: every v1 trap appears at least once in every Medium scenario. Easy
scenarios contain no deliberate traps. v2: every trap appears at least once in
every Hard and Adversarial scenario. Each trap id is recorded on the rules it
affects, so metrics can be reported per trap.

### 7.3 Deliberate traps

| Id | Scope | Situation | Naive conclusion | Truth |
|---|---|---|---|---|
| `TRAP-LIVE-NOLOG` | v1 | live rule without logging, hit counts recently reset | dead, remove | live; best verdict is verify |
| `TRAP-RARE-JOB` | v1 | quarterly or yearly flow, no hits in window | dead, remove | live; removing it is the most severe error |
| `TRAP-PREPROVISIONED` | v1 | rule created before go-live, zero hits | dead | live soon |
| `TRAP-MISLEADING-COMMENT` | v1 | comment or ticket describes another change | trusts the comment | intent from other evidence |
| `TRAP-BATCH-COMMIT` | v1 | one commit, one comment, many unrelated changes | one intent for all | per rule intents |
| `TRAP-STALE-NAME` | v2 | rule name refers to an old app, objects repointed | intent from the name | intent of the current destination |
| `TRAP-IP-REUSE` | v2 | dead rule matches traffic to a reused IP | live, keep | intent dead, traffic belongs elsewhere; verify |
| `TRAP-SCANNER-HITS` | v2 | hits only from scanners or monitoring | live | dead for business use |
| `TRAP-EMERGENCY-LOADBEARING` | v1 | "temporary" broad rule now the only one carrying a flow | remove the temp rule | needed, verify and replace |
| `TRAP-SHADOWED-DUPLICATE` | v2 | valid intent, rule never matched because an earlier rule covers it | dead, unknown intent | intent known, rule redundant |
| `TRAP-RENAME-CHAIN` | v2 | object or policy renamed, old rollbacks use old names | two unrelated rules | same rule |
| `TRAP-DEACTIVATED` | v1 | deactivated policy still in config | active rule | inactive; intent historical |
| `TRAP-TICKET-REJECTED` | v2 | ticket rejected or cancelled but rule exists | intent from ticket | intent unconfirmed |
| `TRAP-HISTORY-HORIZON` | v1 | rule older than retained history | no T1 evidence means no intent | intent only from T2/T3/T4, confidence capped |
| `TRAP-SHARED-LOGIN` | v2 | commits by `admin` or `root` | one author | several personas |
| `TRAP-CLEANUP-FLAP` | v2 | live rule removed by mistake, re-added under another name | new unrelated rule | same intent as the removed one |

## 8. Determinism and the dev / held-out split

### 8.1 Seeded generation

- A scenario is fully defined by `(simulator_version, difficulty, overrides,
  seed)`. The same inputs produce byte-identical artifacts on any OS.
- One master seed; each component (company, personas, timeline, traffic, each
  artifact writer) gets its own sub-generator seeded from
  `SHA-256("<master seed>:<component name>")`, so adding a component does not
  shift the others.
- Only `random.Random.random()` is used as the primitive; choices, integers and
  shuffles are implemented on top of it in the simulator, because Python only
  guarantees the `random()` sequence across versions, not `randrange`,
  `choice` or `shuffle`.
- No use of `hash()`, set iteration order, wall clock time, locale, or the
  host time zone. Dates come from the scenario calendar. Output files use LF
  line endings and UTF-8.
- The manifest records file hashes; a golden test regenerates a few fixed
  scenarios and compares hashes. A change to the output requires a simulator
  version bump.

### 8.2 Split

Decision 0007 defines where held-out evaluation runs.

- Dev set: scenario seeds `0` to `N`, public, used freely while developing.
- Held-out set: seeds derived from a secret salt,
  `SHA-256("<salt>:<level>:<index>")`. The salt is the GitHub repository secret
  `HOLDOUT_SALT`. It never exists on the development machine, because the coding
  agent has full access to that machine.
- Held-out scenarios are generated and scored only in a GitHub Actions workflow
  with a `workflow_dispatch` trigger, started by the project lead. The workflow
  prints aggregate metrics only (per level and per trap). It never prints seeds,
  scenario content, per rule results or ground truth, and uploads no artifacts.
- Tuning the analyzer on held-out results is forbidden (CLAUDE.md). The Actions
  run history records every held-out run with its date and commit, so repeated
  peeking is visible.
- The project lead rotates the salt when the simulator version changes in a way
  that affects difficulty.
- The workflow is written once the simulator can generate scenarios.

## 9. Evaluation interface (for reference)

The evaluation harness (separate component, specified later) runs the palimp
CLI as a subprocess on `artifacts/`, reads its JSON report, matches rules by
`key`, and computes: intent accuracy, confidence calibration, unsourced claim
count, and dangerous errors (removal candidate on a live rule, also counted per
trap). palimp never sees `ground_truth.json` or `manifest.json`.

## 10. Independence from src/palimp

The risk: the same author writes both sides and bakes the same assumptions into
the generator and the analyzer, so scores look good for the wrong reason.

Rules:

- The simulator is a separate uv workspace member in `simulator/` (decision
  0009): distribution `palimp-sim`, import package `palimp_sim`, command
  `palimp-sim`, never shipped in the palimp wheel. It never imports `palimp`,
  and `src/palimp` never imports `palimp_sim`. Enforced in CI with ruff's
  banned import rule (`TID251`) configured per project, plus a test that scans
  imports.
- No shared helper module, not even for Junos formatting. The simulator writes
  Junos text with its own templates; palimp parses it with its own parser. The
  only shared contract is the ground truth JSON Schema, consumed by the
  evaluation harness, not by palimp.
- The evaluation harness calls palimp only through its CLI and JSON output.
- The real format reference is the vSRX lab fixtures, not the simulator: the
  parser is tested against real vSRX output first, and simulator output is
  checked against the same fixtures (format conformance tests on the simulator
  side).
- Sessions are single-mission (CLAUDE.md): a session working on the analyzer
  does not modify the simulator, and the reverse. Changes to trap definitions
  are reviewed as simulator changes, never made to fix an analyzer score.

## 11. Format assumptions to confirm on a real vSRX

| Id | Assumption | How to confirm |
|---|---|---|
| VSRX-1 | `show configuration \| display set` and `show system rollback N \| display set` print one `set` statement per line, in the layout shown, with quoted descriptions | capture both on vSRX, store as fixtures |
| VSRX-2 | deactivated statements appear as `deactivate ...` lines in set output; annotations are dropped | `deactivate` and `annotate` a policy, then display set |
| VSRX-3 | order of policy lines in set output is the evaluation order within a zone pair, including after `insert policy ... before` | insert a policy, compare set output and `show security policies` order |
| VSRX-4 | exact layout of `show system commit`: column widths, time zone abbreviation, `via cli` / `via netconf`, comment on next line, `commit confirmed, rollback in Nmins` text | several commits with and without comments, over netconf, with commit confirmed |
| VSRX-5 | a `rename` shows as delete plus add between two rollbacks | rename an address object, `show system rollback compare 1 0` |
| VSRX-6 | retention of 50 configurations (0 to 49), and the commit history showing exactly the retained ones | make more than 50 commits |
| VSRX-7 | layout of `show security policies hit-count`, and which events reset counters (reboot, `clear security policies hit-count`, commit of a changed policy?) | reboot, clear, modify a policy, compare counts |
| VSRX-8 | layout of stored rollback files (`/config/juniper.conf.N.gz`, `## Last changed:` header) | `file list /config/`, `file show` |
| VSRX-9 | structured syslog field names and order for RT_FLOW_SESSION_CREATE, CLOSE and DENY on the lab's Junos release, and the `junos@2636...` SD-ID | enable `security log format sd-syslog`, generate traffic |
| VSRX-10 | standard syslog RT_FLOW line layout | same with default format |
| VSRX-11 | whether logs of deactivated or deleted policies keep the old policy name | delete a logged policy during live sessions |

Each confirmed assumption becomes a parser fixture under `tests/fixtures/vsrx/`
and a conformance test on the simulator side.
