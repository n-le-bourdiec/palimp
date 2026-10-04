"""Reader for RT_FLOW session logs in structured syslog format (VSRX-9, VSRX-10).

    <14>1 2026-09-14T08:12:44.311Z fw-01 RT_FLOW - RT_FLOW_SESSION_CLOSE [junos@2636... k="v" ...]

Only a per-policy summary is kept (counts, first and last timestamps). The
standard (unstructured) syslog format is not supported yet: its lines are
counted as unknown.
"""

import re
from datetime import datetime

from palimp.models import LogSummary, ParseStats

LINE = re.compile(r"^<\d+>1 (\S+) (\S+) RT_FLOW - (RT_FLOW_SESSION_\w+) \[(\S+) (.*)\]\s*$")
PAIR = re.compile(r'([\w-]+)="([^"]*)"')
KINDS = {
    "RT_FLOW_SESSION_CREATE": "create",
    "RT_FLOW_SESSION_CLOSE": "close",
    "RT_FLOW_SESSION_DENY": "deny",
}


def _timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def parse_rt_flow(
    text: str, file: str = "logs/rt_flow.log"
) -> tuple[dict[str, LogSummary], ParseStats]:
    stats = ParseStats(file=file)
    summaries: dict[str, LogSummary] = {}
    for raw in text.splitlines():
        if not raw.strip():
            continue
        stats.total += 1
        match = LINE.match(raw)
        if not match or match.group(3) not in KINDS:
            stats.add_unknown(raw[:200])
            continue
        fields = dict(PAIR.findall(match.group(5)))
        name = fields.get("policy-name")
        moment = _timestamp(match.group(1))
        if not name or moment is None:
            stats.add_unknown(raw[:200])
            continue
        summary = summaries.setdefault(name, LogSummary(policy_name=name))
        kind = KINDS[match.group(3)]
        setattr(summary, kind, getattr(summary, kind) + 1)
        if summary.first_seen is None or moment < summary.first_seen:
            summary.first_seen = moment
        if summary.last_seen is None or moment > summary.last_seen:
            summary.last_seen = moment
        stats.parsed += 1
    return summaries, stats
