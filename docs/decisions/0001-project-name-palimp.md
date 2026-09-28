# 0001 Project name: palimp

- Status: Accepted
- Date: 2026-09-28

## Context

The project needs a short name for the repository, the Python package and the
command line tool. The tool reads the layered history of an inherited firewall
(configuration, commits, rollbacks, logs) to recover intent that was written over
and lost.

## Decision

The project, the Python package and the CLI command are all named `palimp`,
short for palimpsest: a manuscript scraped and rewritten, where earlier text can
still be recovered from traces. That is what the tool does with firewall rules.

## Alternatives considered

Each candidate was rejected because of a name collision:

- `sherd`: taken on PyPI, and an active CLI binary with the same name exists.
- `trowel`: taken on PyPI.
- `midden`: taken on PyPI.
- `ostracon`: name of a blockchain consensus binary.
- `exhume`: used by several CLIs, including a forensics toolkit.

## Consequences

- Package `palimp`, command `palimp`, repository `n-le-bourdiec/palimp`.
- The name is short and easy to type, but not self-explanatory: the README must
  say what the tool does in its first sentence.

## Challenged by Nathan

Yes. The challenge: "palimp" contains "limp", which has a negative meaning in
English. Outcome: name kept, decision unchanged.
