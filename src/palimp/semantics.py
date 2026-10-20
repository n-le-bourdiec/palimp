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

from palimp.models import Policy

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


def is_any(names: list[str]) -> bool:
    """An empty match or `any` alone (`any-ipv4`, `any-ipv6` included)."""
    return not names or all(n.lower() in ("any", "any-ipv4", "any-ipv6") for n in names)


def matches_everything(policy: Policy) -> bool:
    """Any source, any destination, any application, no dynamic application."""
    return (
        is_any(policy.sources)
        and is_any(policy.destinations)
        and policy.applications == ["any"]
        and not policy.dynamic_applications
    )


def is_catch_all_deny(policy: Policy) -> bool:
    return is_deny(policy) and matches_everything(policy)


def is_factory_default(policy: Policy) -> bool:
    if policy.is_global or (policy.action or "").lower() != "permit":
        return False
    names = FACTORY_DEFAULTS.get((policy.from_zone, policy.to_zone), frozenset())
    return policy.name in names and matches_everything(policy)


def is_broad_permit(policy: Policy) -> bool:
    return (policy.action or "").lower() == "permit" and matches_everything(policy)
