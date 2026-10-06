"""`palimp report` and `palimp questions`: citations, coverage, removal candidates.

Checked on Easy seed 0 (fast) and on Medium dev seeds
0 to 4 (slow). Black box: the simulator writes a scenario, palimp reads only its
artifacts.
"""

import csv
import io
import ipaddress
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from palimp.addresses import is_public
from palimp.assess import NOT_LIVE_KINDS
from palimp.cli import app
from palimp.evidence import collect_all
from palimp.ingest import ingest
from palimp.questions import answers_csv, cleanup_list
from palimp.questions import build as build_questions
from palimp.report import (
    FIREWALL_TEAM,
    LOOK_SHOWN,
    RISKS,
    Report,
    build,
    cited_ids,
    counters_only,
    internet_facing,
    is_cleanup,
    look_risk,
    markdown,
    worth_a_look,
)

RULE_HEADING = re.compile(r"^#{3,4} (R\d+) `([^`]+)`")
TABLE_ROW = re.compile(r"^\| (R\d+) \| `([^`]+)` \|")


def generate(seed: int, out: Path, level: str = "medium") -> Path:
    command = [sys.executable, "-m", "palimp_sim.cli", "generate", "--level", level]
    subprocess.run(
        command + ["--seed", str(seed), "--out", str(out)], check=True, capture_output=True
    )
    return out / f"scenario-{level}-{seed:06d}"


