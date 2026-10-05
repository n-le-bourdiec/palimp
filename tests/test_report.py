"""`palimp report` and `palimp questions`: citations, coverage, removal candidates.

Checked on the Easy scenario in the repository (fast) and on Medium dev seeds
0 to 4 (slow, black box: the simulator writes a scenario, palimp reads only
its artifacts).
"""

import csv
import io
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from palimp.assess import NOT_LIVE_KINDS
from palimp.cli import app
from palimp.ingest import ingest
from palimp.questions import answers_csv
from palimp.questions import build as build_questions
from palimp.report import Report, build, cited_ids, markdown

EASY = Path(__file__).parent.parent / "scenarios" / "scenario-easy-000000" / "artifacts"
RULE_HEADING = re.compile(r"^#{3,4} (R\d+) `([^`]+)`")
TABLE_ROW = re.compile(r"^\| (R\d+) \| `([^`]+)` \|")


def generate(seed: int, out: Path) -> Path:
    command = [sys.executable, "-m", "palimp_sim.cli", "generate", "--level", "medium"]
    subprocess.run(
        command + ["--seed", str(seed), "--out", str(out)], check=True, capture_output=True
    )
    return out / f"scenario-medium-{seed:06d}"


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
    # Questionnaires ask about every rule to verify or remove, exactly once, never keep.
    questionnaires = build_questions(report)
    asked = [ref for q in questionnaires for ref in q.rules]
    expected = [r.ref for r in report.rules if r.section != "keep"]
    assert sorted(asked) == sorted(expected)
    rows = list(csv.DictReader(io.StringIO(answers_csv(report, questionnaires))))
    assert sorted(row["rule"] for row in rows) == sorted(expected)
    for q in questionnaires:
        for ref in q.rules:
            assert f"Rule {ref} (" in q.text
        assert "[E" not in q.text


def test_easy_report() -> None:
    report = build(ingest(EASY))
    check(report)
    text = markdown(report)
    order = [text.index(h) for h in ("## Summary", "## What palimp could not see")]
    order += [text.index(h) for h in ("## Removal candidates", "## Verify", "## Keep")]
    assert order == sorted(order)
    for topic in ("Policies without logging", "Log window", "History horizon"):
        assert f"**{topic}" in text


def test_removal_candidate_without_not_live_item_is_refused() -> None:
    dataset = ingest(EASY)
    report = build(dataset)
    findings = [r.finding for r in report.rules]
    target = next(f for f in findings if f.assessment and f.assessment.verdict == "keep")
    target.assessment.verdict = "removal_candidate"  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="not-live"):
        build(dataset, findings)


def test_report_and_questions_cli(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["report", "-a", str(EASY), "-o", str(tmp_path / "r")])
    assert result.exit_code == 0, result.output
    payload = json.loads((tmp_path / "r" / "report.json").read_text(encoding="utf-8"))
    assert payload["summary"]["total"] == len(payload["rules"])
    assert (tmp_path / "r" / "report.md").read_text(encoding="utf-8").startswith("# palimp")
    result = runner.invoke(app, ["questions", "-a", str(EASY), "-o", str(tmp_path / "q")])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "q" / "answers.csv").is_file()


@pytest.mark.slow
@pytest.mark.parametrize("seed", range(5))
def test_medium_report(seed: int, tmp_path: Path) -> None:
    check(build(ingest(generate(seed, tmp_path) / "artifacts")))
