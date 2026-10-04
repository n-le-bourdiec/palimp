"""Reader for `show configuration | display set` output (Junos "set" format).

Only security policies, address books and applications are modeled. Lines from
other hierarchies are counted as ignored. Lines that cannot be understood are
counted as unknown and sampled in the stats; they never stop the parse.

Format assumptions to confirm on a real vSRX: VSRX-1 (one statement per line,
quoted descriptions), VSRX-2 (deactivate lines), VSRX-3 (order of appearance
is evaluation order within a zone pair).
"""

import re

from palimp.models import AddressObject, Application, Config, ParseStats, Policy

TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|(\S+)')

# Top-level hierarchies that exist in a Junos config but are outside palimp's scope.
IGNORED_TOP = {
    "version",
    "system",
    "chassis",
    "interfaces",
    "snmp",
    "routing-options",
    "protocols",
    "policy-options",
    "services",
    "firewall",
    "forwarding-options",
    "class-of-service",
    "vlans",
    "groups",
    "apply-groups",
    "access",
    "event-options",
    "routing-instances",
    "bridge-domains",
    "poe",
    "virtual-chassis",
    "ethernet-switching-options",
    "schedulers",
}
IGNORED_SECURITY = {
    "log",
    "screen",
    "nat",
    "ike",
    "ipsec",
    "flow",
    "alg",
    "utm",
    "idp",
    "application-tracking",
    "forwarding-options",
    "authentication-key-chains",
    "pki",
    "ssh-known-hosts",
    "dynamic-address",
    "user-identification",
}


def tokenize(line: str) -> list[str]:
    """Split a set line on spaces, keeping double-quoted strings as one token."""
    return [m.group(1) if m.group(1) is not None else m.group(2) for m in TOKEN.finditer(line)]


class _Builder:
    def __init__(self, file: str) -> None:
        self.stats = ParseStats(file=file)
        self.policies: dict[tuple[str, str, str], Policy] = {}
        self.addresses: dict[str, AddressObject] = {}
        self.applications: dict[str, Application] = {}

    # Each handler returns "parsed", "ignored" or "unknown".

    def policy(self, path: list[str], deactivate: bool) -> str:
        if len(path) < 6 or path[0] != "from-zone" or path[2] != "to-zone" or path[4] != "policy":
            return "unknown"
        key = (path[1], path[3], path[5])
        policy = self.policies.get(key)
        if policy is None:
            policy = Policy(
                from_zone=key[0], to_zone=key[1], name=key[2], position=len(self.policies)
            )
            self.policies[key] = policy
        rest = path[6:]
        if deactivate:
            if not rest:
                policy.deactivated = True
            else:
                policy.deactivated_statements.append(" ".join(rest))
            return "parsed"
        if not rest:
            return "parsed"
        if len(rest) == 2 and rest[0] == "description":
            policy.description = rest[1]
            return "parsed"
        if len(rest) == 3 and rest[0] == "match":
            field = {
                "source-address": policy.sources,
                "destination-address": policy.destinations,
                "application": policy.applications,
            }.get(rest[1])
            if field is None:
                return "ignored"
            if rest[2] not in field:
                field.append(rest[2])
            return "parsed"
        if len(rest) == 2 and rest[0] == "then" and rest[1] in ("permit", "deny", "reject"):
            policy.action = rest[1]
            return "parsed"
        if len(rest) == 3 and rest[:2] == ["then", "log"]:
            if rest[2] == "session-init":
                policy.log_init = True
            elif rest[2] == "session-close":
                policy.log_close = True
            else:
                return "unknown"
            return "parsed"
        if rest and rest[0] in ("then", "match", "scheduler-name"):
            return "ignored"
        return "unknown"

    def address(self, book: str, path: list[str]) -> str:
        if len(path) >= 3 and path[0] == "address":
            name, rest = path[1], path[2:]
            obj = self.addresses.setdefault(
                name, AddressObject(name=name, kind="address", book=book)
            )
            if rest[0] == "description":
                return "ignored"
            obj.value = " ".join(rest)
            return "parsed"
        if len(path) == 4 and path[0] == "address-set" and path[2] in ("address", "address-set"):
            obj = self.addresses.setdefault(
                path[1], AddressObject(name=path[1], kind="address_set", book=book)
            )
            if path[3] not in obj.members:
                obj.members.append(path[3])
            return "parsed"
        if len(path) >= 3 and path[0] == "address-set" and path[2] == "description":
            return "ignored"
        return "unknown"

    def application(self, path: list[str]) -> str:
        if len(path) >= 3 and path[0] == "application":
            app = self.applications.setdefault(
                path[1], Application(name=path[1], kind="application")
            )
            if len(path) == 4 and path[2] == "protocol":
                app.protocol = path[3]
                return "parsed"
            if len(path) == 4 and path[2] == "destination-port":
                app.destination_port = path[3]
                return "parsed"
            return "ignored"
        if len(path) == 4 and path[0] == "application-set" and path[2] == "application":
            app = self.applications.setdefault(
                path[1], Application(name=path[1], kind="application_set")
            )
            app.members.append(path[3])
            return "parsed"
        return "unknown"

    def statement(self, path: list[str], deactivate: bool) -> str:
        if not path:
            return "unknown"
        top = path[0]
        if top in IGNORED_TOP:
            return "ignored"
        if top == "applications" and not deactivate:
            return self.application(path[1:])
        if top != "security" or len(path) < 2:
            return "ignored" if top == "applications" else "unknown"
        section = path[1]
        if section == "policies":
            if len(path) >= 3 and path[2] in (
                "default-policy",
                "policy-rematch",
                "pre-id-default-policy",
            ):
                return "ignored"
            return self.policy(path[2:], deactivate)
        if deactivate:
            return "ignored"
        if section == "address-book" and len(path) >= 4:
            return self.address(path[2], path[3:])
        if section == "zones":
            if len(path) >= 6 and path[2] == "security-zone" and path[4] == "address-book":
                return self.address(path[3], path[5:])
            return "ignored"
        if section in IGNORED_SECURITY:
            return "ignored"
        return "unknown"


def parse_set(text: str, file: str = "config.set") -> Config:
    builder = _Builder(file)
    stats = builder.stats
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        stats.total += 1
        tokens = tokenize(line)
        verb = tokens[0]
        if verb not in ("set", "deactivate"):
            stats.add_unknown(line)
            continue
        try:
            outcome = builder.statement(tokens[1:], deactivate=verb == "deactivate")
        except (IndexError, ValueError):
            outcome = "unknown"
        if outcome == "parsed":
            stats.parsed += 1
        elif outcome == "ignored":
            stats.ignored += 1
        else:
            stats.add_unknown(line)
    return Config(
        policies=list(builder.policies.values()),
        addresses=builder.addresses,
        applications=builder.applications,
        stats=stats,
    )
