"""Config-only input (session 35): every sentence matches the artifacts actually provided.

A real inherited firewall often comes with its configuration alone. Found in a manual
test: the report named hitcount.txt when no hit counts were given, `explain` said a
rule was created "before the retained history" when no history was given, and the
questionnaires were named after guessed applications. Checked on the configuration of
Easy seed 0, copied alone.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from palimp.cli import app

runner = CliRunner()


@pytest.fixture(scope="module")
def easy(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("easy")
    command = [sys.executable, "-m", "palimp_sim.cli", "generate", "--level", "easy"]
    subprocess.run(command + ["--seed", "0", "--out", str(out)], check=True, capture_output=True)
    return out / "scenario-easy-000000" / "artifacts"


@pytest.fixture
def config_only(easy: Path, tmp_path: Path) -> Path:
    directory = tmp_path / "artifacts"
    directory.mkdir()
    shutil.copy(easy / "config.set", directory / "config.set")
    return directory


def _report(config_only: Path, tmp_path: Path) -> str:
    out = tmp_path / "report"
    result = runner.invoke(app, ["report", "-a", str(config_only), "-o", str(out)])
    assert result.exit_code == 0, result.output
    return (out / "report.md").read_text(encoding="utf-8")


def test_report_names_hit_counts_only_as_missing(config_only: Path, tmp_path: Path) -> None:
    text = _report(config_only, tmp_path)
    for line in text.splitlines():
        if "hitcount.txt" in line or "hit counter" in line:
            assert "missing" in line or "no hit counts were provided" in line, line
    assert "Inferred counter clears" not in text
    assert "only the hit counters can" not in text
    assert "No session log and no hit counts were provided, so no rule shows traffic" in text


def test_report_lists_no_text_for_absent_removal_candidates(
    config_only: Path, tmp_path: Path
) -> None:
    text = _report(config_only, tmp_path)
    assert "## Removal candidates (0)" in text
    assert "Each rule below has at least one positive sign" not in text


def test_initials_without_ticket_export(config_only: Path, tmp_path: Path) -> None:
    text = _report(config_only, tmp_path)
    assert "initials LN" in text
    assert "no ticket requester has them" not in text
    assert "no ticket export was provided to match them" in text


def test_explain_says_no_history_was_given(config_only: Path) -> None:
    result = runner.invoke(
        app, ["explain", "trust/servers/users-to-hr-web", "-a", str(config_only)]
    )
    assert result.exit_code == 0, result.output
    assert "before the retained history" not in result.stdout
    assert "created in:   unknown, no commit history was provided" in result.stdout
    # The policy logs: the question must not say it has no logging.
    assert "log session-init and session-close" in result.stdout
    question = next(line for line in result.stdout.splitlines() if "question:" in line)
    assert "no logging" not in question and "does not log" not in question
    assert "no hit counts were provided" in question
    assert "no session log was provided" in question


def test_explain_question_names_missing_logging(config_only: Path) -> None:
    result = runner.invoke(
        app, ["explain", "trust/servers/users-to-wms-app", "-a", str(config_only)]
    )
    assert result.exit_code == 0, result.output
    assert "no logging" in result.stdout
    question = next(line for line in result.stdout.splitlines() if "question:" in line)
    assert "the policy does not log" in question


def test_questionnaires_grouped_by_zone_pair(config_only: Path, tmp_path: Path) -> None:
    out = tmp_path / "questions"
    result = runner.invoke(app, ["questions", "-a", str(config_only), "-o", str(out)])
    assert result.exit_code == 0, result.output
    letters = sorted(out.glob("[0-9]*.txt"))
    assert letters
    for letter in letters:
        assert "no-name-found" not in letter.name
        match = re.fullmatch(r"\d\d-no-owner-name-([a-z0-9]+)-to-([a-z0-9]+)\.txt", letter.name)
        assert match, letter.name
        text = letter.read_text(encoding="utf-8")
        assert f"all from {match[1]} to {match[2]}" in text
        assert "The firewall does not record" not in text
        # Every rule of the letter crosses that zone pair, and each says who may know.
        allows = [line for line in text.splitlines() if "What it allows:" in line]
        assert allows
        for line in allows:
            zones = re.findall(r"in zone (\S+?),", line)
            assert zones[:1] == [match[1]] and zones[-1:] == [match[2]], line
        assert text.count("Who may know:") == len(allows)
