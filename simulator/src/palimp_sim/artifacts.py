"""Artifact writers (spec section 5). Layouts are VSRX assumptions until confirmed."""

import csv
import io
from datetime import datetime, time, timedelta

from palimp_sim.junos import Policy, render_set
from palimp_sim.traffic import TrafficResult

RETAINED = 50  # rollback 0 to 49 (VSRX-6)
SD_ID = "junos@2636.1.1.1.2.129"  # VSRX-9


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
    return "\n".join(lines) + "\n"


def rollback_files(sim) -> dict[str, str]:
    files = {}
    for index in range(1, min(RETAINED, len(sim.commits))):
        commit = sim.commits[len(sim.commits) - 1 - index]
        files[f"rollbacks/rollback-{index:02d}.set"] = render_set(commit.config)
    return files


def hitcount_txt(sim, traffic: TrafficResult) -> str:
    policies = sim.config.ordered_policies()
    width = max([24] + [len(p.name) + 2 for p in policies])
    lines = [
        "Logical system: root-logical-system",
        f" {'Index':<8}{'From zone':<17}{'To zone':<18}{'Name':<{width}}{'Policy count':<14}Action",
    ]
    for index, policy in enumerate(policies, start=1):
        stats = traffic.policies.get(policy.uid)
        count = stats.hits_since_reset if stats else 0
        lines.append(
            f" {index:<8}{policy.from_zone:<17}{policy.to_zone:<18}"
            f"{policy.name:<{width}}{count:<14}Permit"
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


def rt_flow_log(sim, traffic: TrafficResult) -> tuple[str, dict[str, int]]:
    """Structured syslog RT_FLOW lines, and the number of lines per policy uid."""
    policies = _all_policies(sim)
    interface_of = {zone.name: f"{zone.interface}.0" for zone in sim.config.zones}
    host = sim.host_name
    sessions = sorted(
        traffic.sessions, key=lambda s: (s.day, s.second, s.policy_uid, s.flow_id, s.src_port)
    )
    entries: list[tuple[datetime, int, str]] = []
    counts: dict[str, int] = {}
    for number, session in enumerate(sessions):
        policy = policies[session.policy_uid]
        session_id = 40000 + number
        protocol_id = 6 if session.protocol == "tcp" else 17
        common = (
            f'source-address="{session.src_ip}" source-port="{session.src_port}" '
            f'destination-address="{session.dst_ip}" destination-port="{session.dst_port}" '
            f'connection-tag="0" service-name="{session.service}" '
            f'nat-source-address="{session.src_ip}" nat-source-port="{session.src_port}" '
            f'nat-destination-address="{session.dst_ip}" '
            f'nat-destination-port="{session.dst_port}" nat-connection-tag="0" '
            f'src-nat-rule-type="N/A" src-nat-rule-name="N/A" dst-nat-rule-type="N/A" '
            f'dst-nat-rule-name="N/A" protocol-id="{protocol_id}" '
            f'policy-name="{policy.name}" source-zone-name="{policy.from_zone}" '
            f'destination-zone-name="{policy.to_zone}" session-id="{session_id}"'
        )
        tail = (
            f'username="N/A" roles="N/A" '
            f'packet-incoming-interface="{interface_of[policy.from_zone]}" '
            f'application="UNKNOWN" nested-application="UNKNOWN" encrypted="UNKNOWN"'
        )
        start = timestamp(sim, session.day, session.second)
        millis = (session_id * 37) % 1000
        if session.log_init:
            text = (
                f"<14>1 {_iso(start, millis)} {host} RT_FLOW - RT_FLOW_SESSION_CREATE "
                f"[{SD_ID} {common} {tail}]"
            )
            entries.append((start, millis, text))
            counts[session.policy_uid] = counts.get(session.policy_uid, 0) + 1
        if session.log_close:
            end = start + timedelta(seconds=session.elapsed)
            reason = "TCP FIN" if session.protocol == "tcp" else "idle Timeout"
            stats = (
                f'packets-from-client="{session.packets_in}" '
                f'bytes-from-client="{session.bytes_in}" '
                f'packets-from-server="{session.packets_out}" '
                f'bytes-from-server="{session.bytes_out}" elapsed-time="{session.elapsed}"'
            )
            text = (
                f"<14>1 {_iso(end, millis)} {host} RT_FLOW - RT_FLOW_SESSION_CLOSE "
                f'[{SD_ID} reason="{reason}" {common} {stats} {tail}]'
            )
            entries.append((end, millis, text))
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
