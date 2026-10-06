"""LLM writer (decision 0027) with the fake backend: validation, fallback, CLI.

No real model: the fake backend returns the text each test wants to check.
Black box on Easy seed 0: the simulator writes a scenario, palimp reads only
its artifacts.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from palimp.cli import app
from palimp.ingest import ingest
from palimp.llm import FakeBackend, Request
from palimp.models import Dataset
from palimp.prose import Names, add_prose, check, evidence_text, write_rule
from palimp.report import CITE, LLMRun, Report, RuleEntry, build, markdown


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("easy")
    command = [sys.executable, "-m", "palimp_sim.cli", "generate", "--level", "easy"]
    subprocess.run(command + ["--seed", "0", "--out", str(out)], check=True, capture_output=True)
    return out / "scenario-easy-000000" / "artifacts"


@pytest.fixture(scope="module")
def dataset(artifacts: Path) -> Dataset:
    return ingest(artifacts)


@pytest.fixture()
def report(dataset: Dataset) -> Report:
    return build(dataset)


@pytest.fixture()
def names(dataset: Dataset, report: Report) -> Names:
    return Names.of(dataset, [r.finding for r in report.rules])


def with_kinds(report: Report, *kinds: str, verdict: str | None = None) -> RuleEntry:
    for entry in report.rules:
        have = {e.kind for e in entry.finding.evidence}
        a = entry.finding.assessment
        assert a is not None
        if set(kinds) <= have and (verdict is None or a.verdict == verdict):
            return entry
    raise LookupError(kinds)


def item(entry: RuleEntry, kind: str):  # type: ignore[no-untyped-def]
    return next(e for e in entry.finding.evidence if e.kind == kind)


def judge(entry: RuleEntry, sentence: str, names: Names) -> str | None:
    a = entry.finding.assessment
    assert a is not None
    return check(sentence, evidence_text(entry.finding), names, a.verdict, a.confidence)


def address_sentence(entry: RuleEntry) -> tuple[str, str, str]:
    """A true sentence from the address objects item: (sentence, object name, address)."""
    objects = item(entry, "address_objects")
    name, value = objects.claim.split(";")[0].split(" = ")
    return f"The rule reaches {name.strip()} at {value.strip()} [{objects.id}].", name, value


def test_correct_sentence_passes(report: Report, names: Names) -> None:
    entry = with_kinds(report, "address_objects")
    sentence, _, _ = address_sentence(entry)
    assert judge(entry, sentence, names) is None
    a = entry.finding.assessment
    assert a is not None
    stated = f"The verdict is {a.verdict.replace('_', ' ')} [{a.verdict_evidence[0]}]."
    assert judge(entry, stated, names) is None


def test_sentence_without_citation_is_rejected(report: Report, names: Names) -> None:
    entry = with_kinds(report, "address_objects")
    sentence, _, _ = address_sentence(entry)
    assert judge(entry, sentence.rsplit(" [", 1)[0] + ".", names) == "no evidence ID cited"


def test_wrong_evidence_id_is_rejected(report: Report, names: Names) -> None:
    entry = with_kinds(report, "address_objects")
    sentence, _, _ = address_sentence(entry)
    wrong = f"E{len(entry.finding.evidence) + 1}"
    bad = sentence.rsplit(" [", 1)[0] + f" [{wrong}]."
    assert judge(entry, bad, names) == f"unknown evidence ID {wrong}"


def test_fact_from_an_uncited_item_is_rejected(report: Report, names: Names) -> None:
    entry = with_kinds(report, "address_objects", "services")
    sentence, _, _ = address_sentence(entry)
    other = item(entry, "services").id
    bad = sentence.rsplit(" [", 1)[0] + f" [{other}]."
    reason = judge(entry, bad, names)
    assert reason is not None and "not in the cited evidence" in reason


def test_invented_ip_is_rejected(report: Report, names: Names) -> None:
    entry = with_kinds(report, "address_objects")
    sentence, _, value = address_sentence(entry)
    reason = judge(entry, sentence.replace(value.strip(), "192.0.2.77/32"), names)
    assert reason == "IP address 192.0.2.77/32 not in the cited evidence"


def test_invented_person_is_rejected(report: Report, names: Names) -> None:
    entry = with_kinds(report, "address_objects")
    objects = item(entry, "address_objects").id
    reason = judge(entry, f"Martha Kowalski asked for this rule [{objects}].", names)
    assert reason == "name Martha Kowalski not in the cited evidence"


def test_real_person_not_in_cited_evidence_is_rejected(
    report: Report, dataset: Dataset, names: Names
) -> None:
    entry = with_kinds(report, "address_objects")
    objects = item(entry, "address_objects").id
    person = next(t.requester for t in dataset.tickets.values() if t.requester)
    reason = judge(entry, f"The rule was requested by {person} [{objects}].", names)
    assert reason == f"name {person.lower()} not in the cited evidence"


def test_invented_date_is_rejected(report: Report, names: Names) -> None:
    entry = with_kinds(report, "address_objects")
    objects = item(entry, "address_objects").id
    for sentence, reason in (
        (f"It was opened on 2019-07-14 [{objects}].", "date 2019-07-14"),
        (f"It was opened in March [{objects}].", "month March"),
        (f"It carried 4242 sessions [{objects}].", "number 4242"),
    ):
        assert judge(entry, sentence, names) == f"{reason} not in the cited evidence"


def test_invented_application_is_rejected(report: Report, names: Names) -> None:
    entry = with_kinds(report, "address_objects")
    objects = item(entry, "address_objects").id
    reason = judge(entry, f"It serves the zorblax application [{objects}].", names)
    assert reason == "application zorblax not in the cited evidence"


def test_changed_verdict_is_rejected(report: Report, names: Names) -> None:
    entry = with_kinds(report, "address_objects", verdict="keep")
    objects = item(entry, "address_objects").id
    reason = judge(entry, f"This rule can be removed [{objects}].", names)
    assert reason is not None and reason.startswith("states verdict removal_candidate")
    a = entry.finding.assessment
    assert a is not None
    other = "LOW" if a.confidence != "LOW" else "HIGH"
    reason = judge(entry, f"palimp has {other.lower()} confidence in it [{objects}].", names)
    assert reason == f"states {other} confidence, the confidence is {a.confidence}"


def test_rejected_sentences_are_replaced_counted_and_logged(
    report: Report, names: Names, caplog: pytest.LogCaptureFixture
) -> None:
    entry = with_kinds(report, "address_objects")
    good, _, _ = address_sentence(entry)
    objects = item(entry, "address_objects").id
    bad = [f"Martha Kowalski owns it [{objects}].", "It is old.", f"It moved in 2019 [{objects}]."]
    backend = FakeBackend(lambda request: " ".join([good, *bad]))
    run = LLMRun(backend="fake")
    with caplog.at_level(logging.WARNING, logger="palimp.prose"):
        prose = write_rule(entry, backend, names, run)
    assert prose.startswith(good)
    for sentence in bad:
        assert sentence not in prose
    a = entry.finding.assessment
    assert a is not None
    assert f"Verdict {a.verdict} ({a.verdict_rule}" in prose  # the deterministic text
    assert (run.sentences_kept, run.sentences_rejected, run.fallbacks) == (1, 3, 1)
    assert [r.sentence for r in run.rejections] == bad
    assert sum("LLM sentence rejected" in r.message for r in caplog.records) == 3
    # The LLM saw only the facts of this rule.
    request = backend.requests[0]
    assert request.facts["verdict"] == a.verdict
    assert [e["id"] for e in request.facts["evidence"]] == [e.id for e in entry.finding.evidence]


def test_backend_failure_gives_the_deterministic_text(report: Report, names: Names) -> None:
    entry = with_kinds(report, "address_objects")

    def fail(request: Request) -> str:
        raise ConnectionError("refused")

    run = LLMRun(backend="fake")
    prose = write_rule(entry, FakeBackend(fail), names, run)
    assert prose.startswith(("Probably for", "Purpose unknown"))
    assert run.rejections[0].reason == "backend: refused"


def test_prose_never_changes_a_judgment(report: Report, dataset: Dataset) -> None:
    before = [r.finding.model_dump_json() for r in report.rules]
    questions = [(r.section, r.group, r.owner, r.question) for r in report.rules]
    run = add_prose(report, dataset, FakeBackend())
    assert [r.finding.model_dump_json() for r in report.rules] == before
    assert [(r.section, r.group, r.owner, r.question) for r in report.rules] == questions
    assert all(r.prose for r in report.rules)
    assert report.executive_summary
    assert run.sentences_kept > 0
    # Every sentence that survived cites an existing item of its rule.
    for entry in report.rules:
        ids = {e.id for e in entry.finding.evidence}
        assert set(CITE.findall(entry.prose)) <= ids, entry.ref
    facts = {f.id for f in report.summary_facts}
    assert set(CITE.findall(report.executive_summary)) <= facts
    text = markdown(report)
    assert "## Executive summary" in text and "*In words:*" in text


def test_cli_defaults_to_no_llm(artifacts: Path, report: Report, tmp_path: Path) -> None:
    key = report.rules[0].key
    runner = CliRunner()
    result = runner.invoke(app, ["explain", key, "-a", str(artifacts)])
    assert result.exit_code == 0, result.output
    assert "In words:" not in result.output
    result = runner.invoke(
        app, ["explain", key, "-a", str(artifacts), "--llm", "--llm-backend", "fake"]
    )
    assert result.exit_code == 0, result.output
    assert "In words:" in result.output
    result = runner.invoke(
        app, ["explain", key, "-a", str(artifacts), "--llm", "--llm-url", "http://10.1.1.1"]
    )
    assert result.exit_code == 2
    out = tmp_path / "r"
    result = runner.invoke(app, ["report", "-a", str(artifacts), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert "## Executive summary" not in (out / "report.md").read_text(encoding="utf-8")
    assert not (out / "llm-rejections.json").exists()
    result = runner.invoke(
        app, ["report", "-a", str(artifacts), "-o", str(out), "--llm", "--llm-backend", "fake"]
    )
    assert result.exit_code == 0, result.output
    assert "## Executive summary" in (out / "report.md").read_text(encoding="utf-8")
    run = json.loads((out / "llm-rejections.json").read_text(encoding="utf-8"))
    assert run["backend"] == "fake"


def test_modal_may_and_own_policy_name_are_not_rejected(report: Report, names: Names) -> None:
    entry = with_kinds(report, "address_objects")
    objects = item(entry, "address_objects").id
    name = entry.finding.policy.name
    assert judge(entry, f"Policy {name} may serve this flow [{objects}].", names) is None
    reason = judge(entry, f"It was opened in May [{objects}].", names)
    assert reason == "month May not in the cited evidence"
