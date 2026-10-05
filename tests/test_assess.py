"""Verdict and confidence rules (decision 0020), on hand-built findings."""

from palimp.apps import vocabulary
from palimp.assess import assess
from palimp.formats.junos_set import parse_set
from palimp.models import Dataset, Evidence, Finding, Policy, PolicyKey, Ticket

POLICY = Policy(from_zone="trust", to_zone="dc", name="p1", position=0, destinations=["crm-db-01"])


def finding(*items: tuple) -> Finding:
    evidence = [
        Evidence(
            id=f"E{i}",
            tier=tier,
            artifact="x",
            locator="ticket CHG0000001 (referenced in name)" if kind == "ticket" else "x",
            claim="c",
            signal=signal,
            kind=kind,
            apps=apps,
        )
        for i, (tier, kind, signal, apps) in enumerate(items, start=1)
    ]
    return Finding(key=POLICY.key, policy=POLICY, created_in_commit=None, evidence=evidence)


DATASET = Dataset(
    source="test",
    config=parse_set(""),
    tickets={"CHG0000001": Ticket(ticket_id="CHG0000001", requester="Ann Example")},
)
HITS_ZERO = ("T2", "hit_count", "absent", [])
HITS = ("T2", "hit_count", "present", [])
LOG_ZERO = ("T2", "session_log", "absent", [])
LOG = ("T2", "session_log", "present", [])
NO_LOG = ("T2", "session_log", "blind", [])
OBJECTS = ("T3", "address_objects", None, ["crm"])


def verdict(*items: tuple) -> tuple[str, str]:
    result = assess(finding(*items), DATASET)
    return result.verdict, result.verdict_rule


def test_absence_alone_never_gives_removal() -> None:
    assert verdict(HITS_ZERO, LOG_ZERO, OBJECTS) == ("verify", "V-NO-TRAFFIC-SEEN")
    assert verdict(HITS_ZERO, NO_LOG) == ("verify", "V-NO-TRAFFIC-SEEN")
    assert verdict(NO_LOG) == ("verify", "V-NO-VISIBILITY")


def test_positive_not_live_signal_gives_removal() -> None:
    deactivated = ("T3", "deactivated", None, [])
    assert verdict(deactivated, NO_LOG) == ("removal_candidate", "V-NOTLIVE")
    result = assess(finding(deactivated, HITS_ZERO), DATASET)
    assert result.verdict_evidence == ["E1", "E2"]


def test_not_live_signal_with_traffic_is_a_contradiction() -> None:
    assert verdict(("T3", "decommission", None, []), HITS) == ("verify", "V-CONTRADICTION")


def test_traffic_rules() -> None:
    assert verdict(HITS, LOG) == ("keep", "V-TRAFFIC")
    assert verdict(HITS, NO_LOG) == ("keep", "V-TRAFFIC")
    assert verdict(HITS, LOG_ZERO) == ("verify", "V-TRAFFIC-NOT-RECENT")
    temporary = ("T3", "temporary_marker", None, [])
    assert verdict(temporary, HITS) == ("keep", "V-TRAFFIC")
    broad = assess(
        finding(temporary, ("T4", "services", None, []), HITS),
        DATASET,
    )
    assert broad.verdict == "keep"  # POLICY does not permit any application
    POLICY.applications = ["any"]
    try:
        assert verdict(temporary, ("T4", "services", None, []), HITS) == (
            "verify",
            "V-TEMPORARY-IN-USE",
        )
    finally:
        POLICY.applications = []


def test_confidence_levels() -> None:
    def level(*items: tuple) -> tuple[str, str]:
        result = assess(finding(*items), DATASET)
        return result.confidence, result.confidence_rule

    t1_crm = ("T1", "description", None, ["crm"])
    assert level(t1_crm, OBJECTS, HITS) == ("HIGH", "C-T1-T3-AGREE")
    assert level(t1_crm, OBJECTS, HITS_ZERO) == ("MEDIUM", "C-T1-T3-AGREE-NO-TRAFFIC")
    assert level(t1_crm, HITS) == ("MEDIUM", "C-T1-ONLY")
    assert level(OBJECTS, HITS) == ("MEDIUM", "C-T3")
    assert level(("T4", "services", None, []), HITS) == ("LOW", "C-WEAK")
    assert level(("T1", "commit_comment", None, []), HITS) == ("LOW", "C-WEAK")


def test_conflict_lowers_confidence_and_cites_both() -> None:
    result = assess(finding(("T1", "commit_comment", None, ["pos"]), OBJECTS, HITS), DATASET)
    assert (result.confidence, result.confidence_rule) == ("LOW", "C-T1-T3-CONFLICT")
    assert result.conflicts[0].evidence == ["E1", "E2"]
    agreeing = ("T1", "description", None, ["crm"])
    result = assess(
        finding(agreeing, ("T1", "commit_comment", None, ["pos"]), OBJECTS, HITS), DATASET
    )
    assert result.confidence == "MEDIUM" and result.intent_apps == ["crm"]


def test_question_and_owner_only_when_not_keep() -> None:
    assert assess(finding(OBJECTS, HITS, LOG), DATASET).question is None
    ticket = ("T1", "ticket", None, ["crm"])
    result = assess(finding(ticket, OBJECTS, HITS_ZERO), DATASET)
    assert result.question and "Ann Example" in result.ask


def test_vocabulary_learns_aliases_from_tickets() -> None:
    config = parse_set(
        "set security address-book global address webshop-app-01 10.0.0.1/32\n"
        "set security address-book global address vendor-arch-109 10.0.0.2/32\n"
        "set security address-book global address archive-file-01 10.0.0.3/32\n"
        "set security address-book global address pc-kc-111 10.0.0.4/32\n"
    )
    tickets = {
        "CHG1": Ticket(ticket_id="CHG1", summary="Decom ESHOP", related_ci="webshop"),
        "CHG2": Ticket(ticket_id="CHG2", summary="FW request ESHOP", related_ci="webshop"),
        "CHG3": Ticket(ticket_id="CHG3", summary="FW request NTP", related_ci="shared-ntp"),
    }
    vocab = vocabulary(Dataset(source="t", config=config, tickets=tickets))
    assert vocab.in_text("CHG0030016 ESHOP go-live, 2 rules") == ["webshop"]
    assert vocab.in_text("NTP - open flows pls") == ["ntp"]
    assert "fw" not in vocab.aliases  # seen with two related CIs
    assert vocab.in_object("vendor-arch-109") == []
    assert vocab.in_object("webshop-app-01") == ["webshop"]
    assert vocab.in_object("pc-kc-111") == []
    assert PolicyKey.parse("a/b/c").name == "c"
