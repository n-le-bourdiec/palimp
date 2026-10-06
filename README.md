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
    palimp anonymize -a ARTIFACTS -o OUT --key KEYFILE   # a copy safe to share, see below

`--no-llm` is the default. The LLM writer is experimental in v1 (decision 0029):
`--llm --llm-model MODEL` (on `explain` and `report`)
adds a prose paragraph per rule and an executive summary written by a local Ollama
server (`--llm-url`, localhost only). The LLM never decides anything: every sentence
must cite evidence and may state only facts found in it, otherwise it is replaced by
the deterministic text. Text from the artifacts (descriptions, commit comments,
tickets) is passed to the model as untrusted data and never counts as proof.

Why `--no-llm` is the default: on a 4 GB laptop GPU, the best small model measured
(qwen3.5:4b) wrote 58% of the rule paragraphs without a rejected sentence, about 8%
of the sentences that passed the checks were still misleading (true facts wrongly
related, which the checks cannot see), its paragraphs often left out the intent,
confidence and verdict reason, and a 170-rule report went from 2 seconds to 26 minutes.
The deterministic text is the assessment itself. If you want the prose anyway, use
`--llm --llm-model qwen3.5:4b-q4_K_M`. Details in `docs/llm-writer-measure.md`.

## Sharing a problem config safely in an issue

If palimp misreads your artifacts, an anonymized copy is the best bug report.
`palimp anonymize` writes one that palimp analyzes the same way as the original
(same verdicts, confidence and owner certainty, checked on the test scenarios):

    palimp anonymize -a ARTIFACTS -o shared-copy --key ~/palimp.key

1. Keep the key file private and outside the copy. It is created on the first
   run; reuse it and the same original always gets the same replacement, so a
   follow-up copy matches the first one.
2. What is replaced, the same way in every file: IP addresses (private stay
   private, public stay public, addresses of one subnet stay in one subnet),
   policy, object, application and zone names, people, logins, host names,
   ticket IDs, and every known name, address, ticket ID and e-mail address
   inside descriptions, commit comments and ticket summaries. Other words of
   free text are kept, as are ports, protocols, Junos predefined applications
   and the words palimp reads as signals (`temp`, `users`, `decom`, `CHG`, ...).
3. More cautious: `--strip-text` removes free text entirely (the copy then loses
   the evidence it held), `--shift-dates` moves every date back by one secret
   number of whole weeks.
4. Read the copy before you post it. Only the files palimp reads are copied;
   configuration lines palimp does not read (system, SNMP, ...) are anonymized
   word by word, but a name that appears nowhere in a structured field (a person
   mentioned only in a comment) is not known to palimp and stays. `ANONYMIZED.txt` in the copy says what
   was done.
5. `--mapping` writes `shared-copy.PRIVATE-mapping.json` next to the copy, never
   inside it, to translate answers back. Never attach it. Neither the key nor
   the mapping is needed to analyze the copy.

This is keyed pseudonymization, not encryption: names keep their length and
shared prefixes, so someone who knows your network well may still recognize
parts of it.

Licensed under the Apache License 2.0.
