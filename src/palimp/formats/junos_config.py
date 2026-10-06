"""Read a Junos configuration in either format, detected from the text.

- set: `show configuration | display set` (also `display set relative` after
  an `[edit ...]` banner, reported as "set relative");
- hierarchical: `show configuration`, `show` in configuration mode,
  `show system rollback N` (curly braces).

Both readers feed the same model builder, so the format never changes the
analysis. The detected format is in `Config.stats.format`.
"""

import re

from palimp.formats.junos_hier import parse_hierarchical
from palimp.formats.junos_set import parse_set
from palimp.formats.terminal import is_terminal_noise
from palimp.models import Config

SET_VERB = re.compile(r"^(?:set|deactivate|delete|activate|insert|annotate)\s")
HIER_LINE = re.compile(r"(?:[{;]|^\})(?:\s*(?:#.*|/\*.*\*/))?$")


def detect_format(text: str) -> str:
    """Return "set" or "hierarchical", by a vote of the statement lines (set when tied or empty)."""
    votes = {"set": 0, "hierarchical": 0}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "/*")) or is_terminal_noise(line):
            continue
        if SET_VERB.match(line):
            votes["set"] += 1
        elif HIER_LINE.search(line):
            votes["hierarchical"] += 1
    return "hierarchical" if votes["hierarchical"] > votes["set"] else "set"


def parse_config(text: str, file: str = "config.set") -> Config:
    if detect_format(text) == "hierarchical":
        return parse_hierarchical(text, file=file)
    return parse_set(text, file=file)
