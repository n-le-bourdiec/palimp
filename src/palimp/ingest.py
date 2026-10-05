"""Read every artifact of one directory into a normalized Dataset.

Only config.set is required. Missing optional inputs produce warnings.
"""

from datetime import date, datetime
from pathlib import Path
from typing import NamedTuple

from palimp.formats.commits import parse_commits
from palimp.formats.hitcount import parse_hitcount
from palimp.formats.junos_set import parse_set
from palimp.formats.rollbacks import read_rollbacks
from palimp.formats.rt_flow import parse_rt_flow
from palimp.formats.tickets import parse_tickets
from palimp.models import AddressObject, Config, Dataset, PastPolicy, PolicyHistory


def resolve_directory(directory: Path) -> Path:
    """Accept the artifact directory itself, or a parent holding an artifacts/ folder."""
    if (
        not (directory / "config.set").is_file()
        and (directory / "artifacts" / "config.set").is_file()
    ):
        return directory / "artifacts"
    return directory


def _read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None


class History(NamedTuple):
    policies: dict[str, PolicyHistory]
    created_by: dict[int, list[str]]
    removed_by: dict[int, list[PastPolicy]]
    added_by: dict[int, list[PastPolicy]]
    deactivated_by: dict[int, list[PastPolicy]]
    addresses: dict[str, AddressObject]


def history(configs: dict[int, Config]) -> History:
    """Find the commit that added each policy, and what each commit deleted, added
    or deactivated, by diffing consecutive configurations.

    configs[i] is the configuration after commit i (0 is the active one). Only
    the contiguous run 0, 1, 2, ... is used.
    """
    oldest = 0
    while oldest + 1 in configs:
        oldest += 1
    keys = {i: configs[i].keys() for i in range(oldest + 1)}
    created_by: dict[int, list[str]] = {}
    removed_by: dict[int, list[PastPolicy]] = {}
    added_by: dict[int, list[PastPolicy]] = {}
    deactivated_by: dict[int, list[PastPolicy]] = {}
    for i in range(oldest):
        added = sorted(keys[i] - keys[i + 1], key=str)
        if added:
            created_by[i] = [str(k) for k in added]
            added_by[i] = [PastPolicy.of(p) for k in added if (p := configs[i].policy(k))]
        removed = [configs[i + 1].policy(k) for k in sorted(keys[i + 1] - keys[i], key=str)]
        if removed:
            removed_by[i] = [PastPolicy.of(p) for p in removed if p]
        before = {p.key: p for p in configs[i + 1].policies}
        switched = [
            PastPolicy.of(p)
            for p in configs[i].policies
            if p.deactivated and p.key in before and not before[p.key].deactivated
        ]
        if switched:
            deactivated_by[i] = switched
    result: dict[str, PolicyHistory] = {}
    for policy in configs[0].policies:
        created = None
        for i in range(oldest):
            if policy.key in keys[i] and policy.key not in keys[i + 1]:
                created = i
                break
        result[str(policy.key)] = PolicyHistory(
            created_in_commit=created, oldest_retained_index=oldest
        )
    addresses: dict[str, AddressObject] = {}
    for i in range(oldest + 1):
        for name, obj in configs[i].addresses.items():
            addresses.setdefault(name, obj)
    return History(result, created_by, removed_by, added_by, deactivated_by, addresses)


def reference_date(dataset: Dataset) -> datetime | None:
    """Latest date found in the artifacts read so far (commits, then tickets)."""
    if dataset.commits:
        return max(c.timestamp for c in dataset.commits)
    dates: list[datetime] = []
    for ticket in dataset.tickets.values():
        for value in (ticket.opened, ticket.closed):
            try:
                dates.append(
                    datetime.combine(date.fromisoformat((value or "")[:10]), datetime.min.time())
                )
            except ValueError:
                continue
    return max(dates, default=None)


def ingest(directory: Path, log_year: int | None = None) -> Dataset:
    """Read DIRECTORY. `log_year` forces the year of undated log lines (see rt_flow)."""
    directory = resolve_directory(directory)
    config_text = _read(directory / "config.set")
    if config_text is None:
        raise FileNotFoundError(f"no config.set in {directory}")
    config = parse_set(config_text)
    dataset = Dataset(source=str(directory), config=config)

    text = _read(directory / "commits.txt")
    if text is None:
        dataset.warnings.append("commits.txt missing: no commit history")
    else:
        dataset.commits, dataset.commit_stats = parse_commits(text)

    rollbacks = read_rollbacks(directory / "rollbacks")
    if not rollbacks:
        dataset.warnings.append("no rollback files: creation commits cannot be found")
    dataset.rollback_stats = [rollbacks[i].stats for i in sorted(rollbacks)]
    past = history({0: config, **rollbacks})
    dataset.history = past.policies
    dataset.created_by_commit = past.created_by
    dataset.removed_by_commit = past.removed_by
    dataset.added_by_commit = past.added_by
    dataset.deactivated_by_commit = past.deactivated_by
    dataset.past_addresses = past.addresses

    text = _read(directory / "hitcount.txt")
    if text is None:
        dataset.warnings.append("hitcount.txt missing")
    else:
        dataset.hit_counts, dataset.hit_count_stats = parse_hitcount(text)

    text = _read(directory / "tickets.csv")
    if text is None:
        dataset.warnings.append("tickets.csv missing (optional)")
    else:
        dataset.tickets, dataset.ticket_stats = parse_tickets(text)

    text = _read(directory / "logs" / "rt_flow.log")
    if text is None:
        dataset.warnings.append("logs/rt_flow.log missing")
    else:
        dataset.logs, dataset.log_stats, dataset.log_window = parse_rt_flow(
            text, year=log_year, reference=reference_date(dataset)
        )
        if dataset.log_window.year_source in ("inferred", "none"):
            dataset.warnings.append(dataset.log_window.year_note)

    return dataset
