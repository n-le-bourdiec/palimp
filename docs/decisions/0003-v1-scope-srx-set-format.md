# 0003 v1 scope: Juniper SRX, "set" format only

- Status: Accepted, vSRX lab fixtures superseded by 0013 (documentation-sourced fixtures for now)
- Date: 2026-09-28

## Context

Supporting several vendors and several configuration formats from the start
would spread the effort thin before the core idea (recovering rule intent from
evidence) is proven.

## Decision

v1 handles Juniper SRX security policies only, with configuration input in the
Junos "set" format. Commands in scope: `ingest`, `explain <policy>`, `report`,
`questions`, `anonymize`, `demo`.

Out of scope for v1: other vendors, live connections to devices, configuration
changes, advanced shadowing detection, web UI.

## Alternatives considered

- Junos hierarchical (curly brace) format as the input: common in the field,
  but harder to parse and can be converted with `show configuration | display set`.
- Multi-vendor from day one (Fortinet, Palo Alto, Cisco ASA): much larger
  parsing surface, delays validation of the core approach.

## Consequences

- One parser to build and test, with real output fixtures from a vSRX lab.
- Users with hierarchical configs must convert them to "set" format first.
- Internal models should stay vendor neutral enough that other vendors can be
  added later without a rewrite.

## Challenged by Nathan

No.
