# Format assumptions VSRX-1 to VSRX-12, checked against Juniper documentation

Session 6, 2026-10-04. Decision 0013: until a real vSRX is available, each
format assumption is checked against output published in Juniper's official
documentation. Every sample used here is stored, copied unchanged, under
`tests/fixtures/junos_docs/` with its source URL, page title, release and
retrieval date in a header. Nothing below is invented output.

The assumptions themselves are listed in `docs/simulator-spec.md` (section 11).
This file only records what the documentation shows.

## How to read the table

- **Status**: CONFIRMED (documentation agrees), CORRECTED (documentation
  disagrees, the change is given), UNVERIFIED (no documentation evidence).
- **Evidence**: `sample` means a published output sample, stored as a fixture.
  `text` means a statement in the documentation prose, with no output sample.
  Behavioral assumptions (retention, ordering, counter resets) can rarely be
  shown by a sample, so text evidence is accepted for them and marked as such.
- Most samples come from older releases (12.x to 13.x, dates 2002 to 2022), or
  state no release at all. They show the layout Juniper publishes, not
  necessarily what the latest Junos prints.

## Results

| ID | Claim | Status | Evidence | Fixture or source | What the documentation shows |
|----|-------|--------|----------|-------------------|------------------------------|
| VSRX-1a | `show configuration \| display set` prints one `set` statement per line, full path from the top level | CONFIRMED | sample | `display_set_deactivate.txt`, `display_set_pipe.txt` | One full-path statement per line. `display set relative` and `explicit` exist and change the output (relative paths, extra intermediate statements). |
| VSRX-1b | descriptions are double-quoted in set output | UNVERIFIED | none | - | No set-format output with a quoted value was found. Quoted descriptions appear only in hierarchical `show` output and in "CLI Quick Configuration" blocks, which are input, not output. |
| VSRX-1c | `show system rollback N \| display set` prints the same set layout | UNVERIFIED | none | - | The `show system rollback` page shows only hierarchical `compare` output (lines starting with `+`). No `display set` sample for a rollback. |
| VSRX-2a | deactivated statements appear as `deactivate ...` lines | CONFIRMED | sample | `display_set_deactivate.txt` | The subtree is printed as `set` lines, then one `deactivate <path>` line naming the deactivated node, after those lines. |
| VSRX-2b | annotations (`annotate`) do not appear in set output | UNVERIFIED | text (partial) | annotate and "Modify the Configuration of a Device" pages | The documentation says comments are visible with `show` and `show configuration`; it does not say whether `display set` drops them. |
| VSRX-3 | order of policy lines is the evaluation order within a zone pair, including after `insert ... before` | CONFIRMED | text | "Reordering Security Policies" page | "Security policies execute in the order of their appearance in the configuration file", "New policies go to the end of the policy list", `insert security policies ... before policy ...` changes the order. No output sample after an insert. |
| VSRX-4a | entry layout: index, date, time, time zone abbreviation, `by USER via METHOD` | CONFIRMED | sample | `show_system_commit.txt`, `show_system_commit_rollback_pending_12.3.txt` | `0   2003-07-28 19:14:04 PDT by root via other`. Index followed by three spaces in current samples, one space in an older one. |
| VSRX-4b | methods `cli` and `netconf` | CORRECTED | sample + text | `show_system_commit.txt` | Samples show `cli`, `other`, `button`, `autoinstall`. Documented methods: CLI, Junos XML protocol, synchronize, snmp, button, autoinstall, other (`root via other` for system commits without a login). The printed token for NETCONF or Junos XML clients is not shown: `via netconf` stays unverified. A last line `rescue  <date> by root via other` can follow the numbered entries. |
| VSRX-4c | `commit confirmed, rollback in Nmins` text | CONFIRMED | sample | `show_system_commit_rollback_pending.txt`, `show_system_commit_rollback_pending_12.3.txt` | Same line, after the method: `via cli commit confirmed, rollback in 10mins`. |
| VSRX-4d | the commit comment is on the next, indented line, absent when empty | UNVERIFIED (conflicting hint) | sample (indirect) | `show_system_commit_activate.txt` | No sample shows a user comment. The only hint goes the other way: a history line reads `0   2018-07-12 22:54:46 PDT by user via cli commit activate` and the same commit's `show system commit revision detail` shows `Comment     : commit activate`, so the comment may be printed on the same line, after the method. The output fields table of `show system commit` lists no comment field. Highest-risk open point: commit comments are palimp's main T1 source. |
| VSRX-4e | (not in the spec) optional fields | CORRECTED | sample | `show_system_commit_include_revision.txt` | `include-configuration-revision` (20.4R1 and later) appends a revision id such as `re0-1596309177-4` on the same line. |
| VSRX-5 | a `rename` shows as delete plus add between two rollbacks | CONFIRMED | text | "Modify the Configuration of a Device" page | "The rename command replaces the configuration statement indicated with the new configuration": the old name is gone, so two full rollback configurations differ by one removal and one addition. No `compare` output of a rename was found. |
| VSRX-6 | retention of 50 configurations (0 to 49); commit history shows the retained ones | CONFIRMED | sample + text | `rollback_completions_0_49.txt` | `rollback ?` lists 0 to 49; `show system rollback` accepts 0 through 49; `show system commit` "displays the last 50 commit operations". |
| VSRX-7a | hit-count layout: `Logical system:` line, header `Index From zone To zone Name Policy count Action`, one row per policy | CORRECTED | sample | `hitcount_logical_system.txt`, `hitcount_legacy.txt`, `hitcount_detail.txt` | The layout with `Logical system: root-logical-system` and an Action column matches. But: (1) an older layout has a lowercase header `index from zone to zone name policy count`, no Action column, and a footer `Number of policy: 3`; (2) `detail` adds a `Redirect` column; (3) global policies show `junos-global` as both zones. |
| VSRX-7b | row order and index | CORRECTED | text | hit-count page | Without options, rows are listed "in random order"; `Index` is a line number, not the evaluation order. |
| VSRX-7c | events that reset counters | CONFIRMED in part | text | hit-count and `clear security policies hit-count` pages | `clear security policies hit-count [from-zone] [to-zone]` clears counts. Counts are cleared when a node reboots with its PFE, and on ISSU (all PFEs reboot); a PFE failover without reboot keeps them. In a chassis cluster the count is a sum over all SPCs. Whether committing a changed policy resets its counter is not documented: UNVERIFIED. |
| VSRX-8 | stored rollback files are `/config/juniper.conf.N.gz` with a `## Last changed:` header | CORRECTED | text | "Commit the Configuration" page, "View the Configuration" page | Current config `/config/juniper.conf.gz`; rollbacks 1 to 3 in `/config`, 4 to 49 in `/var/db/config` (the page names them both `juniper.conf.1.gz` and `juniper.conf.gz.1`). The header shown at the top of `show configuration` is `## Last commit: 2018-07-18 11:21:58 PDT by echen`, not `## Last changed:`. The header of the stored files themselves is not shown: UNVERIFIED. |
| VSRX-9a | structured syslog header `<14>1 TIMESTAMP HOST RT_FLOW - RT_FLOW_SESSION_X [junos@2636... k="v" ...]` | CONFIRMED | sample | `rt_flow_structured_12.1x47.txt`, `rt_flow_structured_wrapped.txt` | Same header. PRI 14 matches the documented facility LOG_USER and severity info. Timestamps appear with and without offset (`2011-08-28T21:14:43`, `2010-09-30T14:55:04.323+08:00`). |
| VSRX-9b | SD-ID `junos@2636.1.1.1.2.129` | UNVERIFIED | sample (other values) | `rt_flow_structured_12.1x47.txt`, `rt_flow_structured_12.3_remote.txt` | The last number varies by platform: `junos@2636.1.1.1.2.34` and `.39` in the samples. No vSRX sample, so `.129` is not confirmed. |
| VSRX-9c | attribute names and order for CREATE, CLOSE, DENY | CORRECTED | sample + reference | `syslog_explorer_rt_flow_session_*.txt`, `rt_flow_structured_*.txt` | Names and order in the spec example match Juniper's templates up to `encrypted`. Corrections: (1) since at least 22.2R1, more attributes follow `encrypted` (`application-category`, `application-sub-category`, `application-risk`, `application-characteristics`, `secure-web-proxy-session-type`, `peer-*`, `hostname`, `src-vrf-grp`, `dst-vrf-grp`, `tunnel-inspection`, `tunnel-inspection-policy-set`, `session-flag`, `source-tenant`, `destination-service`, and more in later releases; CLOSE has 50 attributes in 22.2R1 and 61 in 26.2R1); (2) releases documented around 12.x use `session-id-32` instead of `session-id` and have no `connection-tag` or NAT rule types; (3) logical systems emit `RT_FLOW_SESSION_CREATE_LS` and `RT_FLOW_SESSION_CLOSE_LS` with a `logical-system-name` attribute; (4) DENY has its own list (`icmp-type`, `reason`, `session-id`, no NAT fields). |
| VSRX-9d | (not in the spec) shape of collected lines | CORRECTED | sample | `rt_flow_structured_12.3_remote.txt`, `rt_flow_structured_wrapped.txt` | Lines collected on a remote syslog server start with the server's own prefix (`Sep 06 16:54:22 10.204.225.164 1 2010-...`) and no `<PRI>`. One published sample has the standard message text appended after the closing `]`. |
| VSRX-10 | standard syslog RT_FLOW line layout | CONFIRMED | sample + reference | `rt_flow_standard_12.3_remote.txt`, `syslog_explorer_rt_flow_session_*.txt` | `RT_FLOW: RT_FLOW_SESSION_CREATE: session created SRC/PORT->DST/PORT SERVICE NATSRC/PORT->NATDST/PORT SRCRULE DSTRULE PROTO POLICY FROMZONE TOZONE SESSIONID` (12.3 sample). Current templates add `0x<connection-tag>`, NAT rule types and the application fields; CLOSE adds `REASON:` after `session closed` and `PKTS(BYTES)` counters. |
| VSRX-11 | logs of deleted or deactivated policies keep the old policy name | UNVERIFIED | text (indirect) | "Monitoring Security Flow Sessions" page | A close reason `policy delete` ("Corresponding policy marked for deletion") exists, so sessions of a deleted policy are closed and logged, but the documentation does not say which policy name the message carries. |
| VSRX-12a | predefined `junos-http` (tcp 80), `junos-https` (tcp 443), `junos-ssh` (tcp 22), `junos-smtp` (tcp 25), `junos-dns-udp` (udp 53) | CONFIRMED | sample | `junos_defaults_applications_13.2.txt` | Present in `show groups junos-defaults` with those protocols and ports. |
| VSRX-12b | predefined `junos-ntp` | UNVERIFIED | none | - | Not in the partial `junos-defaults` sample. The predefined applications page lists NTP with port 123 but does not give the `junos-` name. |
| VSRX-12c | UDP sessions close with reason `idle Timeout` | CONFIRMED in part | text | "Monitoring Security Flow Sessions" page | The reason string `idle Timeout` exists ("no traffic for the session before the configured age-out time was reached"). A separate `aged out` reason also exists; which one UDP sessions use is not stated. |

