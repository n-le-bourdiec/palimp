"""Reader for `show security policies hit-count` output (assumption VSRX-7).

Logical system: root-logical-system
 Index   From zone        To zone           Name             Policy count  Action
 1       users            servers           users-to-crm     184223        Permit
"""

import re

from palimp.models import HitCount, ParseStats

ROW = re.compile(r"^\s*(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\S+)\s*$")
HEADER = re.compile(r"^\s*(Logical system:|Index\s+From zone)")


def parse_hitcount(text: str, file: str = "hitcount.txt") -> tuple[list[HitCount], ParseStats]:
    stats = ParseStats(file=file)
    rows: list[HitCount] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        stats.total += 1
        if HEADER.match(raw):
            stats.ignored += 1
            continue
        match = ROW.match(raw)
        if not match:
            stats.add_unknown(raw)
            continue
        _, from_zone, to_zone, name, count, action = match.groups()
        rows.append(
            HitCount(
                from_zone=from_zone, to_zone=to_zone, name=name, count=int(count), action=action
            )
        )
        stats.parsed += 1
    return rows, stats
