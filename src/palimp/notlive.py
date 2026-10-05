"""Positive not-live signals (decision 0020): artifacts that say a policy is unused.

Decommission leftover: a commit comment or a ticket decommissions or retires an
application, the change that did it deleted policies referencing an address
object named after that application, and this policy, older than the change,
references the same object and was left behind.

Both links are required. The application name alone is not enough: an object
`payroll-provider` (an outside partner) is not the retired internal payroll
servers. The deleted policies show which objects the decommission was about.
Every application the policy's objects name must be retired by the same
change: a policy from a live application to the retired one's partner may
still carry that live application's traffic.

A ticket is linked to the commits whose comment cites it, or else to the
commits made on the day it was closed. A change that cannot be linked to a
commit of the retained history gives no signal.
"""

import re
from dataclasses import dataclass

from palimp.apps import Vocabulary
from palimp.models import Dataset, Policy

DECOMMISSION = re.compile(
    r"\b(?:decom\w*|retire\w*|sunset\w*|shut\s*down|end[- ]of[- ]life)\b", re.IGNORECASE
)


@dataclass
class Marker:
    artifact: str
    locator: str
    text: str
    apps: list[str]
    commits: list[int]


def markers(dataset: Dataset, vocab: Vocabulary) -> list[Marker]:
    found: list[Marker] = []
    for commit in dataset.commits:
        if DECOMMISSION.search(commit.comment):
            apps = vocab.in_text(commit.comment)
            if apps:
                when = f"{commit.timestamp:%Y-%m-%d} by {commit.user}"
                locator = f"commit {commit.index} ({when})"
                found.append(Marker("commits.txt", locator, commit.comment, apps, [commit.index]))
    for ticket in dataset.tickets.values():
        if not DECOMMISSION.search(ticket.summary or ""):
            continue
        apps = vocab.in_text(ticket.summary or "")
        if ticket.related_ci and (ci := vocab.lookup(ticket.related_ci.removeprefix("shared-"))):
            apps = [ci] + [a for a in apps if a != ci]
        if not apps:
            continue
        linked = [c.index for c in dataset.commits if ticket.ticket_id in c.comment]
        if not linked and ticket.closed:
            day = ticket.closed[:10]
            linked = [c.index for c in dataset.commits if f"{c.timestamp:%Y-%m-%d}" == day]
        if linked:
            locator = f"ticket {ticket.ticket_id} (closed {ticket.closed or '?'})"
            found.append(Marker("tickets.csv", locator, ticket.summary or "", apps, linked))
    return found


def decommission_items(
    dataset: Dataset, policy: Policy, created: int | None, found: list[Marker], vocab: Vocabulary
) -> list[tuple[str, str, str, list[str]]]:
    """(artifact, locator, claim, apps) for each decommission this policy was left behind by."""
    objects = {o for o in policy.sources + policy.destinations if o != "any"}
    named = {a for o in objects for a in vocab.in_object(o)}
    items = []
    for marker in found:
        if not named or not named <= set(marker.apps):
            continue  # another application on this policy may still need it
        for index in marker.commits:
            if created is not None and index >= created:
                continue  # the change is older than the policy
            removed = dataset.removed_by_commit.get(index, [])
            shared = sorted(
                o
                for o in objects
                if set(vocab.in_object(o)) & set(marker.apps)
                and any(o in r.sources + r.destinations for r in removed)
            )
            if not shared:
                continue
            deleted = [r.key for r in removed if set(shared) & set(r.sources + r.destinations)]
            claim = (
                f'"{marker.text}" retires {", ".join(marker.apps)}; commit {index} deleted '
                f"{len(deleted)} policies referencing {', '.join(shared)} "
                f"({', '.join(deleted[:3])}{', ...' if len(deleted) > 3 else ''}), "
                "and this older policy, which references the same objects, was left behind"
            )
            items.append((marker.artifact, marker.locator, claim, marker.apps))
            break
    return items
