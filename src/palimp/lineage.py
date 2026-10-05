"""History lineage read from the rollbacks (T3).

Takeover: policies removed or deactivated while this policy existed, whose
whole match (zones, source, destination, application) this policy covers.
Whatever traffic they carried now matches this policy: it is load-bearing for
flows it was not written for. A fact about the configuration, it says nothing
about whether that traffic still exists.

Migration leftover: a later commit added policies that copy existing ones
(same zones, sources and applications) towards a new destination host of the
same application, at least MIN_MIRRORS of them: the application moved to new
hosts. This policy still points to an old host, it logs its sessions, and no
log line of any policy shows the old host's address in the whole log window.
A positive not-live signal (decision 0024): the history says the host was
replaced and the logs show it silent.

Addresses resolve through the active address book, then the newest definition
found in the rollbacks. Anything that does not resolve to IP networks (DNS
names, ranges, unknown objects) never covers and never counts as silent.
"""

import ipaddress
from dataclasses import dataclass

from palimp.apps import Vocabulary
from palimp.models import Dataset, PastPolicy, Policy

Network = ipaddress.IPv4Network | ipaddress.IPv6Network
ANY = [ipaddress.ip_network("0.0.0.0/0"), ipaddress.ip_network("::/0")]
# Copies towards a new host needed before a destination counts as migrated.
MIN_MIRRORS = 2


def networks(dataset: Dataset, name: str, depth: int = 0) -> list[Network] | None:
    """IP networks of an address object or set, None when it does not resolve."""
    if name == "any":
        return list(ANY)
    obj = dataset.config.addresses.get(name) or dataset.past_addresses.get(name)
    if obj is None or depth > 8:
        return None
    if obj.kind == "address_set":
        found: list[Network] = []
        for member in obj.members:
            nets = networks(dataset, member, depth + 1)
            if nets is None:
                return None
            found += nets
        return found or None
    try:
        return [ipaddress.ip_network((obj.value or "").split()[0], strict=False)]
    except (ValueError, IndexError):
        return None


def _within(inner: list[Network], outer: list[Network]) -> bool:
    return all(
        any(n.version == o.version and n.subnet_of(o) for o in outer)  # type: ignore[arg-type]
        for n in inner
    )


def _side(dataset: Dataset, inner: list[str], outer: list[str]) -> bool:
    outer_nets: list[Network] = []
    for name in outer:
        nets = networks(dataset, name)
        if nets is None:
            return False
        outer_nets += nets
    for name in inner:
        nets = networks(dataset, name)
        if nets is None or not _within(nets, outer_nets):
            return False
    return bool(inner)


def covers(dataset: Dataset, policy: Policy, other: PastPolicy) -> bool:
    """True when every packet `other` matches, `policy` matches too."""
    if (other.from_zone, other.to_zone) != (policy.from_zone, policy.to_zone):
        return False
    if "any" not in policy.applications and not set(other.applications) <= set(policy.applications):
        return False
    if not other.applications:
        return False
    return _side(dataset, other.sources, policy.sources) and _side(
        dataset, other.destinations, policy.destinations
    )


@dataclass
class Takeover:
    key: str
    commit: int
    how: str  # "removed" or "deactivated"


def _comment(dataset: Dataset, index: int) -> str:
    commit = next((c for c in dataset.commits if c.index == index), None)
    if commit is None:
        return f"commit {index}"
    text = f', "{commit.comment}"' if commit.comment else ""
    return f"commit {index} ({commit.timestamp:%Y-%m-%d}{text})"


def takeovers(dataset: Dataset, policy: Policy, created: int | None) -> list[Takeover]:
    """Policies removed or deactivated while `policy` existed, whose match it covers."""
    if policy.deactivated:
        return []
    found: list[Takeover] = []
    for how, changes in (
        ("removed", dataset.removed_by_commit),
        ("deactivated", dataset.deactivated_by_commit),
    ):
        for index, past in sorted(changes.items()):
            if created is not None and index >= created:
                continue  # the change happened before this policy existed
            for other in past:
                if other.key != str(policy.key) and covers(dataset, policy, other):
                    found.append(Takeover(other.key, index, how))
    return found


