"""Artifact writers (spec section 5).

Layouts follow the samples in tests/fixtures/junos_docs/ (see
docs/format-assumptions.md); simulator/tests/test_formats.py checks them.
"""

import csv
import io
import ipaddress
from datetime import datetime, time, timedelta

from palimp_sim.junos import Policy, render_hierarchical, render_set
from palimp_sim.rng import Rng
from palimp_sim.traffic import TrafficResult

RETAINED = 50  # rollback 0 to 49 (VSRX-6)
SD_ID = "junos@2636.1.1.1.2.129"  # VSRX-9b, unverified: samples show .34 and .39
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def commit_index(sim, seq: int) -> int:
    """Position of a commit in `show system commit` (0 is the active config)."""
    return len(sim.commits) - 1 - seq


def timestamp(sim, day: int, second: int) -> datetime:
    return datetime.combine(sim.date(day), time()) + timedelta(seconds=second)


def commits_txt(sim) -> str:
    lines = []
    for index, commit in enumerate(reversed(sim.commits[-RETAINED:])):
        moment = timestamp(sim, commit.day, commit.second)
        zone = sim.level.device_time_zone
        lines.append(
            f"{index:<4}{moment:%Y-%m-%d %H:%M:%S} {zone} by {commit.login} via {commit.client}"
        )
        if commit.comment:
            lines.append(f"    {commit.comment}")
    if sim.level.rescue_line:
        # Rescue configuration saved after the first commit of the history,
        # printed last as in the documentation sample (VSRX-4b).
        first = sim.commits[0]
        moment = timestamp(sim, first.day, first.second + 600)
        zone = sim.level.device_time_zone
        lines.append(f"rescue  {moment:%Y-%m-%d %H:%M:%S} {zone} by root via other")
    return "\n".join(lines) + "\n"


def render_config(sim, config, last: bool = False) -> str:
    """The configuration in the scenario's format (decision 0035).

    File names stay `config.set` and `rollback-NN.set` whatever the format
    (the ground truth `artifact` values name them). The hierarchical active
    configuration starts with the `## Last commit:` header of `show
    configuration` (VSRX-8); whether rollbacks carry a header is not shown in
    the documentation (HIER-1e), so they have none.
    """
    if sim.level.config_format != "hierarchical":
        return render_set(config)
    header = None
    if last:
        commit = sim.commits[-1]
        moment = timestamp(sim, commit.day, commit.second)
        zone = sim.level.device_time_zone
        header = f"## Last commit: {moment:%Y-%m-%d %H:%M:%S} {zone} by {commit.login}"
    return render_hierarchical(config, header)


def rollback_files(sim) -> dict[str, str]:
    files = {}
    for index in range(1, min(RETAINED, len(sim.commits))):
        commit = sim.commits[len(sim.commits) - 1 - index]
        files[f"rollbacks/rollback-{index:02d}.set"] = render_config(sim, commit.config)
    return files


def hitcount_txt(sim, traffic: TrafficResult, rng: Rng) -> str:
    """`show security policies hit-count` (VSRX-7).

    Without options the device lists rows in random order and `Index` is a
    line number (VSRX-7b), so rows are shuffled and numbered from 1.
    Deactivated policies are not installed, so they are not listed (VSRX-2b,
    unverified).
    """
    policies = rng.shuffled([p for p in sim.config.ordered_policies() if not p.inactive])
    counts = []
    for policy in policies:
        stats = traffic.policies.get(policy.uid)
        counts.append(stats.hits_since_reset if stats else 0)
    zones = max([len(p.from_zone) for p in policies] + [len(p.to_zone) for p in policies])
    names = max(len(p.name) for p in policies)
    if sim.level.hitcount_layout == "legacy":
        # hitcount_legacy.txt: lowercase header, no Action column, footer.
        zone_width = max(13, zones + 2)
        name_width = max(16, names + 2)
        lines = ["index   from zone    to zone       name       policy count"]
        for index, (policy, count) in enumerate(zip(policies, counts, strict=True), start=1):
            lines.append(
                f" {index:<8}{policy.from_zone:<{zone_width}}{policy.to_zone:<{zone_width}}"
                f"{policy.name:<{name_width}}{count}"
            )
        lines += ["", f"Number of policy: {len(policies)}"]
        return "\n".join(lines) + "\n"
    # hitcount_logical_system.txt: column widths of the documentation header.
    zone_width = max(17, zones + 2)
    name_width = max(22, names + 2)
    lines = [
        "Logical system: root-logical-system",
        f"{'Index':<7}{'From zone':<{zone_width}}{'To zone':<{zone_width}}"
        f"{'Name':<{name_width}}{'Policy count':<14}Action",
    ]
    for index, (policy, count) in enumerate(zip(policies, counts, strict=True), start=1):
        lines.append(
            f"{index:<7}{policy.from_zone:<{zone_width}}{policy.to_zone:<{zone_width}}"
            f"{policy.name:<{name_width}}{count:<14}Permit"
        )
    return "\n".join(lines) + "\n"


