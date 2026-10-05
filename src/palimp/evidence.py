"""Deterministic evidence collectors. No scoring here.

T1 direct: policy description, comment of the commit that created the policy,
ticket references found in the name, description or that comment (matched
against tickets.csv when present).
T2 behavioral: hit count row, RT_FLOW log summary. Each T2 item says whether
the artifact shows traffic ("present"), could show it and shows none
("absent"), or cannot show it for this policy ("blind": no logging,
deactivated, artifact missing), see decision 0019.
T3 structural: address object names, policies created in the same commit.
T4 contextual: plain service names of the applications the policy matches.
"""

import re

from palimp.behavior import recurrence, time_of_day
from palimp.models import Dataset, Evidence, Finding, LogSummary, Policy, PolicyKey, Signal
from palimp.services import describe

TICKET_REF = re.compile(r"\b(?:CHG|INC|RITM|REQ|CR|SR|TASK)[-_]?\d{4,}\b", re.IGNORECASE)


def _resolve(dataset: Dataset, name: str) -> str:
    obj = dataset.config.addresses.get(name)
    if obj is None:
        return name
    if obj.kind == "address_set":
        return f"{name} = {{{', '.join(obj.members)}}}"
    return f"{name} = {obj.value}"


Item = tuple[str, str, str, str, Signal | None]
LIST_SHOWN = 5


def _some(values: list[str], count: int) -> str:
    shown = ", ".join(values[:LIST_SHOWN])
    return f"{count} ({shown}{', ...' if count > LIST_SHOWN else ''})" if count else "0"


def hit_count_items(dataset: Dataset, policy: Policy) -> list[Item]:
    artifact = "hitcount.txt"
    if dataset.hit_count_stats is None:
        return [
            (
                "T2",
                artifact,
                "hitcount.txt missing",
                "no hit counts were provided: use of this policy is unknown from counters",
                "blind",
            )
        ]
    row = next(
        (
            h
            for h in dataset.hit_counts
            if (h.from_zone, h.to_zone, h.name) == (policy.from_zone, policy.to_zone, policy.name)
        ),
        None,
    )
    locator = f"policy {policy.name} ({policy.from_zone} -> {policy.to_zone})"
    if row is None:
        if policy.deactivated:
            claim = "no row: deactivated policies match no traffic and are not listed"
        else:
            claim = "no row for this policy: its use is unknown from counters"
        return [("T2", artifact, locator, claim, "blind")]
    since = "since the counters were last cleared (the clear date is not in hitcount.txt)"
    if row.count:
        return [("T2", artifact, locator, f"{row.count} hits {since}", "present")]
    return [("T2", artifact, locator, f"0 hits {since}", "absent")]


def log_summary(dataset: Dataset, policy: Policy) -> LogSummary | None:
    summary = dataset.logs.get(str(policy.key))
    if summary is None:
        summary = dataset.logs.get(policy.name)
    return summary


def _span(dataset: Dataset) -> str:
    window = dataset.log_window
    if window.start is None or window.end is None:
        return "the log window (dates unknown)"
    days = (window.end.date() - window.start.date()).days + 1
    return f"the log window {window.start:%Y-%m-%d} to {window.end:%Y-%m-%d} ({days} days)"


def log_items(dataset: Dataset, policy: Policy) -> list[Item]:
    artifact = "logs/rt_flow.log"
    if dataset.log_stats is None:
        claim = "no session log was provided: traffic of this policy is unknown from logs"
        return [("T2", artifact, "logs/rt_flow.log missing", claim, "blind")]
    summary = log_summary(dataset, policy)
    locator = f'policy-name="{policy.name}"'
    if summary is not None and (summary.sessions or summary.deny):
        return [("T2", artifact, locator, _describe(dataset, summary), "present")]
    if policy.deactivated:
        claim = f"no session in {_span(dataset)}: the policy is deactivated, it matches no traffic"
        return [("T2", artifact, locator, claim, "blind")]
    if not (policy.log_init or policy.log_close):
        claim = (
            "the policy has no `then log` statement, so the log cannot show its traffic: "
            "no log line here says nothing about use (not the same as no traffic)"
        )
        return [("T2", artifact, f"policy {policy.name} has no logging", claim, "blind")]
    options = " and ".join(
        o
        for o, on in (("session-init", policy.log_init), ("session-close", policy.log_close))
        if on
    )
    claim = f"the policy logs {options}, and no session was logged in {_span(dataset)}"
    return [("T2", artifact, locator, claim, "absent")]