@pytest.fixture(scope="module")
def easy(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return generate(0, tmp_path_factory.mktemp("easy"), "easy") / "artifacts"


def unknown_citations(report: Report, text: str) -> list[str]:
    """Citations of the Markdown text that point to no evidence item."""
    ids = {r.ref: {e.id for e in r.finding.evidence} for r in report.rules}
    known_global = {g.id for g in report.global_evidence}
    bad = []
    current = None
    for line in text.splitlines():
        row = TABLE_ROW.match(line)
        if heading := RULE_HEADING.match(line):
            current = heading.group(1)
        elif line.startswith(("## ", "### ")):
            current = None
        context = row.group(1) if row else current
        for cited in cited_ids(line):
            if cited.startswith("G"):
                ok = cited in known_global
            elif "." in cited:
                ref, item = cited.split(".")
                ok = item in ids.get(ref, set())
            else:
                ok = context is not None and cited in ids[context]
            if not ok:
                bad.append(f"{context}: {cited} in {line[:80]}")
    return bad


def entries(text: str) -> list[tuple[str, str]]:
    """(ref, key) of every rule entry: a rule heading or a row of the keep table."""
    found = []
    for line in text.splitlines():
        if match := RULE_HEADING.match(line) or TABLE_ROW.match(line):
            found.append((match.group(1), match.group(2)))
    return found


def check(report: Report) -> None:
    text = markdown(report)
    assert unknown_citations(report, text) == []
    # Every policy of the configuration appears exactly once.
    listed = entries(text)
    assert sorted(listed) == sorted((r.ref, r.key) for r in report.rules)
    assert len({key for _, key in listed}) == len(listed)
    # The JSON report cites only existing items too.
    for rule in report.rules:
        ids = {e.id for e in rule.finding.evidence}
        for cited in [rule.allows, rule.intent, *rule.why]:
            assert set(cited.evidence) <= ids, (rule.ref, cited)
    # No removal candidate without a positive not-live item, cited in its section.
    for rule in report.rules:
        if rule.section != "removal_candidate":
            continue
        items = {e.id: e for e in rule.finding.evidence}
        cited = {i for c in rule.why for i in c.evidence}
        assert any(items[i].kind in NOT_LIVE_KINDS for i in cited), rule.ref
    # Questionnaires (decision 0026): every rule to verify or remove is asked, never keep;
    # deactivated ones only of the firewall team; one email per person.
    questionnaires = build_questions(report)
    expected = [r.ref for r in report.rules if r.section != "keep"]
    assert sorted({ref for q in questionnaires for ref in q.rules}) == sorted(expected)
    cleanup = {r.ref for r in report.rules if is_cleanup(r.finding)}
    for q in questionnaires:
        if q.group == FIREWALL_TEAM:
            assert set(q.rules) == cleanup
        else:
            assert not set(q.rules) & cleanup, q.name
        assert len(q.rules) == len(set(q.rules))
    people = [p for q in questionnaires if q.group != FIREWALL_TEAM for p in q.recipients]
    assert len(people) == len(set(people))
    # A rule with a certain owner is asked once, in its owner's first section.
    for rule in report.rules:
        owner = rule.finding.assessment.owner  # type: ignore[union-attr]
        if rule.ref in expected and rule.ref not in cleanup and owner:
            asking = [q for q in questionnaires if rule.ref in q.rules]
            assert [q.recipients for q in asking] == [[owner]]
            assert rule.ref in asking[0].owned
    rows = list(csv.DictReader(io.StringIO(answers_csv(report, questionnaires))))
    assert [row["rule"] for row in rows] == [r.ref for r in report.rules if r.ref in expected]
    for q in questionnaires:
        for ref in q.rules:
            assert f"Rule {ref} (" in q.text
        assert "[E" not in q.text
    # Worth a look: keep rules with LOW confidence or counters only, in the report only.
    look = [r.ref for r in report.rules if worth_a_look(r)]
    for rule in report.rules:
        a = rule.finding.assessment
        assert a is not None
        flagged = rule.section == "keep" and (a.confidence == "LOW" or counters_only(rule.finding))
        assert (rule.ref in look) == flagged
    # Sorted by risk, then configuration order; the JSON keeps all, the Markdown the top 20.
    ranked = report.worth_a_look
    assert sorted(e.ref for e in ranked) == sorted(look)
    ranks = [RISKS.index(e.risk) for e in ranked]
    assert ranks == sorted(ranks)
    for entry in ranked:
        assert RISKS[look_risk(report.rule(entry.ref))] == entry.risk
    section = text.split("## Worth a look", 1)[1].split("\n## ", 1)[0]
    shown = [line.split(" ")[1] for line in section.splitlines() if line.startswith("- R")]
    assert shown == [e.ref for e in ranked][:LOOK_SHOWN]
    for q in questionnaires:
        assert "If we do not hear back, the rule is kept." in q.text


def test_worth_a_look_ranked_by_risk(easy: Path) -> None:
    dataset = ingest(easy)
    findings = [r.finding for r in build(dataset).rules]
    keep = [f for f in findings if f.assessment and f.assessment.verdict == "keep"]
    logged = [f for f in keep if not counters_only(f)]
    counted = [f for f in keep if counters_only(f)]
    low, counters, internet, broad = logged[0], counted[0], logged[1], logged[2]
    for finding in (low, counters, internet, broad):
        finding.assessment.confidence = "LOW"  # type: ignore[union-attr]
        finding.policy.from_zone, finding.policy.to_zone = "trust", "servers"
        finding.policy.sources, finding.policy.applications = ["users-hq"], ["junos-ssh"]
        finding.policy.destinations = ["dns-01"]
    internet.policy.to_zone, internet.policy.destinations = "untrust", ["any"]
    broad.policy.applications = ["any"]
    report = build(dataset, findings)
    ref = {id(r.finding): r.ref for r in report.rules}
    order = [e.ref for e in report.worth_a_look]
    mine = [ref[id(f)] for f in (broad, internet, counters, low)]
    assert [r for r in order if r in mine] == mine
    risk = {e.ref: e.risk for e in report.worth_a_look}
    assert [risk[r] for r in mine] == list(RISKS)


def test_internet_facing_from_public_addresses(easy: Path) -> None:
    """Decision 0030: public addresses first, zone names only for unresolved sides."""
    dataset = ingest(easy)
    finding = collect_all(dataset)[0]
    policy = finding.policy
    policy.from_zone, policy.to_zone = "trust", "servers"
    policy.sources, policy.destinations = ["users-hq"], ["dns-01"]
    assert internet_facing(finding, dataset) == ""
    policy.destinations = ["ntp-pool"]
    assert internet_facing(finding, dataset) == "public address ntp-pool (198.51.100.123/32)"
    policy.to_zone, policy.destinations = "untrust", ["dns-01"]
    assert internet_facing(finding, dataset) == ""
    policy.destinations = ["any"]
    assert "zone untrust, named like the internet" in internet_facing(finding, dataset)
    policy.to_zone = "partners"
    assert internet_facing(finding, dataset) == ""


def test_public_address_classes() -> None:
    public = ["198.51.100.7/32", "8.8.8.8/32", "0.0.0.0/0", "2001:db8::/64", "2a00:1450::1/128"]
    private = ["10.1.2.0/24", "172.16.0.0/12", "192.168.1.1/32", "100.64.0.1/32", "fd00::1/128"]
    assert all(is_public(ipaddress.ip_network(n)) for n in public)
    assert not any(is_public(ipaddress.ip_network(n)) for n in private)


def test_easy_report(easy: Path) -> None:
    report = build(ingest(easy))
    check(report)
    text = markdown(report)
    order = [text.index(h) for h in ("## Summary", "## What palimp could not see")]
    order += [text.index(h) for h in ("## Removal candidates", "## Verify", "## Keep")]
    assert order == sorted(order)
    for topic in ("Policies without logging", "Log window", "History horizon"):
        assert f"**{topic}" in text
    for heading in ("## Firewall team cleanup list", "## Worth a look"):
        assert heading in text


def test_removal_candidate_without_not_live_item_is_refused(easy: Path) -> None:
    dataset = ingest(easy)
    report = build(dataset)
    findings = [r.finding for r in report.rules]
    target = next(f for f in findings if f.assessment and f.assessment.verdict == "keep")
    target.assessment.verdict = "removal_candidate"  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="not-live"):
        build(dataset, findings)


