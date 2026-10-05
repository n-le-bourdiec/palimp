"""Questionnaires for rule owners, ready to send by email, and a CSV to track answers.

One questionnaire per owner, or per group of candidates when palimp is not
sure who owns a rule (decision 0023: candidates in alphabetical order), or per
application when no name is found. Only rules that need an answer are asked
about (removal candidates first, then verify). Each rule is described in
plain words: what it allows, why palimp asks, and a yes/no question where
"yes" always means the access is still needed. References (R12, E3) point to
the report, for the person who tracks the answers.
"""

import csv
import io
import re

from pydantic import BaseModel

from palimp.models import Finding
from palimp.report import Report, RuleEntry, group_order

ANSWER_COLUMNS = [
    "questionnaire",
    "recipients",
    "rule",
    "policy",
    "verdict",
    "verdict_rule",
    "question",
    "still_needed",
    "answered_by",
    "answered_on",
    "comment",
]


class Questionnaire(BaseModel):
    name: str  # file stem
    group: str
    recipients: list[str]
    rules: list[str]  # R12 references
    text: str


def _plain_reason(entry: RuleEntry) -> str:
    """Why palimp asks, in words an application owner understands."""
    finding: Finding = entry.finding
    assessment = finding.assessment
    assert assessment is not None
    kinds = {e.kind: e.id for e in finding.evidence}
    rule = assessment.verdict_rule

    def ref(*wanted: str) -> str:
        ids = [kinds[k] for k in wanted if k in kinds]
        return f" (ref {entry.ref}: {', '.join(ids)})" if ids else f" (ref {entry.ref})"

    if rule == "V-NOTLIVE":
        reasons = []
        if "deactivated" in kinds:
            reasons.append(
                "it is switched off in the firewall configuration, so it allows nothing today, "
                "but it is still kept there"
            )
        if "decommission" in kinds:
            reasons.append(
                "a change record says the application was retired and the other rules for it "
                "were deleted, but this one was left behind"
            )
        if "migration_leftover" in kinds:
            reasons.append(
                "a later change moved this flow to new servers, and no log shows the old "
                "servers since"
            )
        text = "We think this rule is no longer used: " + "; ".join(reasons) + "."
        return text + ref("deactivated", "decommission", "migration_leftover")
    texts = {
        "V-CONTRADICTION": "One record says this rule is no longer used, yet traffic still "
        "goes through it.",
        "V-TEMPORARY-IN-USE": "It was set up as a temporary opening for any application, and "
        "traffic still uses it. It may now be needed for flows it was not written for.",
        "V-TAKEOVER-IN-USE": "It lets any application through, and it now carries traffic that "
        "other rules, since removed, used to carry.",
        "V-TRAFFIC-STOPPED": "Traffic went through it regularly, then stopped several weeks "
        "before the end of the period we looked at.",
        "V-TRAFFIC-NOT-RECENT": "It was used at some point, but no use was recorded in the "
        "period we looked at.",
        "V-NO-TRAFFIC-SEEN": "No use was recorded in the period we looked at. It may be a rare "
        "job (yearly, quarterly, disaster recovery) that this period does not cover.",
        "V-NO-VISIBILITY": "The firewall does not record whether this rule is used, so we "
        "cannot tell from our side.",
    }
    return texts[rule] + f" (ref {entry.ref}: {', '.join(assessment.verdict_evidence)})"


def _purpose(entry: RuleEntry) -> str:
    assessment = entry.finding.assessment
    assert assessment is not None
    if assessment.intent_apps:
        return f"We believe it serves {', '.join(assessment.intent_apps)}."
    return "We could not tell which application it serves."


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "unassigned"


def _recipients(entry: RuleEntry) -> list[str]:
    assessment = entry.finding.assessment
    assert assessment is not None
    if assessment.owner:
        return [assessment.owner]
    return sorted(assessment.owner_candidates)


def _letter(group: str, recipients: list[str], entries: list[RuleEntry]) -> str:
    count = len(entries)
    apps = sorted({a for e in entries for a in e.finding.assessment.intent_apps})  # type: ignore[union-attr]
    about = f" ({', '.join(apps)})" if apps else ""
    subject = f"Firewall review: {count} rule{'s' if count > 1 else ''}{about} need your answer"
    if recipients and not group.startswith("not sure"):
        greeting = f"Hello {recipients[0]},"
        intro = (
            "We are reviewing the firewall rules we inherited. The rules below seem to belong "
            "to applications you requested changes for. For each one, please answer yes or no."
        )
    elif len(recipients) == 1:
        greeting = f"Hello {recipients[0]},"
        intro = (
            "We are reviewing the firewall rules we inherited. We are not sure you own the "
            "rules below, but you requested changes for an application they involve. For "
            "each one, please answer yes or no, or tell us who should."
        )
    elif recipients:
        greeting = f"Hello {', '.join(recipients)},"
        intro = (
            "We are reviewing the firewall rules we inherited. We are not sure which of you "
            "owns the rules below: each connects applications that some of you requested "
            "changes for. For each one, please answer yes or no, or tell us who should."
        )
    else:
        target = group.removeprefix("no name found").removeprefix(": ") or "the team concerned"
        greeting = f"Hello ({target}),"
        intro = (
            "We are reviewing the firewall rules we inherited. We found no owner name for the "
            "rules below. If they concern you, please answer yes or no for each one; "
            "otherwise, tell us who to ask."
        )
    lines = [
        f"Subject: {subject}",
        "",
        greeting,
        "",
        intro,
        "",
        "A 'no' does not remove anything by itself: we confirm before any change.",
        "",
    ]
    for number, entry in enumerate(entries, start=1):
        lines += [
            f"{number}. Rule {entry.ref} ({entry.finding.policy.name})",
            f"   What it allows: {entry.allows.text}",
            f"   What it is for: {_purpose(entry)}",
            f"   Why we ask: {_plain_reason(entry)}",
            f"   Question: {entry.question}",
            "   Answer: [ ] yes   [ ] no   Comment:",
            "",
        ]
    lines += [
        "Thank you.",
        "",
        "(Prepared with palimp. The references R and E point to the full report.)",
        "",
    ]
    return "\n".join(lines)


def build(report: Report) -> list[Questionnaire]:
    asked = [r for r in report.rules if r.section in ("removal_candidate", "verify")]
    groups: dict[str, list[RuleEntry]] = {}
    for entry in sorted(asked, key=lambda r: r.section != "removal_candidate"):
        groups.setdefault(entry.group, []).append(entry)
    found = []
    for number, group in enumerate(sorted(groups, key=group_order), start=1):
        entries = groups[group]
        recipients = _recipients(entries[0])
        found.append(
            Questionnaire(
                name=f"{number:02d}-{_slug(group)}",
                group=group,
                recipients=recipients,
                rules=[e.ref for e in entries],
                text=_letter(group, recipients, entries),
            )
        )
    return found


def answers_csv(report: Report, questionnaires: list[Questionnaire]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(ANSWER_COLUMNS)
    for q in questionnaires:
        for ref in q.rules:
            entry = report.rule(ref)
            assessment = entry.finding.assessment
            assert assessment is not None
            writer.writerow(
                [
                    q.name,
                    "; ".join(q.recipients),
                    ref,
                    entry.key,
                    entry.section,
                    assessment.verdict_rule,
                    entry.question,
                    "",
                    "",
                    "",
                    "",
                ]
            )
    return buffer.getvalue()
