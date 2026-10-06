"""Firewall configuration state and its rendering in Junos "set" format.

The rendering follows `show configuration | display set` as described in the
spec (section 5.1). Statement order and layout are assumptions VSRX-1, VSRX-3
and VSRX-12 until confirmed on a real vSRX.
"""

import copy
import ipaddress
from dataclasses import dataclass, field, replace

from palimp_sim.catalog import PREDEFINED_APPLICATIONS

ANY = "any"
ANY_APPLICATION = ("any", 0)
GLOBAL = "global"


@dataclass
class Policy:
    uid: str
    name: str
    from_zone: str
    to_zone: str
    sources: list[str]
    destinations: list[str]
    applications: list[str]
    log_init: bool = False
    log_close: bool = False
    description: str | None = None
    inactive: bool = False  # `deactivate` statement (VSRX-2)
    # Hard only. An annotation (`annotate`) shows in hierarchical output only
    # (VSRX-2, HIER-1c). A global policy has from_zone and to_zone "global"
    # and optional `match from-zone` / `match to-zone` lists (GLOBAL-1).
    annotation: str | None = None
    from_zones: list[str] = field(default_factory=list)
    to_zones: list[str] = field(default_factory=list)

    @property
    def is_global(self) -> bool:
        return self.from_zone == GLOBAL


@dataclass
class Zone:
    name: str
    role: str
    interface: str
    address: str


@dataclass
class Config:
    version: str
    host_name: str
    time_zone: str
    zones: list[Zone]
    logins: list[str] = field(default_factory=list)
    banner: str = "Authorized access only"
    syslog_hosts: list[str] = field(default_factory=list)
    snmp_community: str = "fm-ro-1"
    log_stream_host: str = "10.20.2.40"
    addresses: dict[str, str] = field(default_factory=dict)
    address_sets: dict[str, list[str]] = field(default_factory=dict)
    applications: dict[str, tuple[str, int]] = field(default_factory=dict)
    policies: list[Policy] = field(default_factory=list)

    def snapshot(self) -> "Config":
        """Independent copy (same result as deepcopy, much faster on large configs)."""
        clone = copy.copy(self)
        clone.zones = list(self.zones)  # Zone objects are never modified
        clone.logins = list(self.logins)
        clone.syslog_hosts = list(self.syslog_hosts)
        clone.addresses = dict(self.addresses)
        clone.address_sets = {name: list(members) for name, members in self.address_sets.items()}
        clone.applications = dict(self.applications)
        clone.policies = [
            replace(
                policy,
                sources=list(policy.sources),
                destinations=list(policy.destinations),
                applications=list(policy.applications),
                from_zones=list(policy.from_zones),
                to_zones=list(policy.to_zones),
            )
            for policy in self.policies
        ]
        return clone

    def policy(self, uid: str) -> Policy:
        return next(p for p in self.policies if p.uid == uid)

    def zone_pairs(self) -> list[tuple[str, str]]:
        """Zone pairs in order of first appearance (VSRX-3)."""
        pairs: list[tuple[str, str]] = []
        for policy in self.policies:
            pair = (policy.from_zone, policy.to_zone)
            if pair not in pairs:
                pairs.append(pair)
        return pairs

    def ordered_policies(self) -> list[Policy]:
        """Policies grouped by zone pair, keeping their order inside a pair.

        Global policies come last, as they are evaluated after the zone pair
        policies (GLOBAL-1).
        """
        pairs = [pair for pair in self.zone_pairs() if pair != (GLOBAL, GLOBAL)]
        pairs += [pair for pair in self.zone_pairs() if pair == (GLOBAL, GLOBAL)]
        return [
            policy
            for pair in pairs
            for policy in self.policies
            if (policy.from_zone, policy.to_zone) == pair
        ]

    def remove_unused_objects(self) -> None:
        used = {name for p in self.policies for name in p.sources + p.destinations}
        for set_name in list(self.address_sets):
            if set_name not in used:
                del self.address_sets[set_name]
        used |= {name for members in self.address_sets.values() for name in members}
        for name in list(self.addresses):
            if name not in used:
                del self.addresses[name]
        used_apps = {name for p in self.policies for name in p.applications}
        for name in list(self.applications):
            if name not in used_apps:
                del self.applications[name]

    def resolve_address(self, name: str) -> list[ipaddress.IPv4Network]:
        if name == ANY:
            return [ipaddress.IPv4Network("0.0.0.0/0")]
        if name in self.address_sets:
            return [
                net for member in self.address_sets[name] for net in self.resolve_address(member)
            ]
        return [ipaddress.IPv4Network(self.addresses[name])]

    def resolve_address_list(self, names: list[str]) -> list[ipaddress.IPv4Network]:
        return [net for name in names for net in self.resolve_address(name)]

    def resolve_application(self, name: str) -> tuple[str, int]:
        if name == ANY:
            return ANY_APPLICATION
        if name in PREDEFINED_APPLICATIONS:
            return PREDEFINED_APPLICATIONS[name]
        return self.applications[name]


