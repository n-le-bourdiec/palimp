"""Traffic model (spec section 4.9).

Every day, each active flow produces a number of sessions. Each session is
attributed to the first matching policy of its zone pair in the configuration
in force that day. This drives hit counts, session logs and the ground truth
"live" status.
"""

import ipaddress
from dataclasses import dataclass, field

from palimp_sim.catalog import service_port
from palimp_sim.junos import ANY_APPLICATION, Config
from palimp_sim.model import Flow
from palimp_sim.rng import Rng

Network = ipaddress.IPv4Network


@dataclass
class PolicyStats:
    hits_since_reset: int = 0
    hits_total: int = 0
    first_hit: int | None = None
    last_hit: int | None = None


@dataclass
class Session:
    day: int
    second: int
    policy_uid: str
    flow_id: str
    src_ip: str
    src_port: int
    dst_ip: str
    dst_port: int
    protocol: str
    service: str
    elapsed: int
    packets_in: int
    bytes_in: int
    packets_out: int
    bytes_out: int
    log_init: bool
    log_close: bool


@dataclass
class TrafficResult:
    policies: dict[str, PolicyStats] = field(default_factory=dict)
    flow_last_use: dict[str, int] = field(default_factory=dict)
    sessions: list[Session] = field(default_factory=list)


class Matcher:
    """First match lookup for one configuration version."""

    def __init__(self, config: Config, zone_of_role: dict[str, str]) -> None:
        self.zone_of_role = zone_of_role
        self.by_pair: dict[tuple[str, str], list] = {}
        self.policies = {p.uid: p for p in config.policies}
        for policy in config.ordered_policies():
            if policy.inactive:
                continue
            entry = (
                policy.uid,
                config.resolve_address_list(policy.sources),
                config.resolve_address_list(policy.destinations),
                {config.resolve_application(name) for name in policy.applications},
            )
            self.by_pair.setdefault((policy.from_zone, policy.to_zone), []).append(entry)
        self.cache: dict[tuple, str | None] = {}

    def match(self, flow: Flow, src: str, dst: str, service: tuple[str, int]) -> str | None:
        key = (flow.flow_id, src, dst, service)
        if key not in self.cache:
            pair = (self.zone_of_role[flow.src.zone_role], self.zone_of_role[flow.dst.zone_role])
            src_net, dst_net = Network(src), Network(dst)
            found = None
            for uid, sources, destinations, services in self.by_pair.get(pair, []):
                if (
                    (service in services or ANY_APPLICATION in services)
                    and any(src_net.subnet_of(n) for n in sources)
                    and any(dst_net.subnet_of(n) for n in destinations)
                ):
                    found = uid
                    break
            self.cache[key] = found
        return self.cache[key]


def sessions_for_day(flow: Flow, day: int, weekday: int, rng: Rng) -> int:
    base = flow.template.base
    schedule = flow.template.schedule
    if flow.period is not None:
        return base if flow.runs_on(day) else 0
    if schedule == "nightly":
        return base
    if schedule == "always":
        return round(base * rng.uniform(0.85, 1.15))
    if weekday >= 5:
        return round(base * rng.uniform(0.0, 0.05))
    return round(base * rng.uniform(0.7, 1.3))


def _host_in(prefix: str, rng: Rng, server_ips: list[str]) -> str:
    network = Network(prefix)
    if network.prefixlen == 32:
        return str(network.network_address)
    if network.prefixlen == 0:
        return f"198.51.100.{rng.randint(2, 250)}"
    inside = [ip for ip in server_ips if ipaddress.IPv4Address(ip) in network]
    if inside:
        return rng.choice(inside)
    return str(network.network_address + rng.randint(10, min(250, network.num_addresses - 2)))


def _second_of_day(schedule: str, rng: Rng) -> int:
    if schedule == "nightly":
        return rng.randint(3600, 4 * 3600)
    if schedule == "business":
        return rng.randint(8 * 3600, 18 * 3600)
    return rng.randint(0, 86399)


