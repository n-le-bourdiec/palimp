"""Lines a saved terminal session adds around command output (gap G1).

An engineer who inherits a firewall often hands over a capture of an SSH
session, not the bare command output. Such a capture holds the prompt and the
command (`user@host> show system commit`), the configuration-mode banner
(`[edit]`, `[edit security policies]`), a cluster node banner
(`{primary:node0}`), CLI completion help (`Possible completions:`) and, in
published samples, `...` for elided lines. Readers count these lines as
ignored, never as unknown and never as data.

Published samples also show prompts with no space before the command
(`user@host#show security zones`).
"""

import re

PROMPT = re.compile(r"^\S+@[\w.:-]+([>#%])(?:\s|$|(?=[a-z]))")
EDIT_BANNER = re.compile(r"^\[edit(?:\s+(.*))?\]$")
NODE_BANNER = re.compile(r"^\{[\w:-]+\}$")
ELISION = re.compile(r"^\.{3}$")
COMPLETION = re.compile(r"^(Possible completions:|<[^>\s]+>\s|\|\s+Pipe through)")


def is_terminal_noise(line: str) -> bool:
    """True for prompt, banner, completion help and elision lines."""
    line = line.strip()
    return bool(
        PROMPT.match(line)
        or EDIT_BANNER.match(line)
        or NODE_BANNER.match(line)
        or ELISION.match(line)
        or COMPLETION.match(line)
    )


def edit_path(line: str) -> str | None:
    """Hierarchy named by an `[edit ...]` banner ("" for `[edit]`), else None."""
    match = EDIT_BANNER.match(line.strip())
    if not match:
        return None
    return (match.group(1) or "").strip()


def shown_path(line: str) -> tuple[str, list[str]] | None:
    """For a prompt line running a command that prints configuration, the mode and
    the hierarchy it prints, else None.

    Configuration mode (`#`): `show security policies` prints the hierarchy
    below `security policies`, relative to the current `[edit ...]` level.
    Operational mode (`>`): `show configuration security policies` prints it
    from the top; `show system rollback N` prints a whole configuration.
    """
    match = PROMPT.match(line.strip())
    if not match:
        return None
    words = line.strip()[match.end() :].split("|")[0].split()
    if not words or words[0] != "show":
        return None
    if match.group(1) == "#":
        return "edit", words[1:]
    if words[1:2] == ["configuration"]:
        return "top", words[2:]
    if words[1:3] == ["system", "rollback"]:
        return "top", []
    return None
