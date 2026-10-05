"""Who to ask about a policy: application owners found in the artifacts.

Plain rules, no scoring weights. Candidates come from:
- the requester of a ticket the policy references (name, description or the
  comment of the commit that created it);
- the requesters of the tickets whose related CI is an application the
  intent names (`app_requesters` evidence items);
- initials after "req" in the description or the commit comment
  (`req FP`), resolved to the one ticket requester with those initials.

Administrators (commit users, ticket assignees) are kept apart: they made the
change, they are not application owners, and are never named as one.

One owner is stated as certain only when every source points to the same
person (no other candidate, no unresolved initials), the policy involves one
application only (a flow between two applications may belong to either side),
the intent shows no T1-T3 conflict, and either the application has
at least two tickets all requested by that person, or two different sources
agree. Otherwise palimp says it is not sure and lists the candidates.
"""

import re
from dataclasses import dataclass, field

from palimp.models import Dataset, Evidence, Finding

INITIALS_REF = re.compile(r"\breq(?:uested by)?\.?\s*:?\s+([A-Z]{2,3})\b")
# Tickets needed for the requester of an application to be stated as its owner alone.
MIN_TICKETS = 2


def admins(dataset: Dataset) -> set[str]:
    """Logins and names of people who change the firewall, not application owners."""
    found = {c.user for c in dataset.commits if c.user}
    found |= {t.assignee for t in dataset.tickets.values() if t.assignee}
    return found


def _app(related_ci: str | None) -> str:
    return (related_ci or "").strip().lower().removeprefix("shared-")


def requesters(dataset: Dataset, app: str) -> dict[str, list[str]]:
    """Requester name -> ticket IDs, for the tickets whose related CI is `app`."""
    staff = admins(dataset)
    found: dict[str, list[str]] = {}
    for ticket in sorted(dataset.tickets.values(), key=lambda t: t.ticket_id):
        if _app(ticket.related_ci) == app and ticket.requester and ticket.requester not in staff:
            found.setdefault(ticket.requester, []).append(ticket.ticket_id)
    return found


def requester_items(dataset: Dataset, apps: list[str]) -> list[tuple[str, str, list[str]]]:
    """(locator, claim, apps) of one `app_requesters` item per application with tickets."""
    items = []
    for app in apps:
        found = requesters(dataset, app)
        if not found:
            continue
        ranked = sorted(found.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        claim = "requested by " + "; ".join(
            f"{name} ({len(ids)} of {sum(len(v) for v in found.values())}: {', '.join(ids)})"
            for name, ids in ranked
        )
        items.append((f"tickets with related CI {app}", claim, [app]))
    return items


def initials(name: str) -> str:
    return "".join(word[0] for word in name.split() if word).upper()


@dataclass
class Owner:
    owner: str | None = None
    candidates: list[str] = field(default_factory=list)
    text: str = ""


def _staff_note(finding: Finding, dataset: Dataset) -> str:
    commit = next((c for c in dataset.commits if c.index == finding.created_in_commit), None)
    if commit is None:
        return ""
    return (
        f" Administrator who created the policy: {commit.user} (commit {commit.index}), "
        "who made the change but is not an application owner."
    )


def find_owner(finding: Finding, dataset: Dataset, apps: list[str], conflict: bool) -> Owner:
    evidence = finding.evidence
    staff = admins(dataset)
    # name -> reasons; sources: name -> set of source kinds that point to it.
    reasons: dict[str, list[str]] = {}
    sources: dict[str, set[str]] = {}

    def vote(name: str, source: str, reason: str) -> None:
        reasons.setdefault(name, []).append(reason)
        sources.setdefault(name, set()).add(source)

    for item in [e for e in evidence if e.kind == "ticket"]:
        ticket = dataset.tickets.get(item.locator.split()[1])
        if ticket and ticket.requester and ticket.requester not in staff:
            vote(ticket.requester, "ticket", f"requester of {ticket.ticket_id} [{item.id}]")

    solid_app = False
    by_app: dict[str, Evidence] = {
        e.apps[0]: e for e in evidence if e.kind == "app_requesters" and e.apps
    }
    for app in apps:
        item = by_app.get(app)
        if item is None:
            continue
        found = requesters(dataset, app)
        total = sum(len(ids) for ids in found.values())
        for name, ids in found.items():
            vote(name, "app", f"requester of {len(ids)} of {total} tickets for {app} [{item.id}]")
        if len(found) == 1 and total >= MIN_TICKETS:
            solid_app = True

    known = {t.requester for t in dataset.tickets.values() if t.requester} - staff
    for item in [e for e in evidence if e.kind in ("description", "commit_comment")]:
        for letters in INITIALS_REF.findall(item.claim):
            matches = sorted(n for n in known if initials(n) == letters)
            if len(matches) == 1:
                vote(matches[0], "initials", f"initials {letters} after req in [{item.id}]")
            else:
                reasons.setdefault(f"initials {letters}", []).append(
                    f"after req in [{item.id}], "
                    + ("no ticket requester has them" if not matches else "several people match")
                )

    names = [n for n in reasons if not n.startswith("initials ")]
    unresolved = [n for n in reasons if n.startswith("initials ")]
    ranked = sorted(names, key=lambda n: (-len(sources[n]), -len(reasons[n]), n))
    staff_note = _staff_note(finding, dataset)
    if len(ranked) == 1 and len(apps) == 1 and not conflict and not unresolved:
        name = ranked[0]
        if solid_app or len(sources[name]) >= 2:
            text = f"{name}, application owner ({'; '.join(reasons[name])})."
            return Owner(owner=name, candidates=[name], text=text + staff_note)
    if ranked or reasons:
        why = "; ".join(f"{n}: {', '.join(reasons[n])}" for n in ranked + unresolved)
        doubt = " the intent evidence conflicts," if conflict else ""
        if len(apps) > 1:
            doubt += f" the flow involves {', '.join(apps)}, either side may own it,"
        text = f"Not sure who owns it:{doubt} candidates are {why}."
        return Owner(candidates=ranked, text=text + staff_note)
    if apps:
        text = f"The owner of application {', '.join(apps)}: no name in the artifacts."
    else:
        targets = ", ".join(finding.policy.destinations) or "the destination"
        text = f"No owner in the artifacts: ask the team that runs {targets}."
    return Owner(text=text + staff_note)
