"""Whole-ruleset report: what to remove, what to verify and with whom, what palimp could not see.

Built from the findings of `palimp.evidence` only: no new judgment here. Every
sentence of the report cites evidence: `[E3]` inside the section of one rule,
`[R12.E3]` (rule R12, item E3) elsewhere, `[G1]` for facts about the whole
artifact set (log window, history horizon, log year, counter clears).

Rules are numbered R1, R2, ... in configuration order, so the report, the
questionnaires and the answer CSV point to the same rule.

Blind T2 items ("no traffic visible": no logging, deactivated, artifact
missing) are never repeated per rule: they become one global note each.
"""

import re

from pydantic import BaseModel

from palimp import __version__
from palimp.assess import NOT_LIVE_KINDS
from palimp.counters import clears
from palimp.evidence import collect_all
from palimp.models import Dataset, Evidence, Finding
from palimp.services import describe

SHOWN = 3
CITE = re.compile(r"\[((?:R\d+\.)?E\d+|G\d+)\]")


class Cited(BaseModel):
    """One statement and the evidence it rests on."""

    text: str
    evidence: list[str] = []


class GlobalEvidence(BaseModel):
    """A fact about the whole artifact set, cited as [G1], [G2], ..."""

    id: str
    artifact: str
    locator: str
    claim: str


class Note(BaseModel):
    """One distinct "no traffic visible" claim, standing for many blind items."""

    id: str
    claim: str
    items: list[str] = []  # R12.E7 references


class RuleEntry(BaseModel):
    ref: str
    key: str
    section: str  # removal_candidate, verify or keep
    group: str  # who to ask (see owner_group)
    allows: Cited
    why: list[Cited] = []
    intent: Cited
    owner: str = ""
    question: str = ""  # yes/no question, empty for keep
    finding: Finding


class BlindSpot(BaseModel):
    topic: str
    text: str
    evidence: list[str] = []
    rules: list[str] = []  # R12 or R12.E7 references


class Summary(BaseModel):
    total: int
    keep: int
    verify: int
    removal_candidate: int
    sure: list[Cited] = []
    not_sure: list[Cited] = []


class Report(BaseModel):
    source: str
    palimp_version: str = __version__
    summary: Summary
    blind_spots: list[BlindSpot] = []
    global_evidence: list[GlobalEvidence] = []
    notes: list[Note] = []
    rules: list[RuleEntry] = []

    def rule(self, ref: str) -> RuleEntry:
        return next(r for r in self.rules if r.ref == ref)


# Yes/no questions: "yes" always means the access is still needed.
YES_NO = {
    "V-CONTRADICTION": "Is the traffic that still uses this rule expected, and still needed?",
    "V-NOTLIVE": "Is this access still needed by anyone?",
    "V-TEMPORARY-IN-USE": "Is this temporary opening still needed?",
    "V-TAKEOVER-IN-USE": "Is this broad access still needed as it is?",
    "V-TRAFFIC-STOPPED": "Is this flow still needed (paused rather than ended)?",
    "V-TRAFFIC-NOT-RECENT": "Is this flow still needed, even if it runs rarely?",
    "V-NO-TRAFFIC-SEEN": "Is this flow still needed, even if it runs rarely?",
    "V-NO-VISIBILITY": "Is this flow still needed?",
}


def _cite(ids: list[str], prefix: str = "") -> str:
    return " ".join(f"[{prefix}{i}]" for i in ids)


def _by_id(finding: Finding) -> dict[str, Evidence]:
    return {e.id: e for e in finding.evidence}


def _service(name: str, dataset: Dataset) -> str:
    texts = []
    for line in describe(name, dataset.config.applications):
        text = line.split(": ", 1)[1] if ": " in line else line
        text = text.replace(", Junos predefined application)", ")")
        text = text.replace(", custom application)", ")")
        texts.append(text)
    if name == "any":
        return "any application"
    return "; ".join(dict.fromkeys(texts))


def _side(names: list[str], dataset: Dataset) -> str:
    if not names or names == ["any"]:
        return "any address"
    shown = []
    for name in names[:SHOWN]:
        obj = dataset.config.addresses.get(name)
        if obj is None or name == "any":
            shown.append(name)
        elif obj.kind == "address_set":
            shown.append(f"{name} (group of {len(obj.members)})")
        else:
            shown.append(f"{name} ({obj.value})")
    more = f" and {len(names) - SHOWN} more" if len(names) > SHOWN else ""
    return ", ".join(shown) + more


