"""Sum token usage and API-equivalent cost of a Claude Code session.

Claude Code writes every session to
~/.claude/projects/<project-slug>/<session-id>.jsonl. Each assistant entry
carries the API `usage` block and the model id. One API response can be
written on several lines (one per content block) with the same message id, so
entries are deduplicated by message id before summing.

Several palimp sessions can share one transcript (the conversation is simply
continued), so --since and --until restrict the sum to a time window. Use the
timestamp of the user prompt that opened each palimp session as the boundary.

Cost is API-equivalent: what the same tokens would cost on the Claude API at
the prices in metrics/pricing.json (see docs/decisions/0006). It is not what a
subscription plan bills.

Usage:
    uv run python metrics/session_tokens.py <session-id or path>
        [--since 2026-09-28T14:58:54Z] [--until 2026-09-28T16:00:00Z]

Reads local files only. The numbers cover the transcript as it is when the
script runs, so run it as the last step of a session, or later to finalize.
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

PRICING = Path(__file__).with_name("pricing.json")


def find_transcript(arg: str) -> Path:
    path = Path(arg)
    if path.is_file():
        return path
    matches = list((Path.home() / ".claude" / "projects").glob(f"*/{arg}.jsonl"))
    if not matches:
        sys.exit(f"no transcript found for {arg}")
    return matches[0]


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def collect_messages(
    files: list[Path], since: datetime | None, until: datetime | None
) -> list[dict]:
    """Return one message dict (with model and usage) per API response."""
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
            if not message.get("usage") or "timestamp" not in entry:
                continue
            when = parse_time(entry["timestamp"])
            if (since and when < since) or (until and when >= until):
                continue
            seen[message.get("id") or entry.get("uuid")] = message
    return list(seen.values())


def model_prices(model: str, speed: str, pricing: dict) -> dict | None:
    """Per-million-token prices for a model id, or None if unknown."""
    base = re.sub(r"-\d{8}$", "", model)
    prices = pricing["models"].get(base)
    if prices is None:
        return None
    prices = dict(prices)
    fast = pricing["fast_mode"].get(base)
    if speed == "fast" and fast:
        # Fast mode replaces input and output prices; cache multipliers stack on top.
        factor = fast["input"] / prices["input"]
        for key in ("cache_write_5m", "cache_write_1h", "cache_read"):
            prices[key] *= factor
        prices["input"] = fast["input"]
        prices["output"] = fast["output"]
    return prices


def summarize(messages: list[dict], pricing: dict) -> dict:
    totals = {
        "calls": len(messages),
        "input": 0,
        "output": 0,
        "cache_read": 0,
        "cache_write": 0,
        "cache_write_5m": 0,
        "cache_write_1h": 0,
        "web_searches": 0,
    }
    cost = 0.0
    unknown_models: set[str] = set()
    for message in messages:
        usage = message["usage"]
        write_total = usage.get("cache_creation_input_tokens", 0)
        split = usage.get("cache_creation") or {}
        write_1h = split.get("ephemeral_1h_input_tokens", 0)
        # Without a split, assume the default 5 minute cache.
        write_5m = split.get("ephemeral_5m_input_tokens", write_total - write_1h)
        searches = (usage.get("server_tool_use") or {}).get("web_search_requests", 0)
        counts = {
            "input": usage.get("input_tokens", 0),
            "output": usage.get("output_tokens", 0),
            "cache_read": usage.get("cache_read_input_tokens", 0),
            "cache_write_5m": write_5m,
            "cache_write_1h": write_1h,
        }
        for key, value in counts.items():
            totals[key] += value
        totals["cache_write"] += write_total
        totals["web_searches"] += searches
        if not any(counts.values()) and not searches:
            continue
        prices = model_prices(message.get("model", ""), usage.get("speed", ""), pricing)
        if prices is None:
            unknown_models.add(message.get("model", "?"))
            continue
        geo = pricing["us_inference_multiplier"] if usage.get("inference_geo") == "us" else 1.0
        tokens_cost = sum(counts[key] * prices[key] for key in counts) / 1_000_000
        cost += tokens_cost * geo + searches * pricing["web_search_per_request"]
    totals["est_cost_usd"] = "n/a" if unknown_models else f"{cost:.2f}"
    if unknown_models:
        totals["unknown_models"] = ",".join(sorted(unknown_models))
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("session", help="session id or path to a transcript .jsonl")
    parser.add_argument("--since", type=parse_time, help="include entries at or after (ISO)")
    parser.add_argument("--until", type=parse_time, help="include entries before (ISO)")
    args = parser.parse_args()

    transcript = find_transcript(args.session)
    # Subagent transcripts, if any, live next to the main one.
    files = [transcript, *transcript.with_suffix("").glob("**/*.jsonl")]
    pricing = json.loads(PRICING.read_text(encoding="utf-8"))
    totals = summarize(collect_messages(files, args.since, args.until), pricing)
    for key, value in totals.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
