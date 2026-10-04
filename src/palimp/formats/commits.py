"""Reader for `show system commit` output (assumptions VSRX-4, VSRX-6).

One entry per commit, newest first. The commit comment is on the next line,
indented (VSRX-4d, confirmed on a real vMX capture, decision 0015):

    0   2026-09-14 22:41:07 CEST by jdoe via cli
        CHG0012345 add CRM export
    1   2026-09-12 10:02:55 CEST by admin via cli commit confirmed, rollback in 10mins
      10  2018-03-16 14:13:57 PST by def via cli

Indexes may be right-aligned (gap G5). Text after the method holds known
suffixes, parsed into fields (gap G4): `commit confirmed, rollback in Nmins`,
`commit activate`, and a configuration revision id (`re0-1596309177-4`,
`include-configuration-revision`). Anything else stays in `extra`. The
trailing `rescue` entry and terminal lines are ignored (gaps G1, G3).
"""

import re
from datetime import datetime

from palimp.formats.terminal import is_terminal_noise
from palimp.models import Commit, ParseStats

STAMP = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
ENTRY = re.compile(rf"^\s*(\d+)\s+({STAMP})\s+(\S+)\s+by\s+(\S+)\s+via\s+(\S+)\s*(.*)$")
RESCUE = re.compile(rf"^\s*rescue\s+{STAMP}\s")
CONFIRMED = re.compile(r"\bcommit confirmed, rollback in (\d+)\s*mins?\b")
ACTIVATE = re.compile(r"\bcommit activate\b")
REVISION = re.compile(r"\bre\d+-\d+-\d+\b")


def _suffixes(text: str) -> tuple[str, int | None, str, str]:
    """Split the text after the method into (commit type, minutes, revision, rest)."""
    kind, minutes, revision = "", None, ""
    if match := CONFIRMED.search(text):
        kind, minutes = "confirmed", int(match.group(1))
        text = text[: match.start()] + text[match.end() :]
    elif match := ACTIVATE.search(text):
        kind = "activate"
        text = text[: match.start()] + text[match.end() :]
    if match := REVISION.search(text):
        revision = match.group(0)
        text = text[: match.start()] + text[match.end() :]
    return kind, minutes, revision, " ".join(text.split())


def parse_commits(text: str, file: str = "commits.txt") -> tuple[list[Commit], ParseStats]:
    stats = ParseStats(file=file)
    commits: list[Commit] = []
    current: Commit | None = None
    for raw in text.splitlines():
        if not raw.strip():
            continue
        stats.total += 1
        match = ENTRY.match(raw)
        if match:
            index, stamp, zone, user, client, rest = match.groups()
            kind, minutes, revision, extra = _suffixes(rest)
            current = Commit(
                index=int(index),
                timestamp=datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S"),
                time_zone=zone,
                user=user,
                client=client,
                commit_type=kind,
                rollback_minutes=minutes,
                revision=revision,
                extra=extra,
            )
            commits.append(current)
            stats.parsed += 1
        elif RESCUE.match(raw) or is_terminal_noise(raw):
            current = None
            stats.ignored += 1
        elif raw[:1].isspace() and current is not None:
            current.comment = f"{current.comment} {raw.strip()}".strip()
            stats.parsed += 1
        else:
            stats.add_unknown(raw)
    return commits, stats