def _describe(dataset: Dataset, summary: LogSummary) -> str:
    parts = []
    if summary.sessions:
        when = ""
        if summary.first_seen and summary.last_seen:
            when = (
                f", first {summary.first_seen:%Y-%m-%d %H:%M}"
                f", last {summary.last_seen:%Y-%m-%d %H:%M}"
            )
        parts.append(f"{summary.sessions} sessions logged in {_span(dataset)}{when}")
        parts.append(f"sources {_some(summary.sources, summary.source_count)}")
        parts.append(f"destinations {_some(summary.destinations, summary.destination_count)}")
        if summary.ports:
            parts.append("ports " + ", ".join(summary.ports))
        if pattern := time_of_day(summary.hours, summary.weekdays):
            parts.append(f"time of day: {pattern}")
        window = dataset.log_window
        if hint := recurrence(
            summary.days,
            window.start.date() if window.start else None,
            window.end.date() if window.end else None,
        ):
            parts.append(f"recurrence: {hint}")
    if summary.deny:
        parts.append(f"{summary.deny} denied sessions")
    return "; ".join(parts)


def collect(dataset: Dataset, key: PolicyKey) -> Finding:
    policy = dataset.config.policy(key)
    if policy is None:
        raise KeyError(f"policy {key} not found in config.set")
    history = dataset.history.get(str(key))
    created = history.created_in_commit if history else None
    commit = next((c for c in dataset.commits if c.index == created), None)
    items: list[Item] = []

    if policy.description:
        items.append(
            ("T1", "config.set", f"policy {policy.name} description", policy.description, None)
        )
    if commit and commit.comment:
        when = f"{commit.timestamp:%Y-%m-%d %H:%M:%S} {commit.time_zone} by {commit.user}"
        items.append(("T1", "commits.txt", f"commit {commit.index} ({when})", commit.comment, None))

    places = [("name", policy.name), ("description", policy.description or "")]
    if commit:
        places.append((f"commit {commit.index} comment", commit.comment))
    seen: set[str] = set()
    for place, text in places:
        for ref in TICKET_REF.findall(text):
            ref = ref.upper()
            if ref in seen:
                continue
            seen.add(ref)
            ticket = dataset.tickets.get(ref)
            if ticket:
                details = ", ".join(
                    f"{label} {value}"
                    for label, value in (
                        ("requester", ticket.requester),
                        ("status", ticket.status),
                        ("opened", ticket.opened),
                    )
                    if value
                )
                claim = f"{ticket.summary or ''} ({details})".strip()
                items.append(
                    ("T1", "tickets.csv", f"ticket {ref} (referenced in {place})", claim, None)
                )
            else:
                artifact = "commits.txt" if place.startswith("commit") else "config.set"
                items.append(
                    (
                        "T1",
                        artifact,
                        f"ticket reference {ref} in {place}",
                        "not in tickets.csv",
                        None,
                    )
                )

    named = [n for n in policy.sources + policy.destinations if n != "any"]
    if named:
        claim = "; ".join(_resolve(dataset, n) for n in named)
        items.append(("T3", "config.set", "address objects " + ", ".join(named), claim, None))
    if created is not None:
        siblings = [k for k in dataset.created_by_commit.get(created, []) if k != str(key)]
        if siblings:
            locator = f"commit {created}: rollback-{created + 1:02d} vs " + (
                "config.set" if created == 0 else f"rollback-{created:02d}"
            )
            items.append(
                (
                    "T3",
                    "rollbacks",
                    locator,
                    "created together with " + ", ".join(siblings),
                    None,
                )
            )

    items += hit_count_items(dataset, policy) + log_items(dataset, policy)
    if policy.applications:
        services = [
            line
            for name in policy.applications
            for line in describe(name, dataset.config.applications)
        ]
        locator = "applications " + ", ".join(policy.applications)
        items.append(("T4", "config.set", locator, "; ".join(services), None))

    evidence = [
        Evidence(
            id=f"E{i}", tier=tier, artifact=artifact, locator=locator, claim=claim, signal=signal
        )
        for i, (tier, artifact, locator, claim, signal) in enumerate(items, start=1)
    ]
    return Finding(key=key, policy=policy, created_in_commit=created, evidence=evidence)


def collect_all(dataset: Dataset) -> list[Finding]:
    return [collect(dataset, p.key) for p in dataset.config.policies]
