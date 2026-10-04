"""Reader for RT_FLOW session logs (VSRX-9, VSRX-10).

Two message formats are accepted, each as written by the device or as stored
by a syslog server (gap G8), which puts its own timestamp and host in front
and drops the `<PRI>`:

    <14>1 2026-09-14T08:12:44.311Z fw-01 RT_FLOW - RT_FLOW_SESSION_CLOSE [junos@2636... k="v" ...]
    Sep 06 16:54:22 10.0.0.5 1 2010-09-06T04:24:22.094 fw-01 RT_FLOW - RT_FLOW_SESSION_CLOSE [...]
    Sep 06 15:22:29 10.0.0.5 Sep 6 02:52:30 RT_FLOW: RT_FLOW_SESSION_CREATE: session created ...

Structured lines may carry the standard text after `]` (gap G9). Logical
system variants (`RT_FLOW_SESSION_CREATE_LS`, gap G7) count as their base
type. `session-id-32` (releases around 12.x) is read as `session-id`.

Standard (unstructured) messages (gap G10) are positional and their field list
grows with the release, so only the fields palimp needs are read, anchored on
the protocol number that precedes the policy name:
`... PROTO POLICY FROM-ZONE TO-ZONE SESSION-ID ...` for CREATE and CLOSE, and
`... PROTO(ICMP-TYPE) POLICY FROM-ZONE TO-ZONE ...` for DENY. Their syslog
timestamp has no year: pass `year` to keep first and last seen times; without
it the events are counted and their times left unset.

Only a per-policy summary is kept (counts, first and last timestamps). Lines
that are not RT_FLOW messages (other daemons, `last message repeated`) are
ignored.
"""

import re
from dataclasses import dataclass
from datetime import datetime

from palimp.formats.terminal import is_terminal_noise
from palimp.models import LogSummary, ParseStats

ISO = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
BSD = r"[A-Z][a-z]{2}\s+\d{1,2} \d{2}:\d{2}:\d{2}"
TIMESTAMP = re.compile(rf"({ISO})|({BSD})")
STRUCTURED = re.compile(
    rf"(?:<\d+>)?1 ({ISO}) (\S+) RT_FLOW - (RT_FLOW_SESSION_[A-Z_]+) "
    r"\[(\S+)((?:\s+[\w-]+=(?:\"(?:[^\"\\]|\\.)*\"|\S+))*)\s*\](?:\s|$)"
)
STANDARD = re.compile(r"\bRT_FLOW: (RT_FLOW_SESSION_[A-Z_]+): (.*)$")
PAIR = re.compile(r'([\w-]+)="((?:[^"\\]|\\.)*)"')
TUPLE = r"\S+/\d+-+>\S+/\d+"
CREATE_CLOSE = re.compile(
    rf"^session (?:created|closed [^:]*:) {TUPLE} "
    r".*?\s\d{1,3} (\S+) (\S+) (\S+) (\d+)(?:\s|$)"
)
DENY = re.compile(rf"^session denied {TUPLE} .*?\s\d{{1,3}}\(\d+\) (\S+) (\S+) (\S+)(?:\s|$)")
KINDS = {
    "RT_FLOW_SESSION_CREATE": "create",
    "RT_FLOW_SESSION_CLOSE": "close",
    "RT_FLOW_SESSION_DENY": "deny",
}


@dataclass
class FlowEvent:
    kind: str
    policy_name: str
    from_zone: str
    to_zone: str
    session_id: str = ""
    logical_system: str = ""
    timestamp: datetime | None = None


def _kind(message_type: str) -> str | None:
    return KINDS.get(message_type.removesuffix("_LS"))


def _timestamp(prefix: str, year: int | None) -> datetime | None:
    """Device time: the last timestamp before the message, else any full one."""
    found: list[datetime] = []
    for iso, bsd in TIMESTAMP.findall(prefix):
        if iso:
            try:
                found.append(
                    datetime.fromisoformat(iso.replace("Z", "+00:00")).replace(tzinfo=None)
                )
            except ValueError:
                continue
        elif year is not None:
            try:
                found.append(
                    datetime.strptime(f"{year} {' '.join(bsd.split())}", "%Y %b %d %H:%M:%S")
                )
            except ValueError:
                continue
    return found[-1] if found else None


def parse_event(line: str, year: int | None = None) -> FlowEvent | None:
    """Read one RT_FLOW message, or None if the line is not a readable one."""
    if match := STRUCTURED.search(line):
        kind = _kind(match.group(3))
        fields = dict(PAIR.findall(match.group(5)))
        name = fields.get("policy-name")
        if kind is None or not name:
            return None
        return FlowEvent(
            kind=kind,
            policy_name=name,
            from_zone=fields.get("source-zone-name", ""),
            to_zone=fields.get("destination-zone-name", ""),
            session_id=fields.get("session-id") or fields.get("session-id-32", ""),
            logical_system=fields.get("logical-system-name", ""),
            timestamp=_timestamp(match.group(1), None),
        )
    if match := STANDARD.search(line):
        kind = _kind(match.group(1))
        body = match.group(2)
        found = (DENY if kind == "deny" else CREATE_CLOSE).match(body) if kind else None
        if not found:
            return None
        name, from_zone, to_zone, *rest = found.groups()
        return FlowEvent(
            kind=kind,
            policy_name=name,
            from_zone=from_zone,
            to_zone=to_zone,
            session_id=rest[0] if rest else "",
            timestamp=_timestamp(line[: match.start()], year),
        )
    return None


def parse_rt_flow(
    text: str, file: str = "logs/rt_flow.log", year: int | None = None
) -> tuple[dict[str, LogSummary], ParseStats]:
    stats = ParseStats(file=file)
    summaries: dict[str, LogSummary] = {}
    for raw in text.splitlines():
        if not raw.strip():
            continue
        stats.total += 1
        event = None if is_terminal_noise(raw) else parse_event(raw, year)
        if event is None:
            if "RT_FLOW" in raw and not is_terminal_noise(raw):
                stats.add_unknown(raw[:200])
            else:
                stats.ignored += 1
            continue
        summary = summaries.setdefault(event.policy_name, LogSummary(policy_name=event.policy_name))
        setattr(summary, event.kind, getattr(summary, event.kind) + 1)
        moment = event.timestamp
        if moment is not None:
            if summary.first_seen is None or moment < summary.first_seen:
                summary.first_seen = moment
            if summary.last_seen is None or moment > summary.last_seen:
                summary.last_seen = moment
        stats.parsed += 1
    return summaries, stats
