# 0030 Internet-facing from public addresses, zone names as a secondary signal

- Status: Accepted
- Date: 2026-10-06
- Supersedes: the internet-facing check added in session 18 (a zone name
  list, `INTERNET_ZONES`, no decision file), used by the "Worth a look"
  ranking of decision 0025's report

## Context

Session 18 ranked the "Worth a look" list of `palimp report` by risk, and
called a rule internet-facing when one of its zones is named `internet`,
`untrust`, `outside`, `external` or `wan`. Zone names are a convention, not
a fact: a site can call its internet zone `isp1` or `public`, and a zone
named `untrust` can hold a partner VPN. Anonymized copies (session 19,
`palimp anonymize`) also replace zone names with tokens, so a zone name list
would see no internet at all on them.

## Decision

A rule is internet-facing when:

1. primary: an address object of its source or destination resolves (through
   the address book, then the rollbacks' history) to a public network, that
   is a network not inside a private or reserved range (RFC 1918, shared
   address space, loopback, link-local, multicast, benchmarking, reserved,
   and the IPv6 equivalents; list in `palimp.addresses`); or
2. secondary: a side of the rule has `any` or addresses palimp cannot resolve
   (DNS names, unknown objects), and the zone of that side is named like the
   internet (the session 18 list).

Resolved private addresses in a zone named `untrust` are not
internet-facing. Documentation ranges (192.0.2.0/24, 198.51.100.0/24,
203.0.113.0/24, 2001:db8::/32) count as public, since examples and
synthetic data use them for internet hosts. The report says why: "public
address ntp-pool (198.51.100.123/32)" or "zone untrust, named like the
internet, with any or unresolved addresses".

## Alternatives considered

- Keep the zone name list only (session 18): rejected, see Context.
- Public addresses only, no zone names: rejected, `any` to `untrust` is the
  most common internet rule and has no address to look at.
- Count documentation ranges as reserved (Python's `is_global`): rejected,
  then the test scenarios and Juniper's documentation samples would show no
  internet-facing rule at all.
- Count zone names even when the side's addresses resolve private: rejected,
  a resolved private address is a stronger fact than a zone name.

## Consequences

- Only the ranking and the reasons of "Worth a look" change. No verdict,
  confidence or owner depends on it (safe direction: it never puts a rule on
  the list by itself, decision 0025).
- The same address classes keep anonymized copies analyzable: `palimp
  anonymize` keeps private addresses private and public addresses public.
- `RuleEntry.internet` in `report.json` holds the reason, empty when the
  rule is not internet-facing.

## Challenged by Nathan

Yes (session 19 prompt): "use public addresses as the primary signal, zone
names as a secondary one". Outcome: this decision.