def allows(finding: Finding, dataset: Dataset) -> Cited:
    """What the rule lets through, in words, citing the address and service items."""
    policy = finding.policy
    action = (policy.action or "").lower()
    verb = {"permit": "Allows", "deny": "Blocks", "reject": "Rejects"}.get(action, "Matches")
    services = "; ".join(_service(a, dataset) for a in policy.applications) or "no application"
    text = (
        f"{verb} {_side(policy.sources, dataset)}, in zone {policy.from_zone}, "
        f"to reach {_side(policy.destinations, dataset)}, in zone {policy.to_zone}, "
        f"for {services}."
    )
    if policy.deactivated:
        text += " The rule is deactivated, so it matches nothing today."
    cited = [e.id for e in finding.evidence if e.kind in ("address_objects", "services")]
    cited += [e.id for e in finding.evidence if e.kind == "deactivated"]
    return Cited(text=text, evidence=cited)


def intent(finding: Finding) -> Cited:
    assessment = finding.assessment
    assert assessment is not None
    if assessment.intent_apps:
        text = (
            f"Probably for {', '.join(assessment.intent_apps)}, "
            f"{assessment.confidence} confidence: {assessment.confidence_reason}."
        )
    else:
        text = (
            f"Purpose unknown, {assessment.confidence} confidence: {assessment.confidence_reason}."
        )
    for conflict in assessment.conflicts:
        text += f" Conflict: {conflict.text}."
    return Cited(text=text, evidence=list(assessment.confidence_evidence))


def owner_group(finding: Finding) -> str:
    """Who to ask: the owner, the candidates when unsure, else the applications."""
    assessment = finding.assessment
    assert assessment is not None
    if assessment.owner:
        return assessment.owner
    if assessment.owner_candidates:
        return "not sure: " + ", ".join(sorted(assessment.owner_candidates))
    if assessment.intent_apps:
        return "no name found: owner of " + ", ".join(assessment.intent_apps)
    return "no name found"


def why(finding: Finding, notes: dict[str, Note], ref: str) -> list[Cited]:
    """The verdict reason, then each item it rests on (blind items point to a note)."""
    assessment = finding.assessment
    assert assessment is not None
    items = _by_id(finding)
    lines = [
        Cited(
            text=f"{assessment.verdict_rule}: {assessment.verdict_reason}.",
            evidence=list(assessment.verdict_evidence),
        )
    ]
    for evidence_id in assessment.verdict_evidence:
        item = items[evidence_id]
        if item.signal == "blind":
            note = notes[item.claim]
            lines.append(Cited(text=f"No traffic visible, see note {note.id}.", evidence=[item.id]))
            continue
        label = "not live: " if item.kind in NOT_LIVE_KINDS else ""
        lines.append(
            Cited(
                text=f"{label}{item.artifact}, {item.locator}: {item.claim}",
                evidence=[item.id],
            )
        )
    return lines


def _global(dataset: Dataset, findings: list[Finding]) -> list[GlobalEvidence]:
    found: list[GlobalEvidence] = []

    def add(artifact: str, locator: str, claim: str) -> None:
        found.append(
            GlobalEvidence(id=f"G{len(found) + 1}", artifact=artifact, locator=locator, claim=claim)
        )

    window = dataset.log_window
    if dataset.log_stats is None:
        add("logs/rt_flow.log", "missing", "no session log was provided")
    elif window.start and window.end:
        days = (window.end.date() - window.start.date()).days + 1
        add(
            "logs/rt_flow.log",
            "first and last log line",
            f"the log covers {window.start:%Y-%m-%d} to {window.end:%Y-%m-%d} ({days} days)",
        )
    if dataset.log_stats is not None:
        year = {
            "inferred": window.year_note,
            "none": window.year_note,
            "forced": f"{window.year_note} (--log-year)",
        }.get(window.year_source, "every log timestamp carries its year")
        add("logs/rt_flow.log", f"log year ({window.year_source or 'in the timestamps'})", year)
    if dataset.commits:
        oldest = (
            max(h.oldest_retained_index for h in dataset.history.values())
            if (dataset.history)
            else None
        )
        commit = next((c for c in dataset.commits if c.index == oldest), None)
        before = sum(1 for f in findings if f.created_in_commit is None)
        if commit is not None:
            add(
                "rollbacks",
                f"oldest retained configuration, commit {commit.index}",
                f"the configuration history goes back to commit {commit.index} "
                f"({commit.timestamp:%Y-%m-%d} by {commit.user}); {before} policies already "
                "existed then, their creation commit and comment are not available",
            )
    else:
        add("commits.txt", "missing", "no commit history was provided")
    if dataset.hit_count_stats is None:
        add("hitcount.txt", "missing", "no hit counts were provided")
    if dataset.ticket_stats is None:
        add("tickets.csv", "missing", "no ticket export was provided")
    for (src, dst), clear in sorted(clears(dataset).items()):
        if latest := clear.latest:
            name, when = latest
            add(
                "hitcount.txt and logs/rt_flow.log",
                f"zone pair {src} -> {dst}",
                f"counters from {src} to {dst} were cleared after {when:%Y-%m-%d %H:%M} "
                f"(policy {name} logged sessions until then and shows 0 hits)",
            )
        if clear.whole_pair:
            add(
                "hitcount.txt",
                f"zone pair {src} -> {dst}",
                f"all {clear.whole_pair} policies from {src} to {dst} show 0 hits while other "
                "zone pairs show hits: these counters were probably cleared, at an unknown date",
            )
    return found


