"""`palimp demo`: a bundled synthetic Medium scenario and its report (session 35).

Decisions 0003 and 0032 listed `demo` as a v1 command; it did not exist until
session 35 (see their amendments).
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from palimp.cli import app

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[1]


def test_demo_writes_report(tmp_path: Path) -> None:
    out = tmp_path / "demo"
    result = runner.invoke(app, ["demo", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert "Synthetic scenario" in result.stdout
    assert (out / "artifacts" / "config.set").is_file()
    assert (out / "artifacts" / "logs" / "rt_flow.log").is_file()
    assert not (out / "ground_truth.json").exists()
    assert not list(out.rglob("ground_truth.json"))
    report = (out / "report.md").read_text(encoding="utf-8")
    assert report.startswith("# palimp report")
    assert (out / "report.json").is_file()
    assert "128 policies" in result.stdout


def test_demo_default_directory_is_new() -> None:
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0, result.output
    line = next(x for x in result.stdout.splitlines() if x.startswith("artifacts copied to "))
    out = Path(line.removeprefix("artifacts copied to ")).parent
    try:
        assert out.name.startswith("palimp-demo-")
        assert (out / "report.md").is_file()
    finally:
        shutil.rmtree(out, ignore_errors=True)


def test_demo_refuses_a_directory_in_use(tmp_path: Path) -> None:
    (tmp_path / "keep.txt").write_text("mine", encoding="utf-8")
    result = runner.invoke(app, ["demo", "--out", str(tmp_path)])
    assert result.exit_code == 2
    assert (tmp_path / "keep.txt").read_text(encoding="utf-8") == "mine"


@pytest.mark.slow
def test_demo_data_matches_the_simulator() -> None:
    """The packaged scenario is what the simulator writes today (rebuild with
    `uv run python eval/demo_data.py` after a simulator change that moves Medium seed 14)."""
    done = subprocess.run(
        [sys.executable, str(ROOT / "eval" / "demo_data.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stdout + done.stderr
