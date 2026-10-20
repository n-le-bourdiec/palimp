"""What kind of rule a policy is, from its action and match alone (session 29).

Plain rules, no scoring:
- a deny or reject rule blocks traffic: removing it opens that traffic, so it is
  never a removal candidate unless it is deactivated (palimp.assess);
- a catch-all deny (any source, any destination, any application, in a zone pair
  or global) is a cleanup rule: it blocks whatever no rule above permits;
- a Junos factory default policy is recognized from its zones, name and match, as
  the Juniper documentation shows them (FACTORY-1 to FACTORY-3 in
  docs/format-assumptions.md);
- a broad permit permits any source to any destination for any application.
"""

from palimp.models import AddressObject, Policy

DENY_ACTIONS = frozenset({"deny", "reject"})
# Zone pair -> policy names of a Junos factory default policy (any/any/any permit).
# trust-to-untrust: SRX210 factory default sample (FACTORY-1,
# hier_factory_default_srx210.txt). The trust to trust pair: SRX300 factory default
# table, no name published (FACTORY-2). default-permit: practitioner captures only
# (FACTORY-3), the name the project lead found on real configurations.
FACTORY_DEFAULTS: dict[tuple[str, str], frozenset[str]] = {
    ("trust", "untrust"): frozenset({"trust-to-untrust", "default-permit"}),
    ("trust", "trust"): frozenset({"default-permit"}),
}


def is_deny(policy: Policy) -> bool:
    return (policy.action or "").lower() in DENY_ACTIONS


ANY_KEYWORDS = frozenset({"any", "any-ipv4", "any-ipv6"})
EVERYWHERE = frozenset({"0.0.0.0/0", "::/0"})


def _holds_everything(name: str, addresses: dict[str, AddressObject], seen: set[str]) -> bool:
    obj = addresses.get(name)
    if obj is None or name in seen:
        return False
    seen.add(name)
    if obj.kind == "address":
        return (obj.value or "") in EVERYWHERE
    return bool(obj.members) and all(
        m in ANY_KEYWORDS or _holds_everything(m, addresses, seen) for m in obj.members
    )


def is_any(names: list[str], addresses: dict[str, AddressObject] | None = None) -> bool:
    """An empty match or the `any` keyword alone (`any-ipv4`, `any-ipv6` included). An
    address-book object named like it (`ANY`) is read by its contents: any only when it
    holds 0.0.0.0/0 (session 31)."""
    addresses = addresses or {}
    return not names or all(
        n in ANY_KEYWORDS and n not in addresses or _holds_everything(n, addresses, set())
        for n in names
    )


def matches_everything(policy: Policy, addresses: dict[str, AddressObject] | None = None) -> bool:
    """Any source, any destination, any application, no dynamic application."""
    return (
        is_any(policy.sources, addresses)
        and is_any(policy.destinations, addresses)
        and policy.applications == ["any"]
        and not policy.dynamic_applications
    )


def is_catch_all_deny(policy: Policy, addresses: dict[str, AddressObject] | None = None) -> bool:
    return is_deny(policy) and matches_everything(policy, addresses)


def is_factory_default(policy: Policy, addresses: dict[str, AddressObject] | None = None) -> bool:
    if policy.is_global or (policy.action or "").lower() != "permit":
        return False
    names = FACTORY_DEFAULTS.get((policy.from_zone, policy.to_zone), frozenset())
    return policy.name in names and matches_everything(policy, addresses)


def is_broad_permit(policy: Policy, addresses: dict[str, AddressObject] | None = None) -> bool:
    return (policy.action or "").lower() == "permit" and matches_everything(policy, addresses)


def factory_source(policy: Policy) -> str:
    """Where the factory default reading of POLICY comes from, its real source (session 31):
    trust-to-untrust is the SRX210 factory default sample; the trust to trust pair is in
    the SRX300 factory default table, with no name; default-permit is practitioner usage,
    in no Juniper sample."""
    if policy.name == "trust-to-untrust":
        return "as in the Juniper SRX210 factory default sample"
    pair = (
        "the trust to trust pair is in the Juniper SRX300 factory default table, with no name"
        if (policy.from_zone, policy.to_zone) == ("trust", "trust")
        else "the trust to untrust pair is in the Juniper SRX210 factory default sample"
    )
    return (
        f"{pair}; the name {policy.name} comes from practitioner usage on real "
        "configurations, no Juniper sample shows it"
    )