def _all_policies(sim) -> dict[str, Policy]:
    policies: dict[str, Policy] = {}
    for commit in sim.commits:
        for policy in commit.config.policies:
            policies.setdefault(policy.uid, policy)
    return policies


def _iso(moment: datetime, millis: int) -> str:
    return f"{moment:%Y-%m-%dT%H:%M:%S}.{millis:03d}Z"


def _bsd(moment: datetime) -> str:
    """Syslog server timestamp, `Sep 06 16:54:22` (rt_flow_structured_12.3_remote.txt)."""
    return f"{MONTHS[moment.month - 1]} {moment:%d %H:%M:%S}"


# Attributes after `encrypted` in the 22.2R1 templates (VSRX-9c,
# syslog_explorer_rt_flow_session_*.txt). No published line shows their
# values: "N/A" is an assumption.
EXTRA_22_2 = {
    "CREATE": (
        "application-category application-sub-category application-risk "
        "application-characteristics src-vrf-grp dst-vrf-grp tunnel-inspection "
        "tunnel-inspection-policy-set source-tenant destination-service"
    ).split(),
    "CLOSE": (
        "application-category application-sub-category application-risk "
        "application-characteristics secure-web-proxy-session-type peer-session-id "
        "peer-source-address peer-source-port peer-destination-address "
        "peer-destination-port hostname src-vrf-grp dst-vrf-grp tunnel-inspection "
        "tunnel-inspection-policy-set session-flag source-tenant destination-service"
    ).split(),
}


def _attributes(kind: str, release: str, values: dict[str, str]) -> list[tuple[str, str]]:
    """Ordered RT_FLOW attributes of one message for a release (VSRX-9c).

    "12.x" follows rt_flow_structured_12.1x47.txt; "pre-22.2" and "22.2"
    follow the 22.2R1 templates (the first one stops at `encrypted`).
    """
    old = release == "12.x"
    names = ["reason"] if kind == "CLOSE" else []
    names += "source-address source-port destination-address destination-port".split()
    names += [] if old else ["connection-tag"]
    names += "service-name nat-source-address nat-source-port".split()
    names += "nat-destination-address nat-destination-port".split()
    if old:
        names += "src-nat-rule-name dst-nat-rule-name".split()
    else:
        names += "nat-connection-tag src-nat-rule-type src-nat-rule-name".split()
        names += "dst-nat-rule-type dst-nat-rule-name".split()
    names += "protocol-id policy-name source-zone-name destination-zone-name".split()
    names += ["session-id-32" if old else "session-id"]
    if kind == "CREATE":
        names += "username roles packet-incoming-interface".split()
        names += [] if old else "application nested-application encrypted".split()
    else:
        names += "packets-from-client bytes-from-client packets-from-server".split()
        names += "bytes-from-server elapsed-time application nested-application".split()
        names += "username roles packet-incoming-interface".split()
        names += [] if old else ["encrypted"]
    if release == "22.2":
        names += EXTRA_22_2[kind]
    rule = "None" if old else "N/A"
    defaults = {
        "connection-tag": "0",
        "nat-connection-tag": "0",
        "src-nat-rule-name": rule,
        "dst-nat-rule-name": rule,
        "session-id-32": values.get("session-id", ""),
        "application": "UNKNOWN",
        "nested-application": "UNKNOWN",
        "encrypted": "UNKNOWN",
    }
    return [(name, values.get(name, defaults.get(name, "N/A"))) for name in names]


def _source_address(sim) -> str:
    """Address the device sends logs from: its interface toward the collector."""
    collector = ipaddress.IPv4Address(sim.config.log_stream_host)
    for zone in sim.config.zones:
        interface = ipaddress.IPv4Interface(zone.address)
        if collector in interface.network:
            return str(interface.ip)
    return str(ipaddress.IPv4Interface(sim.config.zones[0].address).ip)


