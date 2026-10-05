# 0027 LLM writer: local backends, facts in, cited sentences out, strict validation

- Status: Accepted
- Date: 2026-10-06

## Context

Principle 3: the LLM writes, it never judges, every sentence cites an
evidence ID and a validation pass rejects any sentence without a valid
citation. Decision 0004: the LLM runs locally (Ollama), zero network egress,
and `--no-llm` stays fully functional. Session 17 builds the writer and tests
it with a fake backend only; no real model is run or measured.

## Decision

- Backends (`palimp.llm`): a `Backend` protocol with `generate(Request) ->
  str`, and two implementations.
  - `OllamaBackend`: `POST /api/generate`, temperature 0, seed 0, no
    streaming, standard library only (no new dependency). The URL must be
    http or https, without credentials, to `localhost` or a loopback address;
    `localhost` must resolve to loopback addresses only. Proxy environment
    variables are ignored (empty `ProxyHandler`) and redirects are refused,
    so the request cannot leave the machine even through a proxy or a
    redirect. Any other URL is refused before any connection.
  - `FakeBackend`: deterministic, records its requests. By default it writes
    one sentence per evidence item from the item's own text; tests pass a
    function to return the text they want.
- Input (`palimp.prose`): for one rule, only the facts already established:
  the rule in words, verdict and its reason and evidence IDs, confidence and
  its reason and evidence IDs, intent applications, owner or owner
  candidates, and the evidence items (ID, tier, artifact, locator, claim).
  For the executive summary: S facts (the summary counts and the summary
  statements of the report) and the G facts (decision 0025).
- Output: a short paragraph per rule (`RuleEntry.prose`) and an executive
  summary (`Report.executive_summary`). Nothing else of the report is written
  by or depends on the LLM: verdict, confidence, owner, questions and
  evidence are computed before and never changed (a test compares them).
- Validation, per sentence (split on sentence ends; a lone citation joins the
  sentence before it). A sentence is kept only if:
  - it cites at least one ID, and every cited ID exists for that rule (or
    is an S or G fact for the summary);
  - every IP address, date, time, month name, number (digits or words),
    email, person, application, policy or object name in it appears in the
    text (artifact, locator, claim) of the items it cites. Names are the
    ones palimp knows from the artifacts (ticket requesters and assignees,
    commit users, owners and candidates, application names and aliases,
    policy and object names that are not ordinary words), any run of two or
    more capitalized words (an unknown person), and any word placed before
    "app", "application", "server", "service" or "database";
  - it states no verdict word of another verdict (for example "removed" on a
    keep rule) unless the cited evidence has that word, and no other
    confidence level.
- A failing sentence is dropped and logged (logger `palimp.prose`, one
  warning per rejection), counted in `LLMRun`, and the deterministic text of
  the rule (intent and verdict with their citations) takes its place once.
  An empty response or a backend error also gives the deterministic text.
  `report --llm` writes every rejection to `llm-rejections.json`; both
  commands print the counts to stderr.
- `--no-llm` is the default of `explain` and `report` until a session
  measures a real model. `--llm` needs `--llm-model` with Ollama.
- Citation scheme: `[S1]` is added to decision 0025 for the summary facts,
  which the report lists under the executive summary.

## Alternatives considered

- Validate only the citation (principle 3 as written): rejected, a sentence
  citing a real ID can still invent a person or an address.
- Ask the LLM for JSON (sentence plus IDs): kept for later if small local
  models format citations badly; plain text with bracket citations is what
  the report shows and is easier to check.
- Replace the whole paragraph on the first failure: rejected, the request
  is to drop only the failing sentences; the deterministic text is inserted
  once so no established fact is lost.
- A third-party HTTP client (httpx, requests): rejected, the standard
  library is enough and makes the no-proxy, no-redirect guarantees explicit.
- Exposing the fake backend as a public option: it is reachable only as a
  hidden `--llm-backend fake`, for CLI tests.

## Consequences

- With the default fake backend on Medium dev seed 0 (text copied from the
  evidence), 1148 sentences are kept and 9 rejected, all for a missing
  citation (multi-sentence claims where the fake cites only the last
  sentence). No false rejection from the fact checks on verbatim text.
- The checks are strict: application names that are ordinary words
  (`internet`, `backup`, `files`, `monitoring`) are rejected when the cited
  item does not contain them. A real model will see more rejections than
  the fake; that rate is the first thing the next session measures.
- Known limit: a lowercase application name that palimp never saw, outside
  the "before app/server/..." pattern, is not detected. A negated verdict
  ("should not be kept" on a keep rule) is not detected either.

## Challenged by Nathan

Not challenged yet.
