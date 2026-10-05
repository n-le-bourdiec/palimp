"""Who to ask: application owners from ticket requesters and initials (palimp.owners)."""

from datetime import datetime

from palimp.assess import assess
from palimp.formats.junos_set import parse_set
from palimp.models import Commit, Dataset, Evidence, Finding, Policy, Ticket
from palimp.owners import requester_items

POLICY = Policy(from_zone="trust", to_zone="dc", name="p1", position=0, destinations=["crm-db-01"])


def ticket(ticket_id: str, requester: str, ci: str, assignee: str = "jdoe") -> Ticket:
    return Ticket(ticket_id=ticket_id, requester=requester, related_ci=ci, assignee=assignee)


TICKETS = {
    t.ticket_id: t
    for t in (
        ticket("CHG1", "Ann Example", "crm"),
        ticket("CHG2", "Ann Example", "crm"),
        ticket("CHG3", "Bob Sample", "billing"),
        ticket("CHG4", "jdoe", "crm"),
    )
}
COMMIT = Commit(index=3, timestamp=datetime(2026, 1, 1), time_zone="UTC", user="jdoe", client="cli")


def dataset(tickets: dict | None = None) -> Dataset:
    return Dataset(
        source="t",
        config=parse_set(""),
        tickets=TICKETS if tickets is None else tickets,
        commits=[COMMIT],
    )


def owner_of(data: Dataset, objects: list[str], *extra: tuple) -> object:
    items = [("T3", "address_objects", "x", objects)]
    items += [("T3", "app_requesters", "x", [a]) for a in objects if requester_items(data, [a])]
    items += list(extra)
    items.append(("T2", "hit_count", "1 hits", []))
    evidence = [
        Evidence(
            id=f"E{i}",
            tier=tier,
            artifact="x",
            locator=locator,
            claim=claim,
            kind=kind,
            apps=apps,
            signal="present" if tier == "T2" else None,
        )
        for i, (tier, kind, claim, apps) in enumerate(items, start=1)
        for locator in [f"ticket {claim} (referenced in name)" if kind == "ticket" else "x"]
    ]
    finding = Finding(key=POLICY.key, policy=POLICY, created_in_commit=3, evidence=evidence)
    return assess(finding, data)


def test_requesters_of_one_application_name_its_owner() -> None:
    result = owner_of(dataset(), ["crm"])
    assert result.owner == "Ann Example"
    assert "2 of 2 tickets for crm [E2]" in result.ask
    # The admin login that requested CHG4 is never an owner, and is named apart.
    assert "jdoe" not in result.owner_candidates
    assert "Administrator who created the policy: jdoe" in result.ask


def test_one_ticket_is_a_candidate_not_an_owner() -> None:
    result = owner_of(dataset(), ["billing"])
    assert result.owner is None and result.owner_candidates == ["Bob Sample"]
    assert result.ask.startswith("Not sure who owns it")


def test_two_applications_never_give_a_certain_owner() -> None:
    result = owner_of(dataset(), ["crm", "billing"])
    assert result.owner is None
    assert result.owner_candidates == ["Ann Example", "Bob Sample"]
    assert "either side may own it" in result.ask


def test_initials_confirm_a_single_ticket() -> None:
    initials = ("T1", "description", "user PC xy-1 > BILL DB req BS", ["billing"])
    result = owner_of(dataset(), ["billing"], initials)
    assert result.owner == "Bob Sample"
    assert "initials BS after req in [E3]" in result.ask


def test_unresolved_or_other_initials_keep_the_doubt() -> None:
    other = ("T1", "description", "CRM db access req ZZ", ["crm"])
    result = owner_of(dataset(), ["crm"], other)
    assert result.owner is None and result.owner_candidates == ["Ann Example"]
    assert "initials ZZ" in result.ask


def test_no_ticket_no_name() -> None:
    result = owner_of(dataset({}), ["crm"])
    assert result.owner is None and result.owner_candidates == []
    assert "no name in the artifacts" in result.ask