def simulate(sim, rng: Rng) -> TrafficResult:
    """Play traffic over the whole timeline of a finished Simulation."""
    level = sim.level
    total = sim.total_days
    reset_day = sim.hit_reset_day if sim.hit_reset_day is not None else 0
    # `clear security policies hit-count from-zone A to-zone B` (VSRX-7c):
    # counters of one zone pair restart later than the others.
    pair_resets = getattr(sim, "pair_resets", {})
    log_start = total - level.log_window_days
    zone_of_role = dict(sim.zone_names)
    result = TrafficResult()
    commits = sim.commits
    pointer = -1
    matcher = None
    rng_count = rng.derive("counts")
    rng_log = rng.derive("logs")

    for day in range(total):
        # A commit applies from the day after it, so no session on the commit
        # day can be attributed to a policy committed later that day.
        while pointer + 1 < len(commits) and commits[pointer + 1].day < day:
            pointer += 1
            matcher = Matcher(commits[pointer].config, zone_of_role)
        if matcher is None:
            continue
        weekday = sim.date(day).weekday()
        server_ips = [
            s.ip
            for s in sim.servers.values()
            if s.active_from <= day and (s.active_to is None or day < s.active_to)
        ]
        candidates: dict[str, list] = {}
        for flow in sim.flows.values():
            if not flow.active(day):
                continue
            count = sessions_for_day(flow, day, weekday, rng_count)
            parts = [
                (src, dst, service)
                for src in flow.src.prefixes
                for dst in flow.dst.prefixes
                for service in flow.template.services
            ]
            share, extra = divmod(count, len(parts))
            for index, (src, dst, service) in enumerate(parts):
                part_count = share + (1 if index < extra else 0)
                if part_count == 0:
                    continue
                port = service_port(service)
                uid = matcher.match(flow, src, dst, port)
                if uid is None:
                    continue
                stats = result.policies.setdefault(uid, PolicyStats())
                stats.hits_total += part_count
                if pair_resets:
                    policy = matcher.policies[uid]
                    pair = (policy.from_zone, policy.to_zone)
                    counted = day >= max(reset_day, pair_resets.get(pair, 0))
                else:
                    counted = day >= reset_day
                if counted:
                    stats.hits_since_reset += part_count
                stats.first_hit = day if stats.first_hit is None else stats.first_hit
                stats.last_hit = day
                result.flow_last_use[flow.flow_id] = day
                if day >= log_start:
                    candidates.setdefault(uid, []).append((flow, src, dst, service, port))
        for uid in sorted(candidates):
            policy = matcher.policies[uid]
            if not (policy.log_init or policy.log_close):
                continue
            for _ in range(level.log_samples_per_policy_day):
                flow, src, dst, service, (protocol, port) = rng_log.choice(candidates[uid])
                tcp = protocol == "tcp"
                result.sessions.append(
                    Session(
                        day=day,
                        second=_second_of_day(flow.template.schedule, rng_log),
                        policy_uid=uid,
                        flow_id=flow.flow_id,
                        src_ip=_host_in(src, rng_log, server_ips),
                        src_port=rng_log.randint(1024, 65535),
                        dst_ip=_host_in(dst, rng_log, server_ips),
                        dst_port=port,
                        protocol=protocol,
                        service=service,
                        elapsed=rng_log.randint(1, 300) if tcp else rng_log.randint(1, 60),
                        packets_in=rng_log.randint(3, 40),
                        bytes_in=rng_log.randint(200, 20000),
                        packets_out=rng_log.randint(3, 60),
                        bytes_out=rng_log.randint(200, 90000),
                        log_init=policy.log_init,
                        log_close=policy.log_close,
                    )
                )
    return result


def live_policies(sim) -> dict[str, list[str]]:
    """Policies of the final config carrying at least one flow active at the end."""
    last_day = sim.total_days - 1
    config = sim.commits[-1].config
    matcher = Matcher(config, dict(sim.zone_names))
    carried: dict[str, list[str]] = {}
    for flow in sim.flows.values():
        if not flow.active(last_day):
            continue
        for src in flow.src.prefixes:
            for dst in flow.dst.prefixes:
                for service in flow.template.services:
                    uid = matcher.match(flow, src, dst, service_port(service))
                    if uid and flow.flow_id not in carried.setdefault(uid, []):
                        carried[uid].append(flow.flow_id)
    return carried
