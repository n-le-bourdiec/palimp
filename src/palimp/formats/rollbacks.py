"""Reader for rollback files: `show system rollback N`, in set format
(`| display set`, VSRX-1, VSRX-6) or hierarchical (the default output).

Files are expected as rollbacks/rollback-NN.set, where NN matches the index in
the commit history, whatever their format. Index 0 is the active
configuration (config.set).
"""

import re
from pathlib import Path

from palimp.formats.junos_config import parse_config
from palimp.models import Config

NAME = re.compile(r"^rollback-(\d+)\.set$")


def read_rollbacks(directory: Path) -> dict[int, Config]:
    configs: dict[int, Config] = {}
    if not directory.is_dir():
        return configs
    for path in sorted(directory.iterdir()):
        match = NAME.match(path.name)
        if match:
            text = path.read_text(encoding="utf-8", errors="replace")
            configs[int(match.group(1))] = parse_config(text, file=f"rollbacks/{path.name}")
    return configs
