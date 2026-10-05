# palimp

palimp is an open-source, offline command line tool that reconstructs the lost intent
behind inherited firewall rules. Feed it what you find when you inherit a Juniper SRX
(configuration, commit history, rollback files, session logs, hit counts, optional
ticket or CMDB exports) and, for each rule, it tells you the probable reason the rule
exists, the ranked evidence behind that guess, a confidence level, a verdict (keep,
verify, removal candidate) and the question to ask the rule owner. Nothing leaves your
machine: no network egress, no telemetry, and the optional LLM runs locally.

**Status: work in progress.** Deterministic analysis works without an LLM:

    palimp explain --all -a ARTIFACTS            # every policy, its evidence and verdict
    palimp report -a ARTIFACTS -o OUT            # OUT/report.md and OUT/report.json
    palimp questions -a ARTIFACTS -o OUT         # one email per person, cleanup list, OUT/answers.csv

`--no-llm` is the default. `--llm --llm-model MODEL` (on `explain` and `report`)
adds a prose paragraph per rule and an executive summary written by a local Ollama
server (`--llm-url`, localhost only). The LLM never decides anything: every sentence
must cite evidence and may state only facts found in it, otherwise it is replaced by
the deterministic text. No real model has been measured yet.

Licensed under the Apache License 2.0.
