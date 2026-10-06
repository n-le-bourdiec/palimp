"""Questionnaires for rule owners, ready to send by email, and a CSV to track answers.

Decision 0026 (supersedes the grouping part of decision 0025): one email per
person, with a section "Rules for your applications" (rules the person owns)
and a section "Rules you may own (please forward if not)" (rules the person is
a candidate owner of, decision 0023). Rules with no name go to one email per
application. A question is sent only if its answer can change the action:
deactivated rules go to the firewall team cleanup list instead, and keep
rules are never asked about. Removal candidates come first in each section.
Each question is yes/no and "yes" always means the access is still needed.
Every questionnaire states that silence keeps the rule (decision 0024: no
removal signal from silence alone).
References (R12, E3) point to the report, for the person who tracks the answers.
"""

import csv
import io
import re

from pydantic import BaseModel

from palimp.models import Finding
from palimp.report import FIREWALL_TEAM, Report, RuleEntry, is_cleanup

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

CLEANUP_NAME = "00-firewall-team-cleanup"


class Questionnaire(BaseModel):
    name: str  # file stem
    group: str  # a person, "no name found: ...", or the firewall team
    recipients: list[str]
    owned: list[str] = []  # R12 references: rules for the person's applications
    may_own: list[str] = []  # rules the person may own (owner candidate)
    text: str

    @property
    def rules(self) -> list[str]:
        return self.owned + self.may_own


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


def _subject(entries: list[RuleEntry]) -> str:
    count = len(entries)
    apps = sorted({a for e in entries for a in e.finding.assessment.intent_apps})  # type: ignore[union-attr]
    about = f" ({', '.join(apps)})" if apps else ""
    rules = f"{count} rule{'s' if count > 1 else ''}"
    return f"Subject: Firewall review: {rules}{about} need your answer"


def _items(entries: list[RuleEntry], start: int, person: str = "") -> list[str]:
    lines = []
    for number, entry in enumerate(entries, start=start):
        assessment = entry.finding.assessment
        assert assessment is not None
        lines += [
            f"{number}. Rule {entry.ref} ({entry.finding.policy.name})",
            f"   What it allows: {entry.allows.text}",
            f"   What it is for: {_purpose(entry)}",
            f"   Why we ask: {_plain_reason(entry)}",
        ]
        others = [c for c in sorted(assessment.owner_candidates) if c != person]
        if person and not assessment.owner and others:
            lines.append(f"   Also asked: {', '.join(others)}")
        lines += [
            f"   Question: {entry.question}",
            "   Answer: [ ] yes   [ ] no   Comment:",
            "",
        ]
    return lines


INTRO = (
    "We are reviewing the firewall rules we inherited. For each rule below, please answer "
    "yes or no."
)
NO_REMOVAL = (
    "A 'no' does not remove anything by itself: we confirm before any change. "
    "If we do not hear back, the rule is kept."
)
CLOSING = [
    "Thank you.",
    "",
    "(Prepared with palimp. The references R and E point to the full report.)",
    "",
]


def _person_letter(person: str, owned: list[RuleEntry], may_own: list[RuleEntry]) -> str:
    lines = [_subject(owned + may_own), "", f"Hello {person},", "", INTRO, NO_REMOVAL, ""]
    if owned:
        lines += [
            f"Rules for your applications ({len(owned)})",
            "",
            "These rules seem to belong to applications you requested changes for.",
            "",
            *_items(owned, 1, person),
        ]
    if may_own:
        lines += [
            f"Rules you may own, please forward if not ({len(may_own)})",
            "",
            "You requested changes for an application these rules involve, but we are not sure "
            "they are yours. If a rule is not yours, please forward it to its owner, or tell us "
            "who to ask.",
            "",
            *_items(may_own, len(owned) + 1, person),
        ]
    return "\n".join(lines + CLOSING)