## Readers against the fixtures

`uv run python eval/format_fixtures.py` runs the readers in
`src/palimp/formats/` on the fixture bodies (header removed). Result on
2026-10-04, no reader changed:

| Fixture | Reader | Result | Gap |
|---------|--------|--------|-----|
| `display_set_deactivate.txt` | junos_set | parses (interfaces lines ignored as out of scope) | G1 |
| `display_set_pipe.txt` | junos_set | fails on relative lines | G1, G2 |
| `show_system_commit.txt` | commits | 6 of 6 numbered entries | G1, G3 |
| `show_system_commit_rollback_pending.txt` | commits | parses | G1 |
| `show_system_commit_rollback_pending_12.3.txt` | commits | parses | - |
| `show_system_commit_include_revision.txt` | commits | parses, revision id lands in `extra` | G1, G4 |
| `show_system_commit_activate.txt` | commits | parses, `commit activate` lands in `extra`, comment empty | G1, G4 |
| `rollback_completions_0_49.txt` | commits | 10 of 50 entries: indexes 10 to 49 are right-aligned, start with spaces and are glued to entry 9 as comment text | G5 |
| `hitcount_logical_system.txt` | hitcount | parses | G1 |
| `hitcount_detail.txt` | hitcount | 0 of 2 rows (extra Redirect column) | G1, G6 |
| `hitcount_legacy.txt` | hitcount | 0 of 3 rows (no Action column, lowercase header, footer) | G1, G6 |
| `rt_flow_structured_12.1x47.txt` | rt_flow | 3 of 5 messages; `_LS` message types rejected | G7 |
| `rt_flow_structured_12.3_remote.txt` | rt_flow | 0 of 3 (collector prefix, no `<PRI>`) | G8 |
| `rt_flow_structured_wrapped.txt` | rt_flow | 0 of 2 (text after `]`, plus line wrapping from the page) | G9 |
| `rt_flow_standard_12.3_remote.txt` | rt_flow | 0 of 2 (standard format not supported, known) | G10 |

