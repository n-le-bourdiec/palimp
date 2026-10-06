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
the address tuple and on the protocol number that precedes the policy name:
`... SRC/PORT->DST/PORT [0xTAG] SERVICE ... PROTO POLICY FROM-ZONE TO-ZONE
SESSION-ID ...` for CREATE and CLOSE, and `... PROTO(ICMP-TYPE) POLICY
FROM-ZONE TO-ZONE ...` for DENY.

A BSD syslog timestamp (`Sep  6 02:52:30`) has no year. When a full ISO
timestamp precedes it on the line (a syslog server stamp), its year is used.
Otherwise the line is "undated": `parse_rt_flow` gives it a year from `year`
(the year of the first undated line, forced by the user) or infers one from
`reference` (the latest date found in other artifacts, normally the newest
commit), and moves to the next year at each December to January rollover.
Without either, those events are counted and their times left unset.

Only a per-policy summary is kept: counts, first and last timestamps, distinct
sources, destinations and ports, sessions per hour and weekday, active days.
Lines that are not RT_FLOW messages (other daemons, `last message repeated`)
are ignored.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from palimp.formats.terminal import is_terminal_noise
from palimp.models import LogSummary, LogWindow, ParseStats

ISO = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
BSD = r"[A-Z][a-z]{2}\s+\d{1,2} \d{2}:\d{2}:\d{2}"
TIMESTAMP = re.compile(rf"({ISO})|({BSD})")
STRUCTURED = re.compile(
    rf"(?:<\d+>)?1 ({ISO}) (\S+) RT_FLOW - (RT_FLOW_SESSION_[A-Z_]+) "
    r"\[(\S+)((?:\s+[\w-]+=(?:\"(?:[^\"\\]|\\.)*\"|\S+))*)\s*\](?:\s|$)"
)
STANDARD = re.compile(r"\bRT_FLOW: (RT_FLOW_SESSION_[A-Z_]+): (.*)$")
PAIR = re.compile(r'([\w-]+)="((?:[^"\\]|\\.)*)"')
TUPLE = r"([^\s/]+)/(\d+)-+>([^\s/]+)/(\d+) (?:0x\w+ )?(\S+)"
CREATE_CLOSE = re.compile(
    rf"^session (?:created|closed [^:]*:) {TUPLE} "
    r".*?\s(\d{1,3}) (\S+) (\S+) (\S+) (\d+)(?:\s|$)"
)
DENY = re.compile(
    rf"^session denied {TUPLE}\s+(?:.*?\s)?(\d{{1,3}})\(\d+\) (\S+) (\S+) (\S+)(?:\s|$)"
)
KINDS = {
    "RT_FLOW_SESSION_CREATE": "create",
    "RT_FLOW_SESSION_CLOSE": "close",
    "RT_FLOW_SESSION_DENY": "deny",
}
PROTOCOLS = {"1": "icmp", "6": "tcp", "17": "udp", "58": "icmp6"}
# Lists kept per policy are capped; their counts are exact.
LIST_CAP = 20
# A placeholder leap year, so that Feb 29 survives until the real year is known.
NO_YEAR = 2000


@dataclass
class FlowEvent:
    kind: str
    policy_name: str
    from_zone: str
    to_zone: str
    session_id: str = ""
    logical_system: str = ""
    timestamp: datetime | None = None
    # Month, day and time of a timestamp without year, in year NO_YEAR.
    undated: datetime | None = None
    source: str = ""
    destination: str = ""
    destination_port: str = ""
    protocol: str = ""
    service: str = ""


def _kind(message_type: str) -> str | None:
    return KINDS.get(message_type.removesuffix("_LS"))


def _bsd(text: str, year: int) -> datetime | None:
    try:
        return datetime.strptime(f"{year} {' '.join(text.split())}", "%Y %b %d %H:%M:%S")
    except ValueError:
        return None