def takeover_claim(dataset: Dataset, found: list[Takeover]) -> str:
    shown = "; ".join(f"{t.key} ({t.how} in {_comment(dataset, t.commit)})" for t in found[:5])
    more = f"; and {len(found) - 5} more" if len(found) > 5 else ""
    which = "1 policy" if len(found) == 1 else f"{len(found)} policies"
    them = "it" if len(found) == 1 else "they"
    return (
        f"covers the whole match of {which} removed or deactivated while this one existed: "
        f"{shown}{more}. Whatever traffic {them} carried now matches this policy"
    )


@dataclass
class Migration:
    commit: int
    old: str
    new: list[str]
    mirrors: list[str]


def migrations(dataset: Dataset, vocab: Vocabulary) -> list[Migration]:
    """Destinations that a commit copied to new hosts of the same application."""
    found: list[Migration] = []
    for index, added in sorted(dataset.added_by_commit.items()):
        existing = [
            PastPolicy.of(p)
            for p in dataset.config.policies
            if (h := dataset.history.get(str(p.key)))
            and (h.created_in_commit is None or h.created_in_commit > index)
        ]
        existing += [r for j, rs in dataset.removed_by_commit.items() if j < index for r in rs]
        moves: dict[str, dict[str, list[str]]] = {}
        for new in added:
            for old in existing:
                if (
                    (old.from_zone, old.to_zone, sorted(old.sources), sorted(old.applications))
                    != (
                        new.from_zone,
                        new.to_zone,
                        sorted(new.sources),
                        sorted(new.applications),
                    )
                    or len(old.destinations) != 1
                    or len(new.destinations) != 1
                ):
                    continue
                before, after = old.destinations[0], new.destinations[0]
                if before == after or not _same_app(vocab, before, after):
                    continue
                if not _disjoint(dataset, before, after):
                    continue
                moves.setdefault(before, {}).setdefault(after, []).append(new.key)
        for before, targets in sorted(moves.items()):
            mirrors = sorted({k for keys in targets.values() for k in keys})
            if len(mirrors) >= MIN_MIRRORS:
                found.append(Migration(index, before, sorted(targets), mirrors))
    return found


def _same_app(vocab: Vocabulary, before: str, after: str) -> bool:
    apps = vocab.in_object(before)
    return bool(apps) and apps == vocab.in_object(after)


def _disjoint(dataset: Dataset, before: str, after: str) -> bool:
    old, new = networks(dataset, before), networks(dataset, after)
    if old is None or new is None:
        return False
    return not any(a.version == b.version and a.overlaps(b) for a in old for b in new)  # type: ignore[arg-type]


def silent(dataset: Dataset, name: str) -> bool:
    """True when no log line shows an address of object `name`."""
    nets = networks(dataset, name)
    if nets is None or dataset.log_stats is None or dataset.log_window.start is None:
        return False
    for address in dataset.log_window.addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if any(ip.version == n.version and ip in n for n in nets):
            return False
    return True


def leftover_items(
    dataset: Dataset, policy: Policy, created: int | None, found: list[Migration]
) -> list[tuple[str, str, list[str]]]:
    """(locator, claim, migrated objects) when this policy is left behind by a migration."""
    if policy.deactivated or not (policy.log_init or policy.log_close):
        return []
    moved: dict[str, Migration] = {}
    for migration in found:
        if created is not None and migration.commit >= created:
            continue  # the migration is older than the policy
        if migration.old in policy.destinations:
            moved.setdefault(migration.old, migration)
    if not moved or set(policy.destinations) - set(moved):
        return []
    if not all(silent(dataset, name) for name in moved):
        return []
    parts = []
    for name, migration in sorted(moved.items()):
        mirrors = migration.mirrors
        parts.append(
            f"{_comment(dataset, migration.commit)} copied {len(mirrors)} policies from "
            f"{name} to {', '.join(migration.new)} ({', '.join(mirrors[:3])}"
            f"{', ...' if len(mirrors) > 3 else ''})"
        )
    window = dataset.log_window
    claim = (
        "; ".join(parts)
        + f". This policy still points to {', '.join(sorted(moved))}, logs its sessions, and no "
        f"log line of any policy shows that address from {window.start:%Y-%m-%d} to "
        f"{window.end:%Y-%m-%d}: the hosts were replaced and the old ones are silent"
    )
    locator = "commits " + ", ".join(str(m.commit) for m in moved.values()) + " (rollbacks)"
    return [(locator, claim, sorted(moved))]
