"""Command line entry point."""

import json
from pathlib import Path

import typer

from palimp import __version__
from palimp.evidence import collect, collect_all
from palimp.ingest import ingest as ingest_directory
from palimp.models import Dataset, Finding, ParseStats, PolicyKey
from palimp.questions import answers_csv
from palimp.questions import build as build_questions
from palimp.report import build as build_report
from palimp.report import json_report, markdown

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


LOG_YEAR_HELP = (
    "Year of the first log line whose timestamp has no year (standard syslog format). "
    "By default it is inferred from the latest commit date, with a warning."
)


def _load(source: Path, log_year: int | None = None) -> Dataset:
    """Read an artifact directory, or a JSON file written by `palimp ingest`."""
    if source.is_file() and source.suffix == ".json":
        return Dataset.model_validate_json(source.read_text(encoding="utf-8"))
    try:
        return ingest_directory(source, log_year=log_year)
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
    log_year: int = typer.Option(None, "--log-year", help=LOG_YEAR_HELP),
) -> None:
    """Parse all artifacts of DIRECTORY and write a normalized JSON file."""
    dataset = _load(directory, log_year)
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


def _cite(ids: list[str]) -> str:
    return " ".join(f"[{i}]" for i in ids)


def _render(finding: Finding, dataset: Dataset, notes: dict[str, int] | None = None) -> str:
    """Text view of one finding. With `notes`, blind T2 items point to a global note."""
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
        if notes is not None and item.signal == "blind":
            note = notes.setdefault(item.claim, len(notes) + 1)
            lines.append(
                f"  [{item.id}] {item.tier} {item.artifact} :: no traffic visible, see note N{note}"
            )
            continue
        lines.append(f"  [{item.id}] {item.tier} {item.artifact} :: {item.locator}")
        lines.append(f"       {item.claim}")
    if assessment := finding.assessment:
        lines.append("Assessment:")
        lines.append(
            f"  verdict:      {assessment.verdict} ({assessment.verdict_rule}: "
            f"{assessment.verdict_reason}) {_cite(assessment.verdict_evidence)}".rstrip()
        )
        apps = assessment.intent_apps
        named = f"; intent names {', '.join(apps)}" if apps else ""
        lines.append(
            f"  confidence:   {assessment.confidence} ({assessment.confidence_rule}: "
            f"{assessment.confidence_reason}{named}) "
            f"{_cite(assessment.confidence_evidence)}".rstrip()
        )
        for conflict in assessment.conflicts:
            lines.append(f"  conflict:     {conflict.text} {_cite(conflict.evidence)}")
        if assessment.question:
            lines.append(f"  question:     {assessment.question}")
        if assessment.ask:
            lines.append(f"  ask:          {assessment.ask}")
    return "\n".join(lines)


def _notes(notes: dict[str, int], findings: list[Finding]) -> str:
    """One line per distinct blind claim, with how many items it stands for."""
    counts: dict[str, int] = {}
    for finding in findings:
        for item in finding.evidence:
            if item.signal == "blind":
                counts[item.claim] = counts.get(item.claim, 0) + 1
    lines = ["Notes (no traffic visible; the JSON output keeps every item):"]
    for claim, number in notes.items():
        lines.append(f"  N{number} ({counts[claim]} items): {claim}")
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
    log_year: int = typer.Option(None, "--log-year", help=LOG_YEAR_HELP),
) -> None:
    """Show a policy and the evidence found for it."""
    if not no_llm:
        typer.echo("note: LLM prose is not implemented yet; showing --no-llm output", err=True)
    dataset = _load(source, log_year)
    if dataset.log_window.year_source in ("inferred", "none"):
        typer.echo(f"warning: {dataset.log_window.year_note}", err=True)
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
        notes: dict[str, int] | None = {} if all_policies else None
        typer.echo("\n\n".join(_render(f, dataset, notes) for f in findings))
        if notes:
            typer.echo("\n" + _notes(notes, findings))


def _findings(source: Path, log_year: int | None) -> tuple[Dataset, list[Finding]]:
    dataset = _load(source, log_year)
    if dataset.log_window.year_source in ("inferred", "none"):
        typer.echo(f"warning: {dataset.log_window.year_note}", err=True)
    return dataset, collect_all(dataset)


@app.command()
def report(
    source: Path = typer.Option(
        Path("."), "--artifacts", "-a", help="Artifact directory or `palimp ingest` JSON."
    ),
    out: Path = typer.Option(
        Path("palimp-report"), "--out", "-o", help="Output directory (report.md, report.json)."
    ),
    log_year: int = typer.Option(None, "--log-year", help=LOG_YEAR_HELP),
) -> None:
    """Write a Markdown and a JSON report of every policy."""
    dataset, findings = _findings(source, log_year)
    built = build_report(dataset, findings)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(markdown(built), encoding="utf-8")
    (out / "report.json").write_text(json_report(built), encoding="utf-8")
    s = built.summary
    typer.echo(
        f"{s.total} policies: {s.removal_candidate} removal_candidate, {s.verify} verify, "
        f"{s.keep} keep; written to {out / 'report.md'} and {out / 'report.json'}"
    )


@app.command()
def questions(
    source: Path = typer.Option(
        Path("."), "--artifacts", "-a", help="Artifact directory or `palimp ingest` JSON."
    ),
    out: Path = typer.Option(
        Path("palimp-questions"),
        "--out",
        "-o",
        help="Output directory (one questionnaire per owner, answers.csv).",
    ),
    log_year: int = typer.Option(None, "--log-year", help=LOG_YEAR_HELP),
) -> None:
    """Write one questionnaire per owner and a CSV to track the answers."""
    dataset, findings = _findings(source, log_year)
    built = build_report(dataset, findings)
    found = build_questions(built)
    out.mkdir(parents=True, exist_ok=True)
    for q in found:
        (out / f"{q.name}.txt").write_text(q.text, encoding="utf-8")
    (out / "answers.csv").write_text(answers_csv(built, found), encoding="utf-8")
    rules = sum(len(q.rules) for q in found)
    typer.echo(f"{len(found)} questionnaires covering {rules} rules written to {out}")