The `syslog_explorer_*` and `junos_defaults_applications_13.2.txt` fixtures are
references, not reader input.

## Gaps for the next sessions

Not fixed in this session. Analyzer gaps (G1 to G10) belong to an analyzer
session; simulator corrections (S1 to S6) to a simulator session.

Analyzer (src/palimp/formats):

- **G1** CLI prompt lines (`user@host> show ...`) and echo lines are counted as
  unknown. Harmless (never fatal) but noisy; a saved terminal capture usually
  contains them.
- **G2** `display set relative` output (`set unit 0 ...`) is not supported.
  Low priority: inherited exports are normally from the top level.
- **G3** the trailing `rescue` line of `show system commit` is unknown; `...`
  is unknown.
- **G4** text after the method is stored in `extra` and never treated as a
  comment. If VSRX-4d turns out to be "same line", every commit comment is
  lost from T1. The reader should at least keep `extra` available to evidence
  collection, and separate known suffixes (`commit confirmed, rollback in
  Nmins`, revision ids) from free text.
- **G5** a line that starts with whitespace is taken as a comment
  continuation. Right-aligned indexes (`  10  2018-...`) break this. The entry
  regex should allow leading spaces, and continuation lines should be those
  that do not match an entry.
- **G6** hit-count rows must accept the legacy layout (5 columns, no Action),
  the `detail` layout (Redirect column), the lowercase header and the
  `Number of policy:` footer.
