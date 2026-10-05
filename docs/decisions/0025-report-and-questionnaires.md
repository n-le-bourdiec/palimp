# 0025 Report and questionnaires: citations, blind spots, grouping

- Status: Accepted; questionnaire grouping superseded by 0026
- Date: 2026-10-05

## Context

Session 16 adds `palimp report` and `palimp questions`, still without an LLM.
Evidence IDs (E1, E2, ...) are numbered per policy, so a whole-ruleset report
needs a way to cite them outside the section of one policy, and facts about
the whole artifact set (log window, history horizon, log year, counter
clears) have no evidence ID at all. The questionnaires go to application
owners by email, who do not read evidence IDs.

## Decision

- Rules are numbered R1, R2, ... in configuration order. The report, the
  questionnaires and `answers.csv` use the same numbers.
- Citations: `[E3]` inside the section of one rule (or its row of the keep
  table), `[R12.E3]` anywhere else, `[G1]` for a fact about the whole artifact
  set. G items are listed in the report ("Facts about the whole artifact
  set") and in `report.json` (`global_evidence`). A test checks that every
  citation of the Markdown text resolves.
- Order: summary (counts, what palimp is sure of, what it is not), "What
  palimp could not see" (always: policies without logging, log window, log
  year even when not inferred, history horizon, counter clears even when none
  is found, deactivated policies, missing artifacts), removal candidates with
  their not-live items, verify grouped by who to ask, keep collapsed in a
  `<details>` table, then the "no traffic visible" notes.
- Blind T2 items are never repeated per rule: one note per distinct claim,
  cited from the rule as "see note N1".
- The report builder refuses a `removal_candidate` without a not-live item
  (it raises), so the report can never present one from silence alone.
- Questionnaires: one per named owner, one per candidate group when the
  owner is unsure (candidates sorted, decision 0023), one per application
  when no name is found. Only removal candidates (first) and verify rules are
  asked about. Each question is yes/no, and "yes" always means "still
  needed", so the `still_needed` column of `answers.csv` reads the same way
  for every rule. The email text cites only rule references and evidence IDs
  (`ref R12: E3`), never evidence text with `[E3]` brackets.
- The keep summary states how many keep rules show traffic on the counters
  only (hits since an unknown clear date, possibly old).

## Alternatives considered

- Global evidence numbering across all policies: rejected, it would change
  the IDs `explain` prints and that the future LLM validation pass checks.
- Citing a policy key with each item (`trust/servers/x E3`): rejected for
  length; the key is printed next to the reference where it helps.
- A free-text question per verdict rule (the `question` field of the
  assessment): kept in the report's "Who to ask" context, but the
  questionnaires need a yes/no answer to track.
- One questionnaire per person, merging candidate groups: rejected, a person
  who is only a candidate would get rules stated as theirs.

## Consequences

- Medium dev seed 0: 170 policies, 20 removal candidates, 7 verify, 143 keep,
  18 questionnaires covering 27 rules. Several candidate groups have one
  person (palimp not sure, one name), which gives more small emails.
- No verdict changes: the report reads the findings of `palimp.evidence`.

## Challenged by Nathan

Not challenged yet.
