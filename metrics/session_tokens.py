"""Sum token usage of one Claude Code session from its local transcript.

Claude Code writes every session to
~/.claude/projects/<project-slug>/<session-id>.jsonl. Each assistant entry
carries the API `usage` block. One API response can be written on several
lines (one per content block) with the same message id, so entries are
deduplicated by message id before summing.

Usage:
    uv run python metrics/session_tokens.py <session-id>
    uv run python metrics/session_tokens.py path/to/transcript.jsonl

Reads local files only. The numbers cover the transcript as it is when the
script runs, so run it as the last step of a session.
"""

import json
import sys
from pathlib import Path


def find_transcript(arg: str) -> Path:
    path = Path(arg)
    if path.is_file():
        return path
    matches = list((Path.home() / ".claude" / "projects").glob(f"*/{arg}.jsonl"))
    if not matches:
        sys.exit(f"no transcript found for {arg}")
    return matches[0]


def sum_usage(files: list[Path]) -> dict[str, int]:
    seen: dict[str, dict] = {}
    for file in files:
        for line in file.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = entry.get("message")
            if entry.get("type") != "assistant" or not isinstance(message, dict):
                continue
            usage = message.get("usage")
            if usage:
                seen[message.get("id") or entry.get("uuid")] = usage
    totals = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0, "calls": len(seen)}
    for usage in seen.values():
        totals["input"] += usage.get("input_tokens", 0)
        totals["output"] += usage.get("output_tokens", 0)
        totals["cache_write"] += usage.get("cache_creation_input_tokens", 0)
        totals["cache_read"] += usage.get("cache_read_input_tokens", 0)
    return totals


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    transcript = find_transcript(sys.argv[1])
    # Subagent transcripts, if any, live next to the main one.
    files = [transcript, *transcript.with_suffix("").glob("**/*.jsonl")]
    totals = sum_usage(files)
    for key, value in totals.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