- **G7** `RT_FLOW_SESSION_CREATE_LS` / `RT_FLOW_SESSION_CLOSE_LS` (logical
  systems) are rejected.
- **G8** structured lines with a collector prefix and no `<PRI>` are rejected.
  Logs handed to palimp will often come from a syslog server, not the device.
- **G9** structured lines followed by the standard text after `]` are rejected
  (the regex requires `]` at end of line).
- **G10** standard (unstructured) RT_FLOW format not supported (known before
  this session).

Simulator (docs/simulator-spec.md and simulator/):

- **S1** hit-count rows: index is a line number and rows are not in evaluation
  order (VSRX-7b); consider emitting the legacy layout as a knob.
- **S2** rollback storage paths and header (VSRX-8): `/config` for 1 to 3,
  `/var/db/config` for 4 to 49, header `## Last commit:` in `show
  configuration` output.
- **S3** RT_FLOW attribute list (VSRX-9c): current releases emit more
  attributes after `encrypted`; consider a release knob, including the
  `session-id-32` era.
- **S4** collected-log shapes (VSRX-9d): collector prefix without `<PRI>`, as a
  knob.
- **S5** commit methods (VSRX-4b): `via other` for system commits, optional
  `rescue` line; `via netconf` is unverified.
- **S6** `junos-ntp` (VSRX-12b) is unverified; keep it but flag it.

## Open points that need a real device

VSRX-1b (quoted descriptions in set output), VSRX-1c (rollback in set format),
VSRX-2b (annotations), VSRX-4d (comment placement, the most important),
VSRX-7c (counter reset on commit), VSRX-8 (stored file header), VSRX-9b (vSRX
SD-ID), VSRX-11 (policy name after delete), VSRX-12b and VSRX-12c.
