# palimp

palimp is an open-source, offline command line tool that reconstructs the lost intent
behind inherited firewall rules. Feed it what you find when you inherit a Juniper SRX
(configuration, commit history, rollback files, session logs, hit counts, optional
ticket or CMDB exports) and, for each rule, it tells you the probable reason the rule
exists, the ranked evidence behind that guess, a confidence level, a verdict (keep,
verify, removal candidate) and the question to ask the rule owner. Nothing leaves your
machine: no network egress, no telemetry, and the optional LLM runs locally.

**Status: work in progress.** Nothing usable yet beyond `palimp --version`.

Licensed under the Apache License 2.0.