def _scope(policy: Policy) -> str:
    """`global` or `from-zone A to-zone B` (GLOBAL-1)."""
    if policy.is_global:
        return GLOBAL
    return f"from-zone {policy.from_zone} to-zone {policy.to_zone}"


def _quote(text: str) -> str:
    return '"' + text.replace('"', "'") + '"'


def render_set(config: Config) -> str:
    lines = [f"set version {config.version}"]
    lines.append(f"set system host-name {config.host_name}")
    lines.append(f"set system time-zone {config.time_zone}")
    lines.append(f"set system login message {_quote(config.banner)}")
    for login in config.logins:
        lines.append(f"set system login user {login} class super-user")
    lines.append("set system services ssh")
    lines.append("set system services netconf ssh")
    for host in config.syslog_hosts:
        lines.append(f"set system syslog host {host} any notice")
    lines.append("set system syslog file messages any notice")
    lines.append("set security log mode stream")
    lines.append("set security log format sd-syslog")
    lines.append(f"set security log stream central host {config.log_stream_host}")
    for policy in config.ordered_policies():
        prefix = f"set security policies {_scope(policy)} policy {policy.name}"
        if policy.description:
            lines.append(f"{prefix} description {_quote(policy.description)}")
        for name in policy.sources:
            lines.append(f"{prefix} match source-address {name}")
        for name in policy.destinations:
            lines.append(f"{prefix} match destination-address {name}")
        for name in policy.applications:
            lines.append(f"{prefix} match application {name}")
        # display_set_global_policy_zones.txt: zone conditions after application.
        for zone in policy.from_zones:
            lines.append(f"{prefix} match from-zone {zone}")
        for zone in policy.to_zones:
            lines.append(f"{prefix} match to-zone {zone}")
        lines.append(f"{prefix} then permit")
        if policy.log_init:
            lines.append(f"{prefix} then log session-init")
        if policy.log_close:
            lines.append(f"{prefix} then log session-close")
        if policy.inactive:
            # display_set_deactivate.txt: the deactivate statement follows the
            # set statements of the deactivated element.
            lines.append(f"deactivate security policies {_scope(policy)} policy {policy.name}")
    lines.append("set security policies default-policy deny-all")
    for zone in config.zones:
        base = f"set security zones security-zone {zone.name}"
        lines.append(f"{base} interfaces {zone.interface}.0")
        if zone.role != "internet":
            lines.append(f"{base} host-inbound-traffic system-services ping")
    for name, prefix in config.addresses.items():
        lines.append(f"set security address-book global address {name} {prefix}")
    for name, members in config.address_sets.items():
        for member in members:
            lines.append(f"set security address-book global address-set {name} address {member}")
    for zone in config.zones:
        lines.append(f"set interfaces {zone.interface} unit 0 family inet address {zone.address}")
    lines.append(f"set snmp community {config.snmp_community} authorization read-only")
    lines.append("set routing-options static route 0.0.0.0/0 next-hop 192.0.2.254")
    for name, (protocol, port) in config.applications.items():
        lines.append(f"set applications application {name} protocol {protocol}")
        lines.append(f"set applications application {name} destination-port {port}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- hierarchical
# `show configuration` output (HIER-1a), Hard only (decision 0035). Layout from
# the samples in tests/fixtures/junos_docs/hier_*.txt: 4 spaces per level,
# `;` after each statement, lists as `[ a b ]` (hier_global_policy_zones.txt),
# `inactive:` before a deactivated statement (hier_inactive.txt, HIER-1b) and
# annotations as `/* ... */` on the line before (hier_annotations.txt,
# HIER-1c). Quoting of descriptions is not shown in any sample (HIER-1d): a
# string is quoted when it holds a space or a special character.

_PLAIN = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_./:+@")


def _value(text: str) -> str:
    if text and all(char in _PLAIN for char in text):
        return text
    return _quote(text)


def _values(names: list[str]) -> str:
    return names[0] if len(names) == 1 else "[ " + " ".join(names) + " ]"


class _Tree:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.depth = 0

    def leaf(self, text: str) -> None:
        self.lines.append("    " * self.depth + text + ";")

    def open(self, text: str, inactive: bool = False, note: str | None = None) -> None:
        if note:
            self.lines.append("    " * self.depth + f"/* {note} */")
        prefix = "inactive: " if inactive else ""
        self.lines.append("    " * self.depth + f"{prefix}{text} {{")
        self.depth += 1

    def close(self) -> None:
        self.depth -= 1
        self.lines.append("    " * self.depth + "}")


def _policy_block(tree: _Tree, policy: Policy) -> None:
    tree.open(f"policy {policy.name}", policy.inactive, policy.annotation)
    if policy.description:
        tree.leaf(f"description {_value(policy.description)}")
    tree.open("match")
    tree.leaf(f"source-address {_values(policy.sources)}")
    tree.leaf(f"destination-address {_values(policy.destinations)}")
    tree.leaf(f"application {_values(policy.applications)}")
    if policy.from_zones:
        tree.leaf(f"from-zone {_values(policy.from_zones)}")
    if policy.to_zones:
        tree.leaf(f"to-zone {_values(policy.to_zones)}")
    tree.close()
    tree.open("then")
    tree.leaf("permit")
    if policy.log_init or policy.log_close:
        tree.open("log")
        if policy.log_init:
            tree.leaf("session-init")
        if policy.log_close:
            tree.leaf("session-close")
        tree.close()
    tree.close()
    tree.close()


def render_hierarchical(config: Config, header: str | None = None) -> str:
    """The configuration as `show configuration` prints it.

    `header` is the `## Last commit: <date> <zone> by <user>` line printed at
    the top of `show configuration` (VSRX-8, documentation text).
    """
    tree = _Tree()
    if header:
        tree.lines.append(header)
    tree.leaf(f"version {config.version}")
    tree.open("system")
    tree.leaf(f"host-name {config.host_name}")
    tree.leaf(f"time-zone {config.time_zone}")
    tree.open("login")
    tree.leaf(f"message {_quote(config.banner)}")
    for login in config.logins:
        tree.open(f"user {login}")
        tree.leaf("class super-user")
        tree.close()
    tree.close()
    tree.open("services")
    tree.leaf("ssh")
    tree.open("netconf")
    tree.leaf("ssh")
    tree.close()
    tree.close()
    tree.open("syslog")
    for host in config.syslog_hosts:
        tree.open(f"host {host}")
        tree.leaf("any notice")
        tree.close()
    tree.open("file messages")
    tree.leaf("any notice")
    tree.close()
    tree.close()
    tree.close()
    tree.open("interfaces")
    for zone in config.zones:
        tree.open(zone.interface)
        tree.open("unit 0")
        tree.open("family inet")
        tree.leaf(f"address {zone.address}")
        tree.close()
        tree.close()
        tree.close()
    tree.close()
    tree.open("snmp")
    tree.open(f"community {config.snmp_community}")
    tree.leaf("authorization read-only")
    tree.close()
    tree.close()
    tree.open("routing-options")
    tree.open("static")
    tree.leaf("route 0.0.0.0/0 next-hop 192.0.2.254")
    tree.close()
    tree.close()
    tree.open("security")
    tree.open("address-book")
    tree.open("global")
    for name, prefix in config.addresses.items():
        tree.leaf(f"address {name} {prefix}")
    for name, members in config.address_sets.items():
        tree.open(f"address-set {name}")
        for member in members:
            tree.leaf(f"address {member}")
        tree.close()
    tree.close()
    tree.close()
    tree.open("log")
    tree.leaf("mode stream")
    tree.leaf("format sd-syslog")
    tree.open("stream central")
    tree.open("host")
    tree.leaf(config.log_stream_host)
    tree.close()
    tree.close()
    tree.close()
    tree.open("policies")
    current = None
    for policy in config.ordered_policies():
        scope = _scope(policy)
        if scope != current:
            if current is not None:
                tree.close()
            tree.open(scope)
            current = scope
        _policy_block(tree, policy)
    if current is not None:
        tree.close()
    tree.open("default-policy")
    tree.leaf("deny-all")
    tree.close()
    tree.close()
    tree.open("zones")
    for zone in config.zones:
        tree.open(f"security-zone {zone.name}")
        if zone.role != "internet":
            tree.open("host-inbound-traffic")
            tree.open("system-services")
            tree.leaf("ping")
            tree.close()
            tree.close()
        tree.open("interfaces")
        tree.leaf(f"{zone.interface}.0")
        tree.close()
        tree.close()
    tree.close()
    tree.close()
    tree.open("applications")
    for name, (protocol, port) in config.applications.items():
        tree.open(f"application {name}")
        tree.leaf(f"protocol {protocol}")
        tree.leaf(f"destination-port {port}")
        tree.close()
    tree.close()
    return "\n".join(tree.lines) + "\n"
