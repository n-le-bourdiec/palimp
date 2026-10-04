# 0009 The simulator is a separate uv workspace member

- Status: Accepted
- Date: 2026-10-04

## Context

Decision 0005 requires that the simulator and the analyzer never share code.
Until now the simulator was a bare `simulator` package at the repository root,
inside the palimp project. Nothing stopped it from being picked up by tooling
as part of palimp, and it could not have dependencies of its own.

## Decision

- The simulator is a uv workspace member in `simulator/`, with its own
  `pyproject.toml`: distribution `palimp-sim`, import package `palimp_sim`,
  command `palimp-sim`.
- It is never shipped in the palimp package: the palimp wheel contains only
  `src/palimp`.
- Import bans with ruff `TID251` in both directions: `src/palimp` and `tests`
  cannot import `palimp_sim` (root `pyproject.toml`), and `simulator/` cannot
  import `palimp` (`simulator/pyproject.toml`). A test also scans imports with
  `ast`, so the rule holds even if the ruff config changes.
- The workspace shares one lock file and one virtual environment. CI installs
  every member with `uv sync --locked --all-packages` and runs both test suites.

## Alternatives considered

- Keep a bare package in the palimp project: no own dependencies, no physical
  boundary.
- A separate repository: strongest separation, but two CI setups and harder
  coordination of the ground truth schema and the evaluation harness.

## Consequences

- The simulator can depend on libraries palimp does not need (for example
  `jsonschema`).
- One shared virtual environment means both packages are importable at test
  time; the bans and the import test are what keep them apart.
- Supersedes the "can later become its own workspace member" note in section 10
  of `docs/simulator-spec.md` (that section is updated).

## Challenged by Nathan

No. Proposed by the project lead in session 3.
