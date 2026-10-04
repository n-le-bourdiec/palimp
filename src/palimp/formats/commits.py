"""Reader for `show system commit` output (assumptions VSRX-4, VSRX-6).

Expected layout, one entry per commit, newest first, comment on the next
indented line(s):

    0   2026-09-14 22:41:07 CEST by jdoe via cli
        CHG0012345 add CRM export
    1   2026-09-12 10:02:55 CEST by admin via cli commit confirmed, rollback in 10mins
"""

import re
from datetime import datetime

from palimp.models import Commit, ParseStats

ENTRY = re.compile(
    r"^(\d+)\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(\S+)\s+by\s+(\S+)\s+via\s+(\S+)\s*(.*)$"
)


def parse_commits(text: str, file: str = "commits.txt") -> tuple[list[Commit], ParseStats]:
    stats = ParseStats(file=file)
    commits: list[Commit] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        stats.total += 1
        match = ENTRY.match(raw)
        if match:
            index, stamp, zone, user, client, extra = match.groups()
            commits.append(
                Commit(
                    index=int(index),
                    timestamp=datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S"),
                    time_zone=zone,
                    user=user,
                    client=client,
                    extra=extra.strip(),
                )
            )
            stats.parsed += 1
        elif raw[:1].isspace() and commits:
            last = commits[-1]
            last.comment = f"{last.comment} {raw.strip()}".strip()
            stats.parsed += 1
        else:
            stats.add_unknown(raw)
    return commits, stats
