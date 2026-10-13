# 0037 Other `then permit` options read as permit; anonymize keeps terminal lines

- Status: Accepted
- Date: 2026-10-13
- Supersedes: the postponed alternative of decision 0034 ("Treat any
  `then permit <option>` (`tunnel`, `firewall-authentication`,
  `destination-address`) as permit: postponed"). The rest of 0034 stands.
  Extends decision 0031 (anonymize) on saved terminal captures.

## Context

Two open items from sessions 21 and 22, raised again in the session 23
prompt:

- `then permit tunnel ...`, `then permit firewall-authentication ...` and
  `then permit destination-address ...` left the policy action unset, in
  both formats. A policy-based VPN rule or a rule behind user
  authentication was then read as a rule with no action.
- `palimp anonymize` on a saved terminal capture treated prompt and banner
  words as names: `[edit]` became `[srwb]`, `show` became `lufh`, so the
  copy lost its relative paths and parsed differently from the original.

## Decision

1. **Permit options.** `then permit tunnel ...`,
   `then permit firewall-authentication ...` and
   `then permit destination-address ...` set the action to `permit`, in
   both formats (the builder is shared). Each statement is kept as written
   after `permit` in `Policy.permit_options` and becomes one T3 evidence
   item (`permit_options`) that names no application: how the rule lets
   traffic through, not why it exists. Other `permit` children
   (`destination-nat`, `source-nat`, `services-offload`) still leave the
   action unset: no sample, not asked.
2. **Fixtures.** Documentation only (decision 0013), with source URL and
   retrieval date: the 12.1X46 policy-based VPN example (set, tunnel), the
   route-based migration page (hierarchical, tunnel), the SRX firewall
   users page (set and hierarchical, firewall-authentication). No published
   configuration sample of `destination-address` was found: the 13.2
   hierarchy page syntax is stored as a reference fixture and the tests
   build an inline sample from it, and say so (PERMIT-OPT-1 to 3 in
   `docs/format-assumptions.md`).
3. **Anonymize names in options.** The word after `ipsec-vpn`,
   `pair-policy`, `client-match`, `access-profile`,
   `ssl-termination-profile` and `auth-user-agent` is a name palimp knows,
   so it is replaced like other names.
4. **Terminal lines in anonymize.** Every line the parsers ignore as
   terminal noise (`palimp.formats.terminal.is_terminal_noise`: prompts,
   `[edit ...]` and node banners, completion help, `...`) keeps its CLI
   words in every file anonymize rewrites (configuration and rollbacks in
   both formats, commits, hit counts, logs). In those lines, only the login
   and host of a prompt, names palimp knows (a zone in
   `[edit security zones security-zone DMZ]`) and IP addresses are
   replaced, the same way as everywhere else.

## Alternatives considered

- Any `then permit <word>` as a permit: simpler, but reads options never
  seen in a sample; kept to the three asked for.
- Keep the options in `application_services`: its evidence text says
  "application services", which would be wrong for a tunnel.
- Leave prompt lines fully unchanged: the login and host in
  `jdoe@fw-paris-01#` identify a person and a device; replacing them keeps
  the line a prompt and keeps the copy shareable.

## Consequences

- No simulator scenario writes these options, so no verdict on Easy,
  Medium or Hard changes (the evaluation of this session runs with this
  code).
- On real configurations, VPN and authenticated rules now have an action
  and show it, with the option as evidence.
- A terminal capture anonymized and parsed again gives the same policies
  (mapped names), the same unknown count and the same judgments
  (`tests/test_anonymize.py`).

## Challenged by Nathan

Not challenged. The session 23 prompt asked for both fixes, with
documentation fixtures only.
