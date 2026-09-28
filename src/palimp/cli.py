"""Command line entry point."""

import typer

from palimp import __version__

app = typer.Typer(
    help="Reconstruct the lost intent behind inherited firewall rules.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"palimp {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Reconstruct the lost intent behind inherited firewall rules."""
