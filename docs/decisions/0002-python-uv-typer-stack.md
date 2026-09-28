# 0002 Stack: Python, uv, Typer

- Status: Accepted
- Date: 2026-09-28

## Context

palimp is an offline CLI that parses text artifacts (Junos configs, logs, CSV
exports), scores evidence and optionally calls a local LLM. Its users are network
and security engineers who need a tool that is easy to install and to audit.

## Decision

- Python 3.12 or later.
- uv for dependency management, locking and running tools.
- Typer for the CLI, pydantic for data models.
- pytest for tests, ruff for lint and formatting, GitHub Actions for CI.
- Source layout: `src/palimp`, with the simulator in a separate top level
  `simulator` package.

## Alternatives considered

- Go or Rust: single static binary, but slower to iterate on parsing and
  evaluation code, and a weaker ecosystem for local LLM tooling and data work.
- pip plus venv, or Poetry: uv is faster and handles Python versions and
  lock files in one tool.
- argparse or Click directly: Typer gives typed commands and help text with
  less code, and is built on Click.

## Consequences

- Users need Python 3.12 or later, or install through `uv tool install`.
- `uv.lock` is committed and CI installs with `uv sync --locked`.

## Challenged by Nathan

No.
