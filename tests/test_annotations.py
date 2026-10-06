"""Annotations as T1 evidence, and hierarchical rollbacks (decision 0032).

A small hand-written artifact directory in hierarchical format: the active
configuration annotates one policy, the rollbacks are hierarchical too (one
in set format, to check that formats can be mixed).
"""

from pathlib import Path

import pytest

from palimp.evidence import collect
from palimp.ingest import ingest
from palimp.models import PolicyKey
from palimp.prose import Names, check, evidence_text, free_text_ids
from palimp.report import build

BOOK = """\
security {
    address-book {
        global {
            address lan 10.10.0.0/16;
            address crm-web 10.20.1.10/32;
        }
    }
"""
CRM = """\
        from-zone trust to-zone dc {
            /* CRM front end, CHG0000777, req AE, temporary until the new proxy */
            policy crm-web {
                match {
                    source-address lan;
                    destination-address crm-web;
                    application junos-https;
                }
                then {
                    permit;
                }
            }
        }
"""
OTHER = """\
        from-zone trust to-zone dc {
            policy ntp {
                match {
                    source-address lan;
                    destination-address any;
                    application junos-ntp;
                }
                then {
                    permit;
                }
            }
        }
"""
COMMITS = """\
0   2026-03-02 10:00:00 UTC by bob via cli
    banner update
1   2026-02-01 09:00:00 UTC by ann via cli
    CRM go-live
2   2026-01-05 09:00:00 UTC by ann via cli
"""
TICKETS = (
    "ticket_id,requester,status,summary,related_ci\n"
    "CHG0000777,Alice Example,closed,CRM go live,crm\n"
)


def hierarchical(*policies: str) -> str:
    return BOOK + "    policies {\n" + "".join(policies) + "    }\n}\n"


@pytest.fixture
def artifacts(tmp_path: Path) -> Path:
    (tmp_path / "rollbacks").mkdir()
    after = hierarchical(OTHER, CRM)
    (tmp_path / "config.set").write_text("## Last commit: 2026-03-02 by bob\n" + after)
    (tmp_path / "rollbacks" / "rollback-01.set").write_text(after)
    ntp = "set security policies from-zone trust to-zone dc policy ntp "
    (tmp_path / "rollbacks" / "rollback-02.set").write_text(
        "set security address-book global address lan 10.10.0.0/16\n"
        f"{ntp}match source-address lan\n"
        f"{ntp}match destination-address any\n"
        f"{ntp}match application junos-ntp\n"
        f"{ntp}then permit\n"
    )
    (tmp_path / "commits.txt").write_text(COMMITS)
    (tmp_path / "tickets.csv").write_text(TICKETS)
    return tmp_path


KEY = PolicyKey(from_zone="trust", to_zone="dc", name="crm-web")


def test_formats_detected_per_file(artifacts: Path) -> None:
    dataset = ingest(artifacts)
    assert dataset.config.stats.format == "hierarchical"
    assert [s.format for s in dataset.rollback_stats] == ["hierarchical", "set"]
    assert dataset.config.stats.unknown == 0


def test_creation_commit_from_hierarchical_rollbacks(artifacts: Path) -> None:
    dataset = ingest(artifacts)
    assert dataset.history[str(KEY)].created_in_commit == 1
    assert dataset.history["trust/dc/ntp"].created_in_commit is None


def test_annotation_is_t1_evidence(artifacts: Path) -> None:
    finding = collect(ingest(artifacts), KEY)
    (note,) = [e for e in finding.evidence if e.kind == "annotation"]
    assert note.tier == "T1" and note.locator == "policy crm-web annotation"
    assert note.claim.startswith("CRM front end, CHG0000777")
    kinds = {e.kind for e in finding.evidence}
    # The ticket it references, and the temporary word in it.
    assert "ticket" in kinds and "temporary_marker" in kinds
    ticket = next(e for e in finding.evidence if e.kind == "ticket")
    assert ticket.locator == "ticket CHG0000777 (referenced in annotation)"


def test_annotation_names_the_owner(artifacts: Path) -> None:
    finding = collect(ingest(artifacts), KEY)
    assert finding.assessment is not None
    assert "Alice Example" in finding.assessment.owner_candidates


def test_annotation_is_untrusted_text_in_validation(artifacts: Path) -> None:
    dataset = ingest(artifacts)
    report = build(dataset)
    entry = next(r for r in report.rules if r.finding.key == KEY)
    names = Names.of(dataset, [r.finding for r in report.rules])
    note = next(e for e in entry.finding.evidence if e.kind == "annotation")
    a = entry.finding.assessment
    assert a is not None
    assert note.id in free_text_ids(entry.finding)
    # Free text licenses only its ticket references and the applications palimp found.
    assert evidence_text(entry.finding)[note.id].endswith("annotation: CHG0000777 crm")

    def judge(sentence: str) -> str | None:
        items = evidence_text(entry.finding)
        free = free_text_ids(entry.finding)
        return check(sentence, items, names, a.verdict, a.confidence, free)

    i = note.id
    assert judge(f"The rule serves the new proxy until 2026-05-01 [{i}].") is not None
    assert judge(f"The rule is required by the business [{i}].") == (
        "free text stated as fact, not attributed to its artifact"
    )
    assert judge(f"The policy annotation refers to change CHG0000777 [{i}].") is None
