from typer.testing import CliRunner

from palimp import __version__
from palimp.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"palimp {__version__}"
