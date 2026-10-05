"""Decommission leftovers: a positive not-live signal (decision 0020)."""

from pathlib import Path

from palimp.evidence import collect
from palimp.ingest import ingest
from palimp.models import PolicyKey

BASE = """\
set security address-book global address users-all 10.10.0.0/16
set security address-book global address hr-web-01 10.20.1.10/32
set security address-book global address crm-app-01 10.20.2.10/32
"""


def rule(name: str, source: str, destination: str) -> str:
    prefix = f"set security policies from-zone trust to-zone dc policy {name}"
    return (
        f"{prefix} match source-address {source}\n"
        f"{prefix} match destination-address {destination}\n"
        f"{prefix} match application junos-https\n"
        f"{prefix} then permit\n"
    )


LEFT = rule("hr-left", "users-all", "hr-web-01")
GONE = rule("hr-gone", "users-all", "hr-web-01")
CRM = rule("crm-to-hr", "crm-app-01", "hr-web-01")
COMMITS = """\
0   2026-03-02 10:00:00 UTC by bob via cli
1   2026-02-01 09:00:00 UTC by ann via cli
    HRP go live
"""
TICKETS = (
    "ticket_id,closed,requester,summary,related_ci\n"
    "CHG0000900,2026-03-02,Ann Example,HRP retirement - remove access,hr\n"
)


def make(tmp_path: Path) -> Path:
    (tmp_path / "rollbacks").mkdir()
    (tmp_path / "config.set").write_text(BASE + LEFT + CRM)
    (tmp_path / "rollbacks" / "rollback-01.set").write_text(BASE + LEFT + GONE + CRM)
    (tmp_path / "rollbacks" / "rollback-02.set").write_text(BASE)
    (tmp_path / "commits.txt").write_text(COMMITS)
    (tmp_path / "tickets.csv").write_text(TICKETS)
    return tmp_path


def test_leftover_of_a_decommission_is_a_removal_candidate(tmp_path: Path) -> None:
    dataset = ingest(make(tmp_path))
    assert [r.key for r in dataset.removed_by_commit[0]] == ["trust/dc/hr-gone"]
    finding = collect(dataset, PolicyKey.parse("trust/dc/hr-left"))
    item = next(e for e in finding.evidence if e.kind == "decommission")
    assert item.artifact == "tickets.csv" and item.apps == ["hr"]
    assert "trust/dc/hr-gone" in item.claim
    assert finding.assessment.verdict == "removal_candidate"
    assert finding.assessment.verdict_rule == "V-NOTLIVE"


def test_policy_naming_another_live_application_gets_no_signal(tmp_path: Path) -> None:
    dataset = ingest(make(tmp_path))
    finding = collect(dataset, PolicyKey.parse("trust/dc/crm-to-hr"))
    assert not [e for e in finding.evidence if e.kind == "decommission"]
    assert finding.assessment.verdict == "verify"