def _blind_spots(
    entries: list[RuleEntry], found: list[GlobalEvidence], dataset: Dataset
) -> list[BlindSpot]:
    spots = []
    nolog = []
    for entry in entries:
        policy = entry.finding.policy
        if policy.deactivated or policy.log_init or policy.log_close:
            continue
        item = next(e for e in entry.finding.evidence if e.kind == "session_log")
        nolog.append(f"{entry.key} [{entry.ref}.{item.id}]")
    spots.append(
        BlindSpot(
            topic="Policies without logging",
            text=(
                f"{len(nolog)} active policies have no `then log` statement: the session log "
                "cannot show their traffic, only the hit counters can, and a zero there may "
                "mean cleared counters."
            ),
            rules=nolog,
        )
    )
    window = [g for g in found if g.locator == "first and last log line"]
    if window:
        spots.append(
            BlindSpot(
                topic="Log window",
                text=(
                    window[0].claim[0].upper() + window[0].claim[1:] + ". A job that runs less "
                    "often (yearly, quarterly, disaster recovery) does not show in it, so no "
                    "traffic seen never makes a rule a removal candidate on its own."
                ),
                evidence=[window[0].id],
            )
        )
    if year := [g for g in found if g.locator.startswith("log year")]:
        guessed = dataset.log_window.year_source in ("inferred", "none")
        spots.append(
            BlindSpot(
                topic="Inferred log year" if guessed else "Log year",
                text=(
                    "Log timestamps have no year; palimp inferred it. Every log date in this "
                    "report depends on that guess (force it with --log-year)."
                    if guessed
                    else "Read from the timestamps, not inferred."
                ),
                evidence=[year[0].id],
            )
        )
    history = [g for g in found if g.artifact in ("rollbacks", "commits.txt")]
    before = [f"{e.key} ({e.ref})" for e in entries if e.finding.created_in_commit is None]
    if history:
        spots.append(
            BlindSpot(
                topic="History horizon",
                text=(
                    f"{history[0].claim[0].upper()}{history[0].claim[1:]}. For these "
                    f"{len(before)} rules the reason they were created is lost unless the "
                    "description or a ticket says it."
                ),
                evidence=[history[0].id],
                rules=before,
            )
        )
    cleared = [g.id for g in found if g.locator.startswith("zone pair")]
    spots.append(
        BlindSpot(
            topic="Inferred counter clears",
            text=(
                f"{len(cleared)} zone pairs show signs of cleared hit counters: a zero there "
                "covers only the time since the clear."
                if cleared
                else "No counter clear could be inferred. hitcount.txt never gives the date "
                "of the last clear, so every count covers an unknown period."
            ),
            evidence=cleared,
        )
    )
    deactivated = [entry.ref for entry in entries if entry.finding.policy.deactivated]
    if deactivated:
        refs = []
        for entry in entries:
            if entry.finding.policy.deactivated:
                item = next(e for e in entry.finding.evidence if e.kind == "deactivated")
                refs.append(f"{entry.key} [{entry.ref}.{item.id}]")
        spots.append(
            BlindSpot(
                topic="Deactivated policies",
                text=f"{len(deactivated)} policies are deactivated: no artifact can show whether "
                "their flow would still be used if they were active.",
                rules=refs,
            )
        )
    missing = [g for g in found if g.locator == "missing"]
    for g in missing:
        spots.append(BlindSpot(topic=f"Missing {g.artifact}", text=g.claim + ".", evidence=[g.id]))
    return spots


