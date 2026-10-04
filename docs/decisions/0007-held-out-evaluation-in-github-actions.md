# 0007 Held-out evaluation runs only in GitHub Actions

- Status: Accepted
- Date: 2026-10-04

## Context

Decision 0005 splits simulator scenarios into a dev set and a held-out test set.
The held-out scenarios are derived from a secret salt. The first version of the
simulator spec kept that salt in an environment variable on the evaluation
machine. But the coding agent has full access to the local machine (files,
environment, shell history), so a secret stored locally is not secret from the
agent that tunes the analyzer.

## Decision

- The held-out salt is a GitHub repository secret named `HOLDOUT_SALT`. It is
  never stored on the development machine, in the repository, or in any
  artifact.
- Held-out evaluation runs only in a GitHub Actions workflow with a
  `workflow_dispatch` trigger, started by the project lead.
- The workflow generates the held-out scenarios, runs palimp on them, and prints
  aggregate metrics only (per difficulty level and per trap). No per-rule
  output, no scenario files, no ground truth are uploaded as artifacts or logs.
- The workflow is written once the simulator exists. Until then, only the dev
  set exists.

## Alternatives considered

- Salt in a local environment variable (first spec draft): readable by the
  agent, so it does not protect the held-out set.
- Salt on a separate machine owned by the project lead: protects the secret, but
  needs manual runs and a second environment to maintain.
- A frozen, encrypted set of held-out scenarios in the repository: the
  decryption key would have the same problem as the salt.

## Consequences

- The agent cannot regenerate held-out scenarios, by construction.
- Held-out runs cost GitHub Actions minutes and are visible in the Actions
  history, which also makes repeated peeking visible.
- Workflow logs must be checked to never print scenario content. Repository
  secrets are masked in logs, but derived values (seeds) are not, so the
  workflow must not print seeds.
- Supersedes the held-out mechanism in section 8.2 of the first draft of
  `docs/simulator-spec.md` (that section is updated).

## Challenged by Nathan

Yes. Nathan challenged the location of the held-out secret (local machine).
Outcome: decision changed, the secret moves to GitHub Actions.