def rt_flow_log(sim, traffic: TrafficResult, skew: int = 0) -> tuple[str, dict[str, int]]:
    """Structured syslog RT_FLOW lines, and the number of lines per policy uid.

    `log_collection="device"` writes lines as `show security log file` prints
    them (`<14>1 ...`, rt_flow_structured_12.1x47.txt). "syslog-server" writes
    them as a remote server stores them: server timestamp and device address
    first, no `<PRI>` (rt_flow_structured_12.3_remote.txt, VSRX-9d). The
    server clock is `skew` seconds ahead of the device clock (negative:
    behind).
    """
    policies = _all_policies(sim)
    interface_of = {zone.name: f"{zone.interface}.0" for zone in sim.config.zones}
    host = sim.host_name
    release = sim.level.log_release
    server = sim.level.log_collection == "syslog-server"
    source = _source_address(sim)
    sessions = sorted(
        traffic.sessions, key=lambda s: (s.day, s.second, s.policy_uid, s.flow_id, s.src_port)
    )
    entries: list[tuple[datetime, int, str]] = []
    counts: dict[str, int] = {}

    def emit(kind: str, moment: datetime, millis: int, values: dict[str, str]) -> None:
        pairs = " ".join(f'{k}="{v}"' for k, v in _attributes(kind, release, values))
        body = f"{_iso(moment, millis)} {host} RT_FLOW - RT_FLOW_SESSION_{kind} [{SD_ID} {pairs}]"
        prefix = f"{_bsd(moment + timedelta(seconds=skew))} {source} 1" if server else "<14>1"
        entries.append((moment, millis, f"{prefix} {body}"))

    for number, session in enumerate(sessions):
        policy = policies[session.policy_uid]
        # The name in force that day (a later rename does not rewrite old
        # lines) and the real zones (a global policy has none of its own).
        name = session.policy_name or policy.name
        from_zone = session.from_zone or policy.from_zone
        to_zone = session.to_zone or policy.to_zone
        session_id = 40000 + number
        values = {
            "source-address": session.src_ip,
            "source-port": str(session.src_port),
            "destination-address": session.dst_ip,
            "destination-port": str(session.dst_port),
            "service-name": session.service,
            "nat-source-address": session.src_ip,
            "nat-source-port": str(session.src_port),
            "nat-destination-address": session.dst_ip,
            "nat-destination-port": str(session.dst_port),
            "protocol-id": "6" if session.protocol == "tcp" else "17",
            "policy-name": name,
            "source-zone-name": from_zone,
            "destination-zone-name": to_zone,
            "session-id": str(session_id),
            "packet-incoming-interface": interface_of[from_zone],
        }
        start = timestamp(sim, session.day, session.second)
        millis = (session_id * 37) % 1000
        if session.log_init:
            emit("CREATE", start, millis, values)
            counts[session.policy_uid] = counts.get(session.policy_uid, 0) + 1
        if session.log_close:
            values |= {
                "reason": "TCP FIN" if session.protocol == "tcp" else "idle Timeout",
                "packets-from-client": str(session.packets_in),
                "bytes-from-client": str(session.bytes_in),
                "packets-from-server": str(session.packets_out),
                "bytes-from-server": str(session.bytes_out),
                "elapsed-time": str(session.elapsed),
            }
            if session.unanswered:
                # Nothing answers (VSRX-15): the session ages out, the server
                # side stays empty. The reason text is an assumption.
                values |= {
                    "reason": "idle Timeout",
                    "packets-from-client": "1",
                    "bytes-from-client": "60" if session.protocol == "tcp" else "76",
                    "packets-from-server": "0",
                    "bytes-from-server": "0",
                }
            emit("CLOSE", start + timedelta(seconds=session.elapsed), millis, values)
            counts[session.policy_uid] = counts.get(session.policy_uid, 0) + 1
    entries.sort(key=lambda e: (e[0], e[1], e[2]))
    return "".join(text + "\n" for _, _, text in entries), counts


def tickets_csv(sim) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            "ticket_id",
            "opened",
            "closed",
            "status",
            "requester",
            "assignee",
            "summary",
            "category",
            "related_ci",
        ]
    )
    for ticket in sorted(sim.tickets, key=lambda t: (t.opened, t.ticket_id)):
        if not ticket.exported:
            continue
        writer.writerow(
            [
                ticket.ticket_id,
                sim.date(ticket.opened).isoformat(),
                sim.date(ticket.closed).isoformat(),
                ticket.status,
                ticket.requester,
                ticket.assignee,
                ticket.summary,
                ticket.category,
                ticket.related_ci,
            ]
        )
    return buffer.getvalue()
