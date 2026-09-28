# Handoff

## Last session: 1 (2026-09-28), bootstrap

### Done

- uv project `palimp` (Python 3.12+, hatchling build, `uv.lock` committed).
- Typer CLI in `src/palimp/cli.py`, exposing only `palimp --version`.
- Empty `simulator` package at the repository root, separate from `src/palimp`.
- ruff (lint + format) and pytest configured in `pyproject.toml`; one smoke test
  in `tests/test_cli.py`.
- GitHub Actions CI (`.github/workflows/ci.yml`): `uv sync --locked`, ruff check,
  ruff format check, pytest.
- Apache 2.0 `LICENSE`, minimal `README.md`.
- Decisions 0001 to 0005 in `docs/decisions/`.
- `metrics/sessions.csv` with header and the session 1 row.
- `metrics/session_tokens.py`: sums token usage of a session from the local
  Claude Code transcript (see "Measuring tokens" below).
- The prompt file was named `CLAUDE (6).md`; it was renamed to `CLAUDE.md`
  (content unchanged).

### Next

- Session 2 mission to be set by the project lead. Likely candidates: pydantic
  models for policies and evidence, the Junos "set" parser with fixtures, or the
  simulator skeleton.

### Open questions

- Decision 0001: which alternative names were considered, and what was the
  challenge about? Not known at the time of writing; the "Alternatives
  considered" section says so.
- Alternatives listed in 0002 to 0005 were written by Claude from the principles
  in `CLAUDE.md`, not from a record of an actual discussion. Please correct them
  if they differ from what was really weighed.
- `tokens_cache` is a single column but there are two cache counters (read and
  write, priced differently). Session 1 puts cache reads in `tokens_cache` and
  cache writes in `notes`. Consider splitting the column.

### Known issues

- Git identity for this repository is set locally (`n-le-bourdiec`,
  repository config only) because no global git identity exists on this machine.
- CI has not been observed green on GitHub yet at the time of writing; check the
  Actions tab after the first push.

## Measuring tokens

Claude Code stores each session as JSONL in
`~/.claude/projects/<project-slug>/<session-id>.jsonl` (here the slug is
`d--projet-code-Palimp`). Every assistant entry has the API `usage` block
(input, output, cache creation, cache read). Run, as the very last step:

    uv run python metrics/session_tokens.py <session-id>

The session id is the transcript file name (the newest file in that folder).
The numbers exclude the few calls made after the script runs. Cost is left
`n/a`: no local source gives it for this model, and it is not estimated.
