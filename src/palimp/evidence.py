"""Deterministic evidence collectors. No scoring here.

T1 direct: policy description, comment of the commit that created the policy,
ticket references found in the name, description or that comment (matched
against tickets.csv when present).
T3 structural: address object names, policies created in the same commit.
"""

import re

from palimp.models import Dataset, Evidence, Finding, PolicyKey

TICKET_REF = re.compile(r"\b(?:CHG|INC|RITM|REQ|CR|SR|TASK)[-_]?\d{4,}\b", re.IGNORECASE)


def _resolve(dataset: Dataset, name: str) -> str:
    obj = dataset.config.addresses.get(name)
    if obj is None:
        return name
    if obj.kind == "address_set":
        return f"{name} = {{{', '.join(obj.members)}}}"
    return f"{name} = {obj.value}"


def collect(dataset: Dataset, key: PolicyKey) -> Finding:
    policy = dataset.config.policy(key)
    if policy is None:
        raise KeyError(f"policy {key} not found in config.set")
    history = dataset.history.get(str(key))
    created = history.created_in_commit if history else None
    commit = next((c for c in dataset.commits if c.index == created), None)
    items: list[tuple[str, str, str, str]] = []

    if policy.description:
        items.append(("T1", "config.set", f"policy {policy.name} description", policy.description))
    if commit and commit.comment:
        when = f"{commit.timestamp:%Y-%m-%d %H:%M:%S} {commit.time_zone} by {commit.user}"
        items.append(("T1", "commits.txt", f"commit {commit.index} ({when})", commit.comment))

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
                items.append(("T1", "tickets.csv", f"ticket {ref} (referenced in {place})", claim))
            else:
                artifact = "commits.txt" if place.startswith("commit") else "config.set"
                items.append(
                    ("T1", artifact, f"ticket reference {ref} in {place}", "not in tickets.csv")
                )

    named = [n for n in policy.sources + policy.destinations if n != "any"]
    if named:
        claim = "; ".join(_resolve(dataset, n) for n in named)
        items.append(("T3", "config.set", "address objects " + ", ".join(named), claim))
    if created is not None:
        siblings = [k for k in dataset.created_by_commit.get(created, []) if k != str(key)]
        if siblings:
            locator = f"commit {created}: rollback-{created + 1:02d} vs " + (
                "config.set" if created == 0 else f"rollback-{created:02d}"
            )
            items.append(
                ("T3", "rollbacks", locator, "created together with " + ", ".join(siblings))
            )

    evidence = [
        Evidence(id=f"E{i}", tier=tier, artifact=artifact, locator=locator, claim=claim)
        for i, (tier, artifact, locator, claim) in enumerate(items, start=1)
    ]
    return Finding(key=key, policy=policy, created_in_commit=created, evidence=evidence)


def collect_all(dataset: Dataset) -> list[Finding]:
    return [collect(dataset, p.key) for p in dataset.config.policies]
