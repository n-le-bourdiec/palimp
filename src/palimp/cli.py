"""Command line entry point."""

import json
from pathlib import Path

import typer

from palimp import __version__
from palimp.evidence import collect, collect_all
from palimp.ingest import ingest as ingest_directory
from palimp.models import Dataset, Finding, ParseStats, PolicyKey

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


def _load(source: Path) -> Dataset:
    """Read an artifact directory, or a JSON file written by `palimp ingest`."""
    if source.is_file() and source.suffix == ".json":
        return Dataset.model_validate_json(source.read_text(encoding="utf-8"))
    try:
        return ingest_directory(source)
    except FileNotFoundError as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(2) from error


def _stats_line(stats: ParseStats | None) -> str:
    if stats is None:
        return ""
    return (
        f"{stats.file}: {stats.total} lines, {stats.parsed} parsed, "
        f"{stats.ignored} ignored, {stats.unknown} unknown"
    )


@app.command()
def ingest(
    directory: Path = typer.Argument(..., help="Directory holding the artifacts."),
    out: Path = typer.Option(Path("palimp-ingest.json"), "--out", "-o", help="Output JSON file."),
) -> None:
    """Parse all artifacts of DIRECTORY and write a normalized JSON file."""
    dataset = _load(directory)
    out.write_text(dataset.model_dump_json(indent=2) + "\n", encoding="utf-8")
    all_stats = [
        dataset.config.stats,
        dataset.commit_stats,
        dataset.hit_count_stats,
        dataset.log_stats,
        dataset.ticket_stats,
    ]
    for stats in all_stats:
        if stats:
            typer.echo(_stats_line(stats))
    unknown = sum(s.unknown for s in dataset.rollback_stats)
    typer.echo(f"rollbacks: {len(dataset.rollback_stats)} files, {unknown} unknown lines")
    for stats in [s for s in all_stats + dataset.rollback_stats if s and s.unknown]:
        for sample in stats.unknown_samples[:3]:
            typer.echo(f"  unknown in {stats.file}: {sample[:120]}")
    for warning in dataset.warnings:
        typer.echo(f"warning: {warning}")
    typer.echo(f"{len(dataset.config.policies)} policies written to {out}")


def _render(finding: Finding, dataset: Dataset) -> str:
    policy = finding.policy
    state = "deactivated" if policy.deactivated else "active"
    logging = [
        o
        for o, on in (("session-init", policy.log_init), ("session-close", policy.log_close))
        if on
    ]
    lines = [
        f"Policy {finding.key}  ({state}, position {policy.position + 1})",
        f"  source:       {', '.join(policy.sources) or '-'}",
        f"  destination:  {', '.join(policy.destinations) or '-'}",
        f"  application:  {', '.join(policy.applications) or '-'}",
        f"  action:       {policy.action or '-'}"
        + (f", log {' and '.join(logging)}" if logging else ", no logging"),
        f"  description:  {policy.description or '-'}",
    ]
    commit = next((c for c in dataset.commits if c.index == finding.created_in_commit), None)
    if commit:
        lines.append(
            f"  created in:   commit {commit.index} "
            f"({commit.timestamp:%Y-%m-%d %H:%M:%S} {commit.time_zone} by {commit.user})"
        )
    else:
        lines.append("  created in:   before the retained history")
    lines.append("Evidence:")
    if not finding.evidence:
        lines.append("  none found")
    for item in finding.evidence:
        lines.append(f"  [{item.id}] {item.tier} {item.artifact} :: {item.locator}")
        lines.append(f"       {item.claim}")
    return "\n".join(lines)


@app.command()
def explain(
    policy: str = typer.Argument(None, help="Policy as FROM/TO/NAME (omit with --all)."),
    source: Path = typer.Option(
        Path("."), "--artifacts", "-a", help="Artifact directory or `palimp ingest` JSON."
    ),
    no_llm: bool = typer.Option(False, "--no-llm", help="Facts and evidence only, no prose."),
    as_json: bool = typer.Option(False, "--json", help="Print JSON instead of text."),
    all_policies: bool = typer.Option(False, "--all", help="Explain every policy."),
) -> None:
    """Show a policy and the evidence found for it."""
    if not no_llm:
        typer.echo("note: LLM prose is not implemented yet; showing --no-llm output", err=True)
    dataset = _load(source)
    if all_policies:
        findings = collect_all(dataset)
    else:
        if not policy:
            typer.echo("error: give FROM/TO/NAME or --all", err=True)
            raise typer.Exit(2)
        try:
            findings = [collect(dataset, PolicyKey.parse(policy))]
        except (KeyError, ValueError) as error:
            typer.echo(f"error: {error}", err=True)
            raise typer.Exit(1) from error
    if as_json:
        payload = [f.model_dump(mode="json") for f in findings]
        typer.echo(json.dumps(payload if all_policies else payload[0], indent=2))
    else:
        typer.echo("\n\n".join(_render(f, dataset) for f in findings))