def _summary(entries: list[RuleEntry], found: list[GlobalEvidence]) -> Summary:
    count = {s: sum(1 for e in entries if e.section == s) for s in SECTIONS}
    confidence = {
        level: sum(1 for e in entries if e.finding.assessment.confidence == level)  # type: ignore[union-attr]
        for level in ("HIGH", "MEDIUM", "LOW")
    }
    owned = sum(1 for e in entries if e.section != "keep" and e.finding.assessment.owner)  # type: ignore[union-attr]
    asked = count["verify"] + count["removal_candidate"]
    window = [g.id for g in found if g.locator == "first and last log line"]
    sure = [
        Cited(
            text=(
                f"{count['removal_candidate']} rules are removal candidates. Each one rests on "
                "a positive sign that it is not in use (deactivated, decommissioned application, "
                "or a migration leftover whose old servers are silent), listed in its section. "
                "None rests on missing traffic alone."
            )
        ),
        Cited(
            text=(
                f"{count['keep']} rules carry traffic in the session log or the hit counters: "
                "they are in use. That does not prove their intent is right or that they are "
                "not too broad."
            ),
            evidence=window,
        ),
    ]
    not_sure = [
        Cited(
            text=(
                f"{count['verify']} rules need a human answer: palimp cannot tell from the "
                "artifacts whether they are still needed. Their owner (or owner candidates) "
                "is listed with each."
            )
        ),
        Cited(
            text=(
                f"The purpose of each rule is a probable intent: {confidence['HIGH']} HIGH, "
                f"{confidence['MEDIUM']} MEDIUM and {confidence['LOW']} LOW confidence."
            )
        ),
        Cited(
            text=(
                f"An owner is named with certainty for {owned} of the {asked} rules to verify "
                "or remove; the others list candidates or no name."
            )
        ),
        Cited(
            text="Traffic that palimp could not see is described under What palimp could not "
            "see. Read it before acting on any verdict.",
            evidence=[g.id for g in found],
        ),
    ]
    return Summary(total=len(entries), **count, sure=sure, not_sure=not_sure)


SECTIONS = ("removal_candidate", "verify", "keep")


def build(dataset: Dataset, findings: list[Finding] | None = None) -> Report:
    findings = collect_all(dataset) if findings is None else findings
    notes: dict[str, Note] = {}
    for number, finding in enumerate(findings, start=1):
        for item in finding.evidence:
            if item.signal == "blind":
                note = notes.setdefault(item.claim, Note(id=f"N{len(notes) + 1}", claim=item.claim))
                note.items.append(f"R{number}.{item.id}")
    entries = []
    for number, finding in enumerate(findings, start=1):
        assessment = finding.assessment
        assert assessment is not None
        ref = f"R{number}"
        if assessment.verdict == "removal_candidate" and not any(
            e.kind in NOT_LIVE_KINDS for e in finding.evidence
        ):
            raise ValueError(f"{finding.key}: removal_candidate without a not-live item")
        entries.append(
            RuleEntry(
                ref=ref,
                key=str(finding.key),
                section=assessment.verdict,
                group=owner_group(finding),
                allows=allows(finding, dataset),
                why=why(finding, notes, ref),
                intent=intent(finding),
                owner=assessment.ask or "",
                question=YES_NO[assessment.verdict_rule] if assessment.verdict != "keep" else "",
                finding=finding,
            )
        )
    found = _global(dataset, findings)
    return Report(
        source=dataset.source,
        summary=_summary(entries, found),
        blind_spots=_blind_spots(entries, found, dataset),
        global_evidence=found,
        notes=list(notes.values()),
        rules=entries,
    )


def _line(cited: Cited, prefix: str = "") -> str:
    return f"{cited.text} {_cite(cited.evidence, prefix)}".rstrip()


def _rule_md(entry: RuleEntry, level: str) -> list[str]:
    lines = [f"{level} {entry.ref} `{entry.key}`", ""]
    lines.append(f"- **What it allows:** {_line(entry.allows)}")
    title = "Why it can go" if entry.section == "removal_candidate" else "Why palimp asks"
    lines.append(f"- **{title}:** {_line(entry.why[0])}")
    for cited in entry.why[1:]:
        lines.append(f"  - {_line(cited)}")
    lines.append(f"- **Intent:** {_line(entry.intent)}")
    if entry.owner:
        lines.append(f"- **Who to ask:** {entry.owner}")
    if entry.question:
        lines.append(f"- **Question:** {entry.question} (yes / no)")
    lines.append("")
    return lines


