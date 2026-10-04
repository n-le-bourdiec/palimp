"""Reader for `show security policies hit-count` output (assumption VSRX-7).

Three published layouts are accepted (gap G6):

    Logical system: root-logical-system
    Index   From zone        To zone           Name             Policy count  Action
    1       users            servers           users-to-crm     184223        Permit

the `detail` layout, which adds a `Redirect` column after Action, and the
legacy layout, with a lowercase header, no Action column and a footer:

    index   from zone    to zone       name       policy count
     1       untrust      trust        policy1         40
    Number of policy: 1

Rows come in no particular order and `Index` is only a display line number
(VSRX-7b): it is read and dropped, rows are identified by zones and name.
"""

import re

from palimp.formats.terminal import is_terminal_noise
from palimp.models import HitCount, ParseStats

ROW = re.compile(r"^\s*\d+\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)(?:\s+([A-Za-z][\w-]*))?(?:\s+\d+)?\s*$")
HEADER = re.compile(r"^\s*(Logical system:|Index\s+From zone|Number of policy:)", re.IGNORECASE)


def parse_hitcount(text: str, file: str = "hitcount.txt") -> tuple[list[HitCount], ParseStats]:
    stats = ParseStats(file=file)
    rows: list[HitCount] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        stats.total += 1
        if HEADER.match(raw) or is_terminal_noise(raw):
            stats.ignored += 1
            continue
        match = ROW.match(raw)
        if not match:
            stats.add_unknown(raw)
            continue
        from_zone, to_zone, name, count, action = match.groups()
        rows.append(
            HitCount(
                from_zone=from_zone,
                to_zone=to_zone,
                name=name,
                count=int(count),
                action=action or "",
            )
        )
        stats.parsed += 1
    return rows, stats
