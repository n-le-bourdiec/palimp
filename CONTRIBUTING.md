# Contributing to palimp

Thank you for your interest. palimp is a release candidate frozen until its
first release: only bug fixes are accepted for now.

## Reporting a bug

Use the bug report template. Never attach real artifacts: make a copy with
`palimp anonymize --strip-text` and read it for leftover words first (the
template explains why).

## Development

    uv sync --all-packages          # palimp, the simulator and dev tools
    uv run pytest                   # fast tests (add --runslow for the long ones)
    uv run ruff check . && uv run ruff format --check .

Python 3.12+, Typer, pydantic, pytest, ruff; CI must stay green.

## Rules that keep palimp what it is

- Zero network egress: no telemetry, no update check, no remote model.
- Deterministic first: parsing, evidence and confidence are plain, tested code.
  The optional LLM only writes prose from established facts, and every
  sentence cites an evidence ID. `--no-llm` must stay fully functional.
- Read-only: palimp never connects to a device and never writes commands
  meant to be pushed.
- A change that moves a verdict toward `removal_candidate` needs a decision
  record and the project lead's approval.
- The analyzer (`src/palimp`) and the simulator (`simulator/`) share no code.
  A change to analyzer behavior is never tuned on the held-out scenarios.
- Significant decisions get a file in `docs/decisions/` (context, decision,
  alternatives, consequences). A recorded decision is never contradicted
  silently: a new file supersedes it.
- American English, no em or en dashes, small focused commits, each one
  passing the tests on its own.

## License

By contributing, you agree that your contributions are licensed under the
Apache License 2.0.
