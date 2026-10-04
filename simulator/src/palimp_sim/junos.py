"""Firewall configuration state and its rendering in Junos "set" format.

The rendering follows `show configuration | display set` as described in the
spec (section 5.1). Statement order and layout are assumptions VSRX-1, VSRX-3
and VSRX-12 until confirmed on a real vSRX.
"""

import copy
import ipaddress
from dataclasses import dataclass, field

from palimp_sim.catalog import PREDEFINED_APPLICATIONS

ANY = "any"


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
        return copy.deepcopy(self)

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
        """Policies grouped by zone pair, keeping their order inside a pair."""
        return [
            policy
            for pair in self.zone_pairs()
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
        if name in PREDEFINED_APPLICATIONS:
            return PREDEFINED_APPLICATIONS[name]
        return self.applications[name]


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
        prefix = (
            f"set security policies from-zone {policy.from_zone} "
            f"to-zone {policy.to_zone} policy {policy.name}"
        )
        if policy.description:
            lines.append(f"{prefix} description {_quote(policy.description)}")
        for name in policy.sources:
            lines.append(f"{prefix} match source-address {name}")
        for name in policy.destinations:
            lines.append(f"{prefix} match destination-address {name}")
        for name in policy.applications:
            lines.append(f"{prefix} match application {name}")
        lines.append(f"{prefix} then permit")
        if policy.log_init:
            lines.append(f"{prefix} then log session-init")
        if policy.log_close:
            lines.append(f"{prefix} then log session-close")
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
