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

Decision 0051 (audit B1): the text is a not-live signal ("decommission") only
when, on top of those links,
- it names an address, host or object of this rule (an object name, an
  address of one, a DNS name), not only an application word that other
  rules share;
- it is neither negated nor conditional ("do not", "not yet", "once",
  "after", "until");
- its environment matches the rule's scope: a test, staging or dev word in
  the text applies only to a rule whose objects carry the same word;
- it is linked to the commit by a citation (the commit comment itself, or a
  ticket that a commit comment cites), not by a closing day alone.
Otherwise the item is a question ("decommission_question"): the verdict is
at most verify.
"""

import re
from dataclasses import dataclass

from palimp.apps import Vocabulary
from palimp.lineage import networks
from palimp.models import Dataset, Policy

DECOMMISSION = re.compile(
    r"\b(?:decom\w*|retire\w*|sunset\w*|shut\s*down|end[- ]of[- ]life)\b", re.IGNORECASE
)
# Negated or conditional wording (decision 0051): the text does not say the retirement
# happened.
DOUBT = re.compile(
    r"\b(?:not|never|cannot|\w+n't|yet|once|after|until|unless|if|when|pending|planned|plan"
    r"|scheduled|will|later|before|maybe|possibly|candidate)\b",
    re.IGNORECASE,
)
# Environment words, by family: a text about one applies only to objects of that family.
ENVIRONMENTS = {
    "test": "test",
    "tests": "test",
    "testing": "test",
    "tst": "test",
    "staging": "staging",
    "stage": "staging",
    "stg": "staging",
    "dev": "dev",
    "devel": "dev",
    "development": "dev",
    "qa": "qa",
    "uat": "uat",
    "preprod": "preprod",
    "sandbox": "sandbox",
    "lab": "lab",
    "poc": "poc",
    "demo": "demo",
}
TOKEN = re.compile(r"[\w.:/-]+")


@dataclass
class Marker:
    artifact: str
    locator: str
    text: str
    apps: list[str]
    commits: list[int]
    # True when a commit comment is the text, or cites the ticket; False for a ticket
    # linked by its closing day alone.
    cited: bool = True


def _environments(text: str) -> set[str]:
    words = re.split(r"[^a-z0-9]+", text.lower())
    return {ENVIRONMENTS[w] for w in words if w in ENVIRONMENTS}


def _names(dataset: Dataset, name: str, depth: int = 0) -> set[str]:
    """Lowercase names an object goes by: its name, members, addresses and DNS name."""
    found = {name.lower()}
    obj = dataset.config.addresses.get(name) or dataset.past_addresses.get(name)
    if obj is None or depth > 8:
        return found
    if obj.kind == "address_set":
        for member in obj.members:
            found |= _names(dataset, member, depth + 1)
        return found
    value = (obj.value or "").split()
    if value:
        found.add(value[0].lower())
        host = value[0].lower().rstrip(".")
        if "/" not in host and not host[:1].isdigit():
            found.add(host.split(".")[0])  # dns-name: the host label too
    for net in networks(dataset, name) or []:
        if net.num_addresses == 1:
            found.add(str(net.network_address))
        found.add(str(net))
    return found


def doubts(dataset: Dataset, policy: Policy, marker: Marker, shared: list[str]) -> list[str]:
    """Why a decommission text is not a not-live signal for this policy (decision 0051).

    The text must name one of the SHARED objects: an object of this rule that the deleted
    policies referenced too. Another object of the rule named in the text may be the
    replacement ("retire app-03, replaced by app-04")."""
    reasons = []
    objects = [o for o in policy.sources + policy.destinations if o != "any"]
    words = {t.lower().strip(".,;:()") for t in TOKEN.findall(marker.text)}
    words -= {a.lower() for a in marker.apps}  # an application word names no rule object
    if not any(words & _names(dataset, o) for o in shared):
        reasons.append(
            "it names no address, host or object of this rule that the deleted policies "
            "referenced too"
        )
    if DOUBT.search(marker.text):
        reasons.append("it is negated or conditional")
    wanted = _environments(marker.text)
    if wanted and not wanted & {e for o in objects for e in _environments(o)}:
        reasons.append(
            f"it is about a {'/'.join(sorted(wanted))} environment, and no object of this rule is"
        )
    if not marker.cited:
        reasons.append("the ticket is linked to the change only by its closing day")
    return reasons


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
        cited = bool(linked)
        if not linked and ticket.closed:
            day = ticket.closed[:10]
            linked = [c.index for c in dataset.commits if f"{c.timestamp:%Y-%m-%d}" == day]
        if linked:
            locator = f"ticket {ticket.ticket_id} (closed {ticket.closed or '?'})"
            text = ticket.summary or ""
            found.append(Marker("tickets.csv", locator, text, apps, linked, cited))
    return found


def decommission_items(
    dataset: Dataset, policy: Policy, created: int | None, found: list[Marker], vocab: Vocabulary
) -> list[tuple[str, str, str, list[str], str]]:
    """(artifact, locator, claim, apps, kind) for each decommission this policy was left
    behind by: kind "decommission" (a not-live signal) or "decommission_question"."""
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
            kind = "decommission"
            if reasons := doubts(dataset, policy, marker, shared):
                kind = "decommission_question"
                claim += (
                    f". Not a sign that this rule is unused: {'; '.join(reasons)}, so it is "
                    "a question for the owner"
                )
            items.append((marker.artifact, marker.locator, claim, marker.apps, kind))
            break
    return items