def _refs(refs: list[str]) -> str:
    return "; ".join(refs)


def group_order(group: str) -> tuple[int, str]:
    """Named owners first, then candidate groups, then rules with no name."""
    return (2 if group.startswith("no name") else 1 if group.startswith("not sure") else 0, group)


def plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def markdown(report: Report) -> str:
    s = report.summary
    out = [
        "# palimp report",
        "",
        f"Source: `{report.source}`. palimp {report.palimp_version}, deterministic, no LLM. "
        "Read-only: nothing here is a command to push.",
        "",
        "## Summary",
        "",
        "| verdict | rules |",
        "|---|---|",
        f"| removal_candidate | {s.removal_candidate} |",
        f"| verify | {s.verify} |",
        f"| keep | {s.keep} |",
        f"| total | {s.total} |",
        "",
        "**What palimp is sure of**",
        "",
        *[f"- {_line(c)}" for c in s.sure],
        "",
        "**What palimp is not sure of**",
        "",
        *[f"- {_line(c)}" for c in s.not_sure],
        "",
        "## What palimp could not see",
        "",
        "> **Read this before acting on any verdict.** These blind spots apply to every rule "
        "below.",
        "",
    ]
    for spot in report.blind_spots:
        out.append(f"- **{spot.topic}:** {spot.text} {_cite(spot.evidence)}".rstrip())
        if spot.rules:
            out.append(f"  <details><summary>{plural(len(spot.rules), 'rule')}</summary>")
            out.append("")
            out.append(f"  {_refs(spot.rules)}")
            out.append("")
            out.append("  </details>")
    out += ["", "Facts about the whole artifact set:", ""]
    for g in report.global_evidence:
        out.append(f"- [{g.id}] {g.artifact}, {g.locator}: {g.claim}")
    out.append("")

    removal = [r for r in report.rules if r.section == "removal_candidate"]
    out += [f"## Removal candidates ({len(removal)})", ""]
    if not removal:
        out += ["None. palimp never proposes removal from missing traffic alone.", ""]
    out.append(
        "Each rule below has at least one positive sign that it is not in use (marked "
        "*not live*). Confirm with the person to ask before removing anything."
    )
    out.append("")
    for entry in removal:
        out += _rule_md(entry, "###")

    verify = [r for r in report.rules if r.section == "verify"]
    out += [f"## Verify ({len(verify)}), grouped by who to ask", ""]
    groups: dict[str, list[RuleEntry]] = {}
    for entry in verify:
        groups.setdefault(entry.group, []).append(entry)
    for group in sorted(groups, key=group_order):
        out += [f"### {group} ({plural(len(groups[group]), 'rule')})", ""]
        for entry in groups[group]:
            out += _rule_md(entry, "####")

    keep = [r for r in report.rules if r.section == "keep"]
    out += [
        f"## Keep ({len(keep)})",
        "",
        "Traffic is seen on these rules. Collapsed: expand for the list.",
        "",
        f"<details><summary>{len(keep)} rules with traffic seen</summary>",
        "",
        "| rule | policy | intent | confidence | traffic |",
        "|---|---|---|---|---|",
    ]
    for entry in keep:
        a = entry.finding.assessment
        assert a is not None
        apps = ", ".join(a.intent_apps) or "unknown"
        out.append(
            f"| {entry.ref} | `{entry.key}` | {apps} {_cite(a.confidence_evidence)} | "
            f"{a.confidence} | {_cite(a.verdict_evidence)} |"
        )
    out += ["", "</details>", ""]

    out += ["## Notes: no traffic visible", ""]
    out.append(
        "Items that cannot show traffic (no logging, deactivated, artifact missing) are not "
        "repeated per rule. Each stands for one or more evidence items; report.json keeps all."
    )
    out.append("")
    for note in report.notes:
        out.append(f"- {note.id} ({len(note.items)} items): {note.claim}")
    out.append("")
    return "\n".join(out)


def json_report(report: Report) -> str:
    return report.model_dump_json(indent=2) + "\n"


def cited_ids(text: str) -> list[str]:
    """Every evidence citation of a Markdown text: E3, R12.E3 or G1."""
    return CITE.findall(text)
