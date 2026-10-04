# 0015 Practitioner captures accepted as a fixture source

- Status: Accepted
- Date: 2026-10-04
- Supersedes: in decision 0013, the rule "a sample counts only if it is copied
  from a documentation page" and the rejected alternative "samples from forums
  or blog posts"

## Context

Decision 0013 accepts only samples copied from Juniper's documentation.
Documentation samples are old and abridged, and none shows a commit comment in
`show system commit` (VSRX-4d), the main T1 source of palimp. A blog post by a
practitioner (networkcuriosity.com, December 2023) shows that output on a real
vMX running Junos 20.4R3-S2.6, with commit comments whose text the page
states.

## Decision

A second fixture source type is accepted: **practitioner capture**, real
device output published by a third party (blog, technical article). A
practitioner capture counts when:

- it is copied unchanged from the page, as for documentation samples;
- the page shows it as terminal output of a real device (prompt, hostname),
  not as typed-in example text;
- the fixture header gives URL, page title, source type, device and release
  when shown, capture date and retrieval date.

Every fixture header states its source type (`documentation` by default for
the fixtures of session 6, `practitioner capture` otherwise).
`docs/format-assumptions.md` says which source type backs each claim. A real
device capture made by the project (vSRX or SRX) still takes precedence.

## Alternatives considered

- Keep documentation only (0013 as is): VSRX-4d would stay open until a real
  device is available.
- Accept forum posts too: forum snippets are often edited by hand or
  paraphrased; only full terminal captures are accepted here.

## Consequences

- Provenance is weaker than Juniper's documentation (single author, possible
  edits). One practitioner capture confirms a layout; it does not prove every
  release prints it the same way.
- Fixture file names may include the device and year
  (`show-system-commit-vmx-2023.txt`).

## Challenged by Nathan

Decision made by Nathan (project lead), session 7.
