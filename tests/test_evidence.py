"""Evidence collection on a small hand-written artifact directory."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from palimp.cli import app
from palimp.evidence import collect
from palimp.ingest import ingest
from palimp.models import PolicyKey

BASE = """\
set security address-book global address lan 10.10.0.0/16
set security address-book global address crm-web 10.20.1.10/32
set security address-book global address crm-db 10.20.1.20/32
set applications application tcp-3306 protocol tcp
set applications application tcp-3306 destination-port 3306
"""
CRM_WEB = """\
set security policies from-zone trust to-zone dc policy crm-web description "CRM FE 443"
set security policies from-zone trust to-zone dc policy crm-web match source-address lan
set security policies from-zone trust to-zone dc policy crm-web match destination-address crm-web
set security policies from-zone trust to-zone dc policy crm-web match application junos-https
set security policies from-zone trust to-zone dc policy crm-web then permit
"""
CRM_DB = """\
set security policies from-zone dc to-zone dc policy CHG0000777-db match source-address crm-web
set security policies from-zone dc to-zone dc policy CHG0000777-db match destination-address crm-db
set security policies from-zone dc to-zone dc policy CHG0000777-db match application tcp-3306
set security policies from-zone dc to-zone dc policy CHG0000777-db then permit
"""
COMMITS = """\
0   2026-03-02 10:00:00 UTC by bob via cli
    banner update
1   2026-02-01 09:00:00 UTC by ann via cli
    CHG0000777 CRM go-live
2   2026-01-05 09:00:00 UTC by ann via cli
"""
TICKETS = "ticket_id,requester,status,summary\nCHG0000777,Ann Example,closed,CRM go live\n"


@pytest.fixture
def artifacts(tmp_path: Path) -> Path:
    (tmp_path / "rollbacks").mkdir()
    after = BASE + CRM_WEB + CRM_DB
    (tmp_path / "config.set").write_text(after + "set system login message x\n")
    (tmp_path / "rollbacks" / "rollback-01.set").write_text(after)
    (tmp_path / "rollbacks" / "rollback-02.set").write_text(BASE)
    (tmp_path / "commits.txt").write_text(COMMITS)
    (tmp_path / "tickets.csv").write_text(TICKETS)
    return tmp_path


def test_creation_commit_found_by_diff(artifacts: Path) -> None:
    dataset = ingest(artifacts)
    assert dataset.history["trust/dc/crm-web"].created_in_commit == 1
    assert dataset.created_by_commit[1] == ["dc/dc/CHG0000777-db", "trust/dc/crm-web"]


def test_t1_and_t3_evidence(artifacts: Path) -> None:
    finding = collect(ingest(artifacts), PolicyKey.parse("dc/dc/CHG0000777-db"))
    found = [(e.tier, e.artifact) for e in finding.evidence]
    assert ("T1", "commits.txt") in found
    assert ("T1", "tickets.csv") in found
    assert ("T3", "config.set") in found
    assert ("T3", "rollbacks") in found
    ticket = next(e for e in finding.evidence if e.artifact == "tickets.csv")
    assert "referenced in name" in ticket.locator and "CRM go live" in ticket.claim
    assert [e.id for e in finding.evidence] == [f"E{i}" for i in range(1, len(found) + 1)]


def test_explain_cli_json(artifacts: Path) -> None:
    result = CliRunner().invoke(
        app, ["explain", "trust/dc/crm-web", "-a", str(artifacts), "--no-llm", "--json"]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["key"]["name"] == "crm-web"
    assert data["evidence"][0] == {
        "id": "E1",
        "tier": "T1",
        "artifact": "config.set",
        "locator": "policy crm-web description",
        "claim": "CRM FE 443",
    }


def test_explain_unknown_policy(artifacts: Path) -> None:
    result = CliRunner().invoke(app, ["explain", "a/b/c", "-a", str(artifacts), "--no-llm"])
    assert result.exit_code == 1


def test_ingest_writes_json(artifacts: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    result = CliRunner().invoke(app, ["ingest", str(artifacts), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert len(json.loads(out.read_text())["config"]["policies"]) == 2


def test_simulator_scenario_parses_cleanly(tmp_path: Path) -> None:
    """Black-box run of the simulator CLI, as a user would do."""
    subprocess.run(
        [
            sys.executable,
            "-m",
            "palimp_sim.cli",
            "generate",
            "--level",
            "easy",
            "--seed",
            "3",
            "--out",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
    )
    dataset = ingest(tmp_path / "scenario-easy-000003")
    assert dataset.config.stats.unknown == 0
    assert all(s.unknown == 0 for s in dataset.rollback_stats)
    assert dataset.config.policies and dataset.commits and dataset.tickets
