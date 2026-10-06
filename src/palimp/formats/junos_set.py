"""Reader for `show configuration | display set` output (Junos "set" format).

The model builder here is shared with the hierarchical reader
(palimp.formats.junos_hier), so both formats give the same model.

Only security policies, address books and applications are modeled. Lines from
other hierarchies are counted as ignored. Lines that cannot be understood are
counted as unknown and sampled in the stats; they never stop the parse.

Format assumptions to confirm on a real vSRX: VSRX-1 (one statement per line,
quoted descriptions), VSRX-2 (deactivate lines), VSRX-3 (order of appearance
is evaluation order within a zone pair).

A saved terminal capture is accepted (gap G1): prompt and banner lines are
ignored. After an `[edit X Y]` banner, statements printed relative to that
level (`show | display set relative`, gap G2) get the `X Y` prefix back.
"""

import re

from palimp.formats.terminal import edit_path, is_terminal_noise
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


def policy_path(policy: Policy) -> list[str]:
    """Where the policy sits under `security policies`."""
    return ["from-zone", policy.from_zone, "to-zone", policy.to_zone, "policy", policy.name]


def tokenize(line: str) -> list[str]:
    """Split a set line on spaces, keeping double-quoted strings as one token."""
    return [m.group(1) if m.group(1) is not None else m.group(2) for m in TOKEN.finditer(line)]


class _Builder:
    def __init__(self, file: str) -> None:
        self.stats = ParseStats(file=file)
        self.policies: dict[tuple[str, str, str], Policy] = {}
        self.addresses: dict[str, AddressObject] = {}
        self.applications: dict[str, Application] = {}
        # Deactivated containers above the policies (decision 0034): path -> statement.
        self.scopes: list[tuple[list[str], str]] = []

    def record(self, outcome: str, line: str) -> None:
        if outcome == "parsed":
            self.stats.parsed += 1
        elif outcome == "ignored":
            self.stats.ignored += 1
        else:
            self.stats.add_unknown(line)

    def note(self, text: str) -> None:
        if text not in self.stats.notes:
            self.stats.notes.append(text)

    def annotate(self, path: list[str], text: str) -> str:
        """An admin's `/* ... */` note on the statement at PATH (hierarchical format only).

        Kept when it is on a policy or on a statement inside one; other
        annotations (zone pairs, objects, other hierarchies) are not used.
        """
        rest = path[2:]
        if (
            path[:2] == ["security", "policies"]
            and len(rest) >= 6
            and rest[0] == "from-zone"
            and rest[2] == "to-zone"
            and rest[4] == "policy"
        ):
            key = (rest[1], rest[3], rest[5])
            policy = self.policies.get(key)
            if policy is None:
                policy = Policy(
                    from_zone=key[0], to_zone=key[1], name=key[2], position=len(self.policies)
                )
                self.policies[key] = policy
            policy.annotations.append(text)
            return "parsed"
        return "ignored"

    # Each handler returns "parsed", "ignored" or "unknown".

    def deactivate_scope(self, path: list[str]) -> str:
        """`deactivate` on a container of policies: every policy under it matches nothing.

        Junos ignores a deactivated statement with its whole subtree at commit
        (decision 0034). Applied when the model is built, whatever the line order.
        """
        statement = " ".join(path)
        self.scopes.append((path[2:], statement))
        self.note(f"deactivate {statement}: every policy under it is read as deactivated")
        return "parsed"

    def config(self) -> Config:
        for scope, statement in self.scopes:
            for policy in self.policies.values():
                if policy_path(policy)[: len(scope)] == scope:
                    policy.deactivated = True
                    shown = f"deactivated with {statement}"
                    if shown not in policy.deactivated_statements:
                        policy.deactivated_statements.append(shown)
        return Config(
            policies=list(self.policies.values()),
            addresses=self.addresses,
            applications=self.applications,
            stats=self.stats,
        )

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
        if path[0] in ("attach", "description"):
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
        for marker in ("apply-groups", "apply-groups-except"):
            if marker in path and path[0] != "groups":
                at = path.index(marker)
                where = " ".join(path[:at]) or "top level"
                use = f"{where}: {marker} {' '.join(path[at + 1 :])}".strip()
                if use not in self.stats.apply_groups:
                    self.stats.apply_groups.append(use)
                return "ignored"
        top = path[0]
        if top in IGNORED_TOP:
            return "ignored"
        if top == "applications" and not deactivate:
            return self.application(path[1:])
        if top == "security" and len(path) == 1 and deactivate:
            return self.deactivate_scope(path)
        if top != "security" or len(path) < 2:
            return "ignored" if top == "applications" else "unknown"
        section = path[1]
        if section == "policies":
            if deactivate and (len(path) <= 2 or (len(path) == 6 and path[2] == "from-zone")):
                return self.deactivate_scope(path)
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
    level: list[str] = []
    stats.format = "set"
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        stats.total += 1
        banner = edit_path(line)
        if banner is not None:
            level = tokenize(banner)
        if is_terminal_noise(line):
            stats.ignored += 1
            continue
        tokens = tokenize(line)
        verb = tokens[0]
        if verb not in ("set", "deactivate"):
            stats.add_unknown(line)
            continue
        path = tokens[1:]
        if level and path[: len(level)] != level:
            path = level + path
            stats.format = "set relative"
        try:
            outcome = builder.statement(path, deactivate=verb == "deactivate")
        except (IndexError, ValueError):
            outcome = "unknown"
        builder.record(outcome, line)
    return builder.config()