def test_report_and_questions_cli(easy: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["report", "-a", str(easy), "-o", str(tmp_path / "r")])
    assert result.exit_code == 0, result.output
    payload = json.loads((tmp_path / "r" / "report.json").read_text(encoding="utf-8"))
    assert payload["summary"]["total"] == len(payload["rules"])
    assert (tmp_path / "r" / "report.md").read_text(encoding="utf-8").startswith("# palimp")
    # The cleanup list is written next to the report when there is one.
    cleanup = tmp_path / "r" / "00-firewall-team-cleanup.txt"
    expected = cleanup_list(Report.model_validate(payload))
    assert cleanup.is_file() == (expected is not None)
    if expected is not None:
        assert cleanup.read_text(encoding="utf-8") == expected.text
    result = runner.invoke(app, ["questions", "-a", str(easy), "-o", str(tmp_path / "q")])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "q" / "answers.csv").is_file()


@pytest.mark.slow
@pytest.mark.parametrize("seed", range(5))
def test_medium_report(seed: int, tmp_path: Path) -> None:
    check(build(ingest(generate(seed, tmp_path) / "artifacts")))


@pytest.mark.slow
def test_medium_report_writes_cleanup_list(tmp_path: Path) -> None:
    artifacts = generate(0, tmp_path) / "artifacts"
    result = CliRunner().invoke(app, ["report", "-a", str(artifacts), "-o", str(tmp_path / "r")])
    assert result.exit_code == 0, result.output
    text = (tmp_path / "r" / "00-firewall-team-cleanup.txt").read_text(encoding="utf-8")
    assert "Hello firewall team" in text
    assert "If we do not hear back, the rule is kept." in text
    payload = json.loads((tmp_path / "r" / "report.json").read_text(encoding="utf-8"))
    look = (tmp_path / "r" / "report.md").read_text(encoding="utf-8").split("## Worth a look")[1]
    shown = [line for line in look.split("\n## ")[0].splitlines() if line.startswith("- R")]
    assert len(shown) == min(LOOK_SHOWN, len(payload["worth_a_look"]))
