"""What a hit count really means: counter clears inferred from the artifacts.

hitcount.txt gives counts since the counters were last cleared, never the
clear date. Two plain observations show a clear:

- the log shows sessions of a policy, yet its counter is 0: that counter was
  cleared after the last logged session;
- every policy of a zone pair (at least MIN_PAIR_POLICIES of them) shows 0
  while other zone pairs show hits: `clear security policies hit-count
  from-zone A to-zone B` was probably run, at a date the artifacts do not give.

A clear only changes what a count means, never a verdict on its own: a zero
after a clear covers only the time since that clear.
"""

from dataclasses import dataclass, field
from datetime import datetime

from palimp.models import Dataset

MIN_PAIR_POLICIES = 3


@dataclass
class Clear:
    """Clears seen in one zone pair."""

    # Policy name -> last logged session, for counters at 0 despite logged sessions.
    after: dict[str, datetime] = field(default_factory=dict)
    whole_pair: int = 0  # number of policies, when every counter of the pair is 0

    @property
    def latest(self) -> tuple[str, datetime] | None:
        if not self.after:
            return None
        name = max(self.after, key=lambda n: self.after[n])
        return name, self.after[name]


def clears(dataset: Dataset) -> dict[tuple[str, str], Clear]:
    found: dict[tuple[str, str], Clear] = {}
    if dataset.hit_count_stats is None:
        return found
    counts = {(h.from_zone, h.to_zone, h.name): h.count for h in dataset.hit_counts}
    pairs: dict[tuple[str, str], list[int]] = {}
    for policy in dataset.config.policies:
        count = counts.get((policy.from_zone, policy.to_zone, policy.name))
        if count is None or policy.deactivated:
            continue
        pair = (policy.from_zone, policy.to_zone)
        pairs.setdefault(pair, []).append(count)
        summary = dataset.logs.get(str(policy.key)) or dataset.logs.get(policy.name)
        if count == 0 and summary and summary.sessions and summary.last_seen:
            found.setdefault(pair, Clear()).after[policy.name] = summary.last_seen
    elsewhere = {pair for pair, values in pairs.items() if any(values)}
    for pair, values in pairs.items():
        if len(values) >= MIN_PAIR_POLICIES and not any(values) and elsewhere - {pair}:
            found.setdefault(pair, Clear()).whole_pair = len(values)
    return found


def meaning(clear: Clear | None, name: str, count: int, pair: tuple[str, str]) -> str:
    """What this count says, given the clears seen in its zone pair ("" when nothing)."""
    if clear is None:
        return ""
    if name in clear.after:
        return (
            f"; yet the log shows sessions up to {clear.after[name]:%Y-%m-%d %H:%M}: this counter "
            "was cleared after that, so the count covers only the time since"
        )
    notes = []
    if latest := clear.latest:
        other, when = latest
        notes.append(
            f"policy {other} of the same zone pair logged sessions up to {when:%Y-%m-%d %H:%M} "
            "but shows 0, so counters of this zone pair were cleared after that; if this one "
            "was cleared with it, "
            + ("these hits are all later" if count else "zero covers only the time since")
        )
    if clear.whole_pair:
        notes.append(
            f"every one of the {clear.whole_pair} policies from {pair[0]} to {pair[1]} shows 0 "
            "while other zone pairs show hits: these counters were probably cleared, at a date "
            "hitcount.txt does not give, and zero says nothing about use before that clear"
        )
    return "".join(f"; {n}" for n in notes)
