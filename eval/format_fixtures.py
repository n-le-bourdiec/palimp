"""Run palimp's format readers on the format fixtures (decisions 0013 and 0015).

Each fixture in tests/fixtures/junos_docs/ starts with a `#` header ending with
`# ---`; only the body after that line is given to the reader. The script
prints, per fixture, what the reader understood and which lines it could not
read. A fixture PARSES when no line is unknown (terminal lines such as prompts
count as ignored). It never fails: gaps are listed in docs/format-assumptions.md and fixed
in later sessions.

    uv run python eval/format_fixtures.py
"""

from pathlib import Path

from palimp.formats.commits import parse_commits
from palimp.formats.hitcount import parse_hitcount
from palimp.formats.junos_config import parse_config
from palimp.formats.junos_set import parse_set
from palimp.formats.rt_flow import parse_rt_flow

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "junos_docs"


def body(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[lines.index("# ---") + 1 :]) + "\n"


def run_commits(text: str, name: str):
    commits, stats = parse_commits(text, file=name)
    shown = "; ".join(
        f"{c.index} {c.timestamp:%Y-%m-%d %H:%M:%S} {c.time_zone} {c.user} via {c.client}"
        + (f" type={c.commit_type}" if c.commit_type else "")
        + (f" rollback_in={c.rollback_minutes}min" if c.rollback_minutes else "")
        + (f" revision={c.revision}" if c.revision else "")
        + (f" extra={c.extra!r}" if c.extra else "")
        + (f" comment={c.comment!r}" if c.comment else "")
        for c in commits[:3]
    )
    return f"{len(commits)} commits [{shown}]", stats


def run_set(text: str, name: str):
    config = parse_set(text, file=name)
    return f"{len(config.policies)} policies", config.stats


def run_config(text: str, name: str):
    config = parse_config(text, file=name)
    notes = sum(len(p.annotations) for p in config.policies)
    return (
        f"{config.stats.format}: {len(config.policies)} policies, {len(config.addresses)} "
        f"addresses, {len(config.applications)} applications, {notes} policy annotations",
        config.stats,
    )


def run_hitcount(text: str, name: str):
    rows, stats = parse_hitcount(text, file=name)
    shown = "; ".join(f"{r.from_zone}/{r.to_zone}/{r.name}={r.count} {r.action}" for r in rows)
    return f"{len(rows)} rows [{shown}]", stats


def run_rt_flow(text: str, name: str):
    summaries, stats = parse_rt_flow(text, file=name)
    shown = "; ".join(
        f"{s.policy_name}: create={s.create} close={s.close} deny={s.deny}"
        for s in summaries.values()
    )
    return f"{len(summaries)} policies [{shown}]", stats


READERS = {
    "show_system_commit": run_commits,
    "show-system-commit": run_commits,
    "rollback_completions": run_commits,
    "display_set": run_set,
    "hier_": run_config,
    "hitcount": run_hitcount,
    "rt_flow": run_rt_flow,
}


def main() -> None:
    for path in sorted(FIXTURES.glob("*.txt")):
        reader = next((r for prefix, r in READERS.items() if path.name.startswith(prefix)), None)
        if reader is None:
            print(f"{path.name}: reference only (no reader)")
            continue
        summary, stats = reader(body(path), path.name)
        verdict = "GAPS" if stats.unknown else "PARSES"
        if not stats.unknown and not stats.parsed:
            verdict += " (nothing in scope)"
        print(
            f"{path.name}: {verdict} total={stats.total} parsed={stats.parsed} "
            f"ignored={stats.ignored} unknown={stats.unknown} -> {summary}"
        )
        for line in stats.unknown_samples:
            print(f"    unknown: {line[:110]!r}")


if __name__ == "__main__":
    main()