def _timestamp(prefix: str, year: int | None = None) -> tuple[datetime | None, datetime | None]:
    """Device time: the last timestamp before the message, as (dated, undated).

    A BSD timestamp takes its year from `year`, else from an ISO timestamp
    earlier on the line (a syslog server stamp), else it stays undated.
    """
    dated: datetime | None = None
    last_bsd: str | None = None
    for iso, bsd in TIMESTAMP.findall(prefix):
        if iso:
            try:
                dated = datetime.fromisoformat(iso.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                continue
            last_bsd = None
        else:
            last_bsd = bsd
    if last_bsd is None:
        return dated, None
    if year is not None:
        return _bsd(last_bsd, year), None
    if dated is not None:
        moment = _bsd(last_bsd, dated.year)
        if moment is not None and moment.month > dated.month + 6:
            moment = _bsd(last_bsd, dated.year - 1)
        elif moment is not None and moment.month + 6 < dated.month:
            moment = _bsd(last_bsd, dated.year + 1)
        return moment, None
    return None, _bsd(last_bsd, NO_YEAR)


def parse_event(line: str, year: int | None = None) -> FlowEvent | None:
    """Read one RT_FLOW message, or None if the line is not a readable one."""
    if match := STRUCTURED.search(line):
        kind = _kind(match.group(3))
        fields = dict(PAIR.findall(match.group(5)))
        name = fields.get("policy-name")
        if kind is None or not name:
            return None
        protocol = fields.get("protocol-id", "")
        dated, _ = _timestamp(match.group(1))
        return FlowEvent(
            kind=kind,
            policy_name=name,
            from_zone=fields.get("source-zone-name", ""),
            to_zone=fields.get("destination-zone-name", ""),
            session_id=fields.get("session-id") or fields.get("session-id-32", ""),
            logical_system=fields.get("logical-system-name", ""),
            timestamp=dated,
            source=fields.get("source-address", ""),
            destination=fields.get("destination-address", ""),
            destination_port=fields.get("destination-port", ""),
            protocol=PROTOCOLS.get(protocol, protocol),
            service=fields.get("service-name", ""),
        )
    if match := STANDARD.search(line):
        kind = _kind(match.group(1))
        body = match.group(2)
        found = (DENY if kind == "deny" else CREATE_CLOSE).match(body) if kind else None
        if not found:
            return None
        source, _, destination, port, service, protocol, name, from_zone, to_zone, *rest = (
            found.groups()
        )
        dated, undated = _timestamp(line[: match.start()], year)
        return FlowEvent(
            kind=kind,
            policy_name=name,
            from_zone=from_zone,
            to_zone=to_zone,
            session_id=rest[0] if rest else "",
            timestamp=dated,
            undated=undated,
            source=source,
            destination=destination,
            destination_port=port,
            protocol=PROTOCOLS.get(protocol, protocol),
            service=service,
        )
    return None


def _with_year(moment: datetime, year: int) -> datetime:
    if moment.month == 2 and moment.day == 29 and year % 4:
        moment = moment.replace(day=28)
    return moment.replace(year=year)


def assign_years(
    events: list[FlowEvent], year: int | None = None, reference: datetime | None = None
) -> LogWindow:
    """Give a year to undated events (file order), handling December to January rollover.

    `year` is the year of the first undated event. Without it, the year of the
    last undated event is the earliest one that puts it no more than 31 days
    before `reference`: logs are collected at handover, after the newest commit.
    """
    undated = [e for e in events if e.timestamp is None and e.undated is not None]
    window = LogWindow(undated_lines=len(undated))
    if not undated:
        return window
    offsets: list[int] = []
    current, previous = 0, None
    for event in undated:
        month = event.undated.month
        if previous is not None and month + 6 < previous:
            current += 1
        elif previous is not None and month > previous + 6:
            # A late line from the previous year: it does not move the clock.
            offsets.append(current - 1)
            continue
        previous = month
        offsets.append(current)
    if year is not None:
        start = year
        window.year_source = "forced"
        window.year_note = f"log year forced to {year} for the first undated line"
    elif reference is not None:
        last = undated[-1].undated
        end = reference.year - 1
        while _with_year(last, end) < reference - timedelta(days=31):
            end += 1
        start = end - offsets[-1]
        window.year_source = "inferred"
        window.year_note = (
            f"{len(undated)} log lines have no year; inferred {start}"
            + (f" to {end}" if end != start else "")
            + f" from the latest date in other artifacts ({reference:%Y-%m-%d});"
            " use --log-year to force it"
        )
    else:
        window.year_source = "none"
        window.year_note = (
            f"{len(undated)} log lines have no year and no other artifact gives one: "
            "their times are left unset; use --log-year"
        )
        return window
    for event, offset in zip(undated, offsets, strict=True):
        event.timestamp = _with_year(event.undated, start + offset)
    return window


@dataclass
class _Accumulator:
    summary: LogSummary
    sessions: set[str] = field(default_factory=set)
    anonymous: int = 0
    sources: set[str] = field(default_factory=set)
    destinations: set[str] = field(default_factory=set)
    ports: set[str] = field(default_factory=set)
    services: set[str] = field(default_factory=set)
    days: set[date] = field(default_factory=set)

    def add(self, event: FlowEvent) -> None:
        summary = self.summary
        setattr(summary, event.kind, getattr(summary, event.kind) + 1)
        moment = event.timestamp
        if moment is not None:
            if summary.first_seen is None or moment < summary.first_seen:
                summary.first_seen = moment
            if summary.last_seen is None or moment > summary.last_seen:
                summary.last_seen = moment
        if event.kind == "deny":
            return
        if event.session_id:
            if event.session_id in self.sessions:
                return
            self.sessions.add(event.session_id)
        else:
            self.anonymous += 1
        for target, value in (
            (self.sources, event.source),
            (self.destinations, event.destination),
            (self.services, event.service),
        ):
            if value:
                target.add(value)
        if event.destination_port:
            self.ports.add(f"{event.protocol or '?'}/{event.destination_port}")
        if moment is not None:
            summary.hours[moment.hour] += 1
            summary.weekdays[moment.weekday()] += 1
            self.days.add(moment.date())

    def finish(self) -> LogSummary:
        summary = self.summary
        # Without session ids, a session logged at create and at close counts twice.
        anonymous = self.anonymous
        if anonymous and summary.create and summary.close:
            anonymous = max(summary.create, summary.close) - len(self.sessions)
        summary.sessions = len(self.sessions) + max(anonymous, 0)
        for name, values in (
            ("sources", self.sources),
            ("destinations", self.destinations),
            ("ports", self.ports),
            ("services", self.services),
        ):
            setattr(summary, name, sorted(values)[:LIST_CAP])
        summary.source_count = len(self.sources)
        summary.destination_count = len(self.destinations)
        summary.days = sorted(self.days)
        return summary


def merge_summaries(name: str, summaries: list[LogSummary]) -> LogSummary:
    """One summary for a policy logged under several zone pairs (a global policy).

    Counts are summed. Distinct sources and destinations are a lower bound
    when a per-pair list was capped.
    """
    merged = LogSummary(policy_name=name)
    for one in summaries:
        merged.create += one.create
        merged.close += one.close
        merged.deny += one.deny
        merged.sessions += one.sessions
        for when in (one.first_seen, one.last_seen):
            if when is None:
                continue
            if merged.first_seen is None or when < merged.first_seen:
                merged.first_seen = when
            if merged.last_seen is None or when > merged.last_seen:
                merged.last_seen = when
        merged.hours = [a + b for a, b in zip(merged.hours, one.hours, strict=True)]
        merged.weekdays = [a + b for a, b in zip(merged.weekdays, one.weekdays, strict=True)]
    for attr in ("sources", "destinations", "ports", "services"):
        values = sorted({v for one in summaries for v in getattr(one, attr)})
        setattr(merged, attr, values[:LIST_CAP])
    merged.source_count = max(
        [len({v for one in summaries for v in one.sources})]
        + [one.source_count for one in summaries]
    )
    merged.destination_count = max(
        [len({v for one in summaries for v in one.destinations})]
        + [one.destination_count for one in summaries]
    )
    merged.days = sorted({d for one in summaries for d in one.days})
    return merged


def summary_key(policy_name: str, from_zone: str, to_zone: str) -> str:
    """FROM/TO/NAME, or NAME alone when the message carries no zones."""
    return f"{from_zone}/{to_zone}/{policy_name}" if from_zone and to_zone else policy_name


def parse_rt_flow(
    text: str,
    file: str = "logs/rt_flow.log",
    year: int | None = None,
    reference: datetime | None = None,
) -> tuple[dict[str, LogSummary], ParseStats, LogWindow]:
    stats = ParseStats(file=file)
    events: list[FlowEvent] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        stats.total += 1
        event = None if is_terminal_noise(raw) else parse_event(raw)
        if event is None:
            if "RT_FLOW" in raw and not is_terminal_noise(raw):
                stats.add_unknown(raw[:200])
            else:
                stats.ignored += 1
            continue
        events.append(event)
        stats.parsed += 1
    window = assign_years(events, year, reference)
    accumulators: dict[str, _Accumulator] = {}
    addresses: set[str] = set()
    for event in events:
        addresses.update(a for a in (event.source, event.destination) if a)
        key = summary_key(event.policy_name, event.from_zone, event.to_zone)
        if key not in accumulators:
            summary = LogSummary(
                policy_name=event.policy_name, from_zone=event.from_zone, to_zone=event.to_zone
            )
            accumulators[key] = _Accumulator(summary)
        accumulators[key].add(event)
        if event.timestamp is not None:
            if window.start is None or event.timestamp < window.start:
                window.start = event.timestamp
            if window.end is None or event.timestamp > window.end:
                window.end = event.timestamp
    window.addresses = sorted(addresses)
    return {key: acc.finish() for key, acc in accumulators.items()}, stats, window