def _unnamed_letter(group: str, entries: list[RuleEntry]) -> str:
    target = group.removeprefix("no name found").removeprefix(": ") or "the team concerned"
    lines = [
        _subject(entries),
        "",
        f"Hello ({target}),",
        "",
        "We are reviewing the firewall rules we inherited. We found no owner name for the "
        "rules below. If they concern you, please answer yes or no for each one; otherwise, "
        "tell us who to ask.",
        NO_REMOVAL,
        "",
        *_items(entries, 1),
    ]
    return "\n".join(lines + CLOSING)


def _cleanup_letter(entries: list[RuleEntry]) -> str:
    plural = "s" if len(entries) != 1 else ""
    lines = [
        f"Subject: Firewall cleanup list: {len(entries)} deactivated rule{plural}",
        "",
        "Hello firewall team,",
        "",
        "These rules are deactivated: they are still in the configuration but match no "
        "traffic today. Their application owners are not asked, because their answer would "
        "not change the action. For each rule: is it kept on purpose, as a rollback switch? "
        "A 'yes' keeps it, a 'no' makes it a candidate for deletion.",
        NO_REMOVAL,
        "",
        *_items(entries, 1),
    ]
    return "\n".join(lines + CLOSING)


def cleanup_list(report: Report) -> Questionnaire | None:
    """The firewall team cleanup list alone, also written next to the report."""
    return next((q for q in build(report) if q.name == CLEANUP_NAME), None)


def build(report: Report) -> list[Questionnaire]:
    asked = [r for r in report.rules if r.section in ("removal_candidate", "verify")]
    owned: dict[str, list[RuleEntry]] = {}
    may_own: dict[str, list[RuleEntry]] = {}
    unnamed: dict[str, list[RuleEntry]] = {}
    cleanup = []
    for entry in sorted(asked, key=lambda r: r.section != "removal_candidate"):
        assessment = entry.finding.assessment
        assert assessment is not None
        if is_cleanup(entry.finding):
            cleanup.append(entry)
        elif assessment.owner:
            owned.setdefault(assessment.owner, []).append(entry)
        elif assessment.owner_candidates:
            for person in assessment.owner_candidates:
                may_own.setdefault(person, []).append(entry)
        else:
            unnamed.setdefault(entry.group, []).append(entry)
    found = []
    if cleanup:
        found.append(
            Questionnaire(
                name=CLEANUP_NAME,
                group=FIREWALL_TEAM,
                recipients=[FIREWALL_TEAM],
                owned=[e.ref for e in cleanup],
                text=_cleanup_letter(cleanup),
            )
        )
    number = 0
    for person in sorted(set(owned) | set(may_own)):
        number += 1
        mine, maybe = owned.get(person, []), may_own.get(person, [])
        found.append(
            Questionnaire(
                name=f"{number:02d}-{_slug(person)}",
                group=person,
                recipients=[person],
                owned=[e.ref for e in mine],
                may_own=[e.ref for e in maybe],
                text=_person_letter(person, mine, maybe),
            )
        )
    for group in sorted(unnamed):
        number += 1
        entries = unnamed[group]
        found.append(
            Questionnaire(
                name=f"{number:02d}-{_slug(group)}",
                group=group,
                recipients=[],
                owned=[e.ref for e in entries],
                text=_unnamed_letter(group, entries),
            )
        )
    return found


def answers_csv(report: Report, questionnaires: list[Questionnaire]) -> str:
    """One row per rule asked, naming every questionnaire that asks it."""
    asked: dict[str, list[Questionnaire]] = {}
    for q in questionnaires:
        for ref in q.rules:
            asked.setdefault(ref, []).append(q)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(ANSWER_COLUMNS)
    for entry in report.rules:
        if entry.ref not in asked:
            continue
        assessment = entry.finding.assessment
        assert assessment is not None
        found = asked[entry.ref]
        writer.writerow(
            [
                "; ".join(q.name for q in found),
                "; ".join(r for q in found for r in q.recipients),
                entry.ref,
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
