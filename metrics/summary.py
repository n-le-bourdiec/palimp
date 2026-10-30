"""Write metrics/summary.md: totals computed from metrics/sessions.csv (session 35).

Only finalized rows count (a provisional row, whose notes start with
"provisional", is listed apart): its token counts are not final until the next
session measures the transcript. Calls are read from the notes ("N API calls").
Cost is API-equivalent (decision 0006), not a billed amount.

Usage:
    uv run python metrics/summary.py
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
SOURCE = HERE / "sessions.csv"
TARGET = HERE / "summary.md"
TOKENS = ["tokens_input", "tokens_output", "tokens_cache_read", "tokens_cache_write"]


def calls(notes: str) -> int | None:
    match = re.search(r"(\d+) API calls", notes)
    return int(match[1]) if match else None


def number(value: str) -> int:
    return int(value) if value.isdigit() else 0


def main() -> None:
    rows = list(csv.DictReader(SOURCE.open(encoding="utf-8")))
    final = [r for r in rows if not r["notes"].startswith("provisional")]
    pending = [r for r in rows if r["notes"].startswith("provisional")]
    phases: dict[str, list[dict]] = defaultdict(list)
    for row in final:
        phases[row["phase"]].append(row)

    def line(label: str, group: list[dict]) -> str:
        cost = sum(float(r["est_cost_usd"]) for r in group)
        minutes = sum(number(r["duration_min"]) for r in group)
        counted = [c for r in group if (c := calls(r["notes"])) is not None]
        tokens = [sum(number(r[k]) for r in group) for k in TOKENS]
        return (
            f"| {label} | {len(group)} | {sum(counted):,} | {minutes:,} | "
            + " | ".join(f"{t:,}" for t in tokens)
            + f" | {cost:,.2f} |"
        )

    first, last = final[0]["session_id"], final[-1]["session_id"]
    out = [
        "# Metrics summary",
        "",
        f"Computed by `metrics/summary.py` from `metrics/sessions.csv`, sessions {first} to "
        f"{last} (finalized rows only). Cost is the API-equivalent cost of the tokens at the "
        "prices in `metrics/pricing.json` (decision 0006), not a billed amount. Calls are "
        "model API calls as counted in each row's notes.",
        "",
        "| scope | sessions | calls | minutes | input tokens | output tokens | "
        "cache read tokens | cache write tokens | API-equivalent cost (USD) |",
        "|---|---|---|---|---|---|---|---|---|",
        line("all", final),
    ]
    for phase in sorted(phases, key=lambda p: (-len(phases[p]), p)):
        out.append(line(f"phase {phase}", phases[phase]))
    out.append("")
    commits = sum(number(r["commits"]) for r in final)
    added = sum(number(r["lines_added"]) for r in final)
    removed = sum(number(r["lines_removed"]) for r in final)
    out += [
        f"Commits: {commits:,}. Lines added: {added:,}, removed: {removed:,} (metrics "
        "files excluded, as each row records them).",
        "",
    ]
    if pending:
        ids = ", ".join(r["session_id"] for r in pending)
        out += [
            f"Not counted yet (provisional row, finalized at the start of the next "
            f"session): session {ids}.",
            "",
        ]
    TARGET.write_text("\n".join(out), encoding="utf-8")
    print(f"{TARGET} written")


if __name__ == "__main__":
    main()
